import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from cogu.loop.budget import TokenBudget, BudgetExceeded
from cogu.loop.goal_parser import GoalParser, ParsedGoal, GoalType
from cogu.loop.run_log import RunLog, LogLevel
from cogu.loop.state_file import StateFile, GoalState
from cogu.core.goal_judge import GoalJudge, GoalCondition, JudgeVerdict, JudgeResult


class GoalStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    EVAL_PASSED = "eval_passed"
    EVAL_FAILED = "eval_failed"


@dataclass
class GoalResult:
    status: GoalStatus
    goal_text: str = ""
    content: str = ""
    iterations: int = 0
    tokens_used: int = 0
    elapsed_seconds: float = 0.0
    run_log: Optional[RunLog] = None
    error: str = ""
    eval_score: float = 0.0
    eval_results: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in (GoalStatus.SUCCESS, GoalStatus.EVAL_PASSED)

    def summary(self) -> str:
        lines = [
            f"GOAL: {self.goal_text}",
            f"Status: {self.status.value}",
            f"Iterations: {self.iterations} | Tokens: {self.tokens_used} | Elapsed: {self.elapsed_seconds:.1f}s",
        ]
        if self.eval_score > 0:
            lines.append(f"Eval Score: {self.eval_score:.2f}")
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.content:
            lines.append(f"\n{self.content}")
        return "\n".join(lines)


@dataclass
class GoalRunnerConfig:
    max_tokens: int = 200000
    max_iterations: int = 50
    max_wall_seconds: float = 600.0
    warning_ratio: float = 0.8
    kill_on_exceed: bool = True
    state_dir: str = ""
    log_enabled: bool = True
    checkpoint_enabled: bool = True
    progress_callback: Optional[Callable[[str], None]] = None
    judge_enabled: bool = True
    judge_max_retries: int = 3
    judge_model: str = "Qwen3.5-0.8B"
    eval_enabled: bool = False
    eval_types: list[str] = field(default_factory=lambda: ["relevance", "helpfulness"])
    eval_pass_threshold: float = 0.6


class GoalRunner:
    def __init__(self, config: GoalRunnerConfig = None):
        self.config = config or GoalRunnerConfig()
        self.parser = GoalParser()
        self._agent = None
        self._budget: Optional[TokenBudget] = None
        self._run_log: Optional[RunLog] = None
        self._state_file: Optional[StateFile] = None
        self._cancelled = False
        self._judge: Optional[GoalJudge] = None
        self._judge_retries: int = 0

    def bind_agent(self, agent):
        self._agent = agent
        self._judge = GoalJudge()
        if hasattr(agent, "_client") and agent._client:
            self._judge.bind_client(agent._client)
        if hasattr(agent, "_multi_provider") and agent._multi_provider:
            self._judge.bind_multi_provider(agent._multi_provider)

    def cancel(self):
        self._cancelled = True

    async def run(self, goal_text: str) -> GoalResult:
        if not self._agent:
            return GoalResult(
                status=GoalStatus.FAILED,
                goal_text=goal_text,
                error="No agent bound. Call bind_agent() first.",
            )

        started = time.time()
        parsed = self.parser.parse(goal_text, max_iterations=self.config.max_iterations)

        goal_id = uuid.uuid4().hex[:12]
        self._cancelled = False

        self._budget = TokenBudget(
            max_tokens=self.config.max_tokens,
            max_iterations=self.config.max_iterations,
            max_wall_seconds=self.config.max_wall_seconds,
            warning_ratio=self.config.warning_ratio,
            kill_on_exceed=self.config.kill_on_exceed,
        )

        self._run_log = RunLog()
        if self.config.log_enabled and self.config.state_dir:
            log_path = Path(self.config.state_dir) / f"goal_{goal_id}.jsonl"
            self._run_log.file_path = log_path

        state_path = None
        if self.config.checkpoint_enabled and self.config.state_dir:
            state_path = Path(self.config.state_dir) / f"state_{goal_id}.json"

        self._state_file = StateFile(
            goal_id=goal_id,
            goal_text=goal_text,
            state=GoalState.IDLE,
            file_path=state_path,
        )

        self._notify(f"[GOAL] {parsed.display}")
        self._run_log.milestone(f"Goal started: {goal_text}", iteration=0)
        self._state_file.start()

        system_prompt = self._build_system_prompt(parsed)
        self._push_system_message(system_prompt)

        final_content = ""
        total_tokens = 0
        final_status = GoalStatus.SUCCESS
        self._judge_retries = 0

        try:
            for iteration in range(1, self.config.max_iterations + 1):
                if self._cancelled:
                    final_status = GoalStatus.CANCELLED
                    self._run_log.warn("Cancelled by user", iteration=iteration)
                    break

                self._notify(f"  iter {iteration}/{self.config.max_iterations} ...")
                self._state_file.update(iteration, total_tokens)

                result = await self._agent.invoke(
                    user_message=self._next_user_message(parsed, iteration, final_content)
                )

                tokens_this_turn = result.usage.get("total_tokens", 0)
                total_tokens += tokens_this_turn
                final_content = result.content

                self._run_log.info(
                    f"iter {iteration}: {result.status.value}",
                    iteration=iteration,
                    tokens=tokens_this_turn,
                )

                try:
                    budget_status = self._budget.consume(tokens_this_turn, iteration=1)
                    if budget_status.value == "warning":
                        self._notify(f"  [WARN] 预算紧张: {self._budget._format_msg('WARNING', self._budget.used_tokens / self._budget.max_tokens, self._budget.used_iterations / self._budget.max_iterations, self._budget.elapsed / self._budget.max_wall_seconds)}")

                    remaining = self._budget.budget_remaining
                    if remaining["tokens_left"] <= 0 or remaining["iterations_left"] <= 0:
                        final_status = GoalStatus.BUDGET_EXCEEDED
                        self._run_log.warn("Budget exceeded", iteration=iteration)
                        break

                except BudgetExceeded:
                    final_status = GoalStatus.BUDGET_EXCEEDED
                    self._run_log.error("Budget exceeded — killed", iteration=iteration)
                    break

                if self._check_termination(parsed, result, iteration):
                    if self.config.judge_enabled and self._judge:
                        judge_result = await self._run_judge(parsed, result, iteration)
                        if judge_result and not judge_result.is_achieved:
                            self._judge_retries += 1
                            if self._judge_retries <= self.config.judge_max_retries:
                                self._notify(f"  [JUDGE] {judge_result.verdict.value} — continuing (retry {self._judge_retries}/{self.config.judge_max_retries})")
                                self._run_log.warn(
                                    f"Judge says {judge_result.verdict.value}: {judge_result.reasoning[:200]}",
                                    iteration=iteration,
                                )
                                continue
                            else:
                                self._notify(f"  [JUDGE] max retries reached, accepting agent claim")
                                self._run_log.warn("Judge max retries reached", iteration=iteration)
                    final_status = GoalStatus.SUCCESS
                    self._run_log.milestone(f"Goal achieved at iter {iteration}", iteration=iteration)
                    break

        except asyncio.CancelledError:
            final_status = GoalStatus.CANCELLED
        except Exception as e:
            final_status = GoalStatus.FAILED
            self._run_log.error(f"Exception: {e}", iteration=0)
        finally:
            self._state_file.complete(final_content) if final_status == GoalStatus.SUCCESS else self._state_file.fail(f"{final_status.value}: {final_content[:200]}")
            self._run_log.flush()

        elapsed = time.time() - started

        eval_score = 0.0
        eval_results = []
        if final_status == GoalStatus.SUCCESS and self.config.eval_enabled and final_content:
            try:
                from cogu.experiment.evaluator import (
                    EvaluatorConfig, EvaluatorType, EvalItem,
                    ExperimentConfig, ExperimentRunner as EvalRunner,
                )
                eval_configs = []
                for etype in self.config.eval_types:
                    eval_configs.append(EvaluatorConfig(
                        evaluator_id=f"goal_eval_{etype}",
                        name=etype,
                        evaluator_type=EvaluatorType.PROMPT,
                        pass_threshold=self.config.eval_pass_threshold,
                    ))
                eval_item = EvalItem(
                    item_id="goal_result",
                    input=goal_text,
                    output=final_content,
                )
                eval_config = ExperimentConfig(
                    name="goal_evaluation",
                    evaluator_configs=eval_configs,
                    items=[eval_item],
                )
                llm_client = None
                if self._agent and hasattr(self._agent, '_get_client'):
                    try:
                        llm_client = self._agent._get_client()
                    except Exception:
                        pass
                eval_runner = EvalRunner(eval_config, llm_client=llm_client)
                eval_result = eval_runner.run()
                eval_score = eval_result.avg_score
                eval_results = eval_result.item_results
                if eval_score >= self.config.eval_pass_threshold:
                    final_status = GoalStatus.EVAL_PASSED
                else:
                    self._run_log.warn(
                        f"Eval score {eval_score:.2f} below threshold {self.config.eval_pass_threshold}",
                        iteration=self._state_file.iteration,
                    )
            except Exception as e:
                self._run_log.warn(f"Eval error: {e}", iteration=self._state_file.iteration)

        result = GoalResult(
            status=final_status,
            goal_text=goal_text,
            content=final_content,
            iterations=self._state_file.iteration,
            tokens_used=total_tokens,
            elapsed_seconds=elapsed,
            run_log=self._run_log,
            error="" if final_status in (GoalStatus.SUCCESS, GoalStatus.EVAL_PASSED) else f"{final_status.value}",
            eval_score=eval_score,
            eval_results=eval_results,
        )

        self._notify(f"[DONE] {result.summary()}")
        return result

    def _build_system_prompt(self, parsed: ParsedGoal) -> str:
        lines = [
            "You are COGU in GOAL mode. You have ONE clear objective and will iterate until it is achieved.",
            "",
            f"OBJECTIVE: {parsed.target}",
        ]
        if parsed.success_criteria:
            lines.append(f"SUCCESS CRITERIA: {parsed.success_criteria}")
        if parsed.goal_type != GoalType.GENERAL:
            lines.append(f"GOAL TYPE: {parsed.goal_type.value}")
        lines.extend([
            "",
            "RULES:",
            "- Each turn, take ONE concrete action toward the goal.",
            "- After an action, observe the result and decide if the goal is met.",
            "- If the goal is NOT met, plan and execute the next action.",
            "- If the goal IS met, state clearly that the goal is achieved and why.",
            "- If you are stuck, explain what is blocking you.",
            "",
            "Output format: first describe your reasoning, then act.",
        ])
        return "\n".join(lines)

    def _push_system_message(self, prompt: str):
        if hasattr(self._agent, "session") and self._agent.session:
            self._agent.session.add_message("system", prompt)
        elif hasattr(self._agent, "_session") and self._agent._session:
            self._agent._session.add_message("system", prompt)

    def _next_user_message(self, parsed: ParsedGoal, iteration: int, last_content: str) -> str:
        if iteration == 1:
            return f"GOAL: {parsed.raw}\n\nBegin working. Report each action and its result. When the goal is achieved, say so explicitly."
        return (
            f"ITERATION {iteration} — goal not yet achieved.\n\n"
            f"Continue working toward: {parsed.raw}\n"
            "Report your next action and its result."
        )

    def _check_termination(self, parsed: ParsedGoal, result, iteration: int) -> bool:
        content_lower = result.content.lower()
        termination_signals = [
            "goal achieved",
            "goal is achieved",
            "目标已达成",
            "目标已完成",
            "all tests pass",
            "all tests passing",
            "build successful",
            "mission accomplished",
            "task complete",
            "任务完成",
        ]
        for signal in termination_signals:
            if signal in content_lower:
                return True
        return False

    async def _run_judge(self, parsed: ParsedGoal, result, iteration: int) -> Optional[JudgeResult]:
        if not self._judge:
            return None
        try:
            conversation = []
            if hasattr(self._agent, "_session") and self._agent._session:
                conversation = list(self._agent._session.conversation)
            elif hasattr(self._agent, "session") and self._agent.session:
                conversation = list(self._agent.session.conversation)

            goal = GoalCondition(
                goal_text=parsed.raw,
                success_criteria=parsed.success_criteria.split("\n") if parsed.success_criteria else [],
                max_judge_retries=self.config.judge_max_retries,
                judge_model=self.config.judge_model,
            )

            judge_result = await self._judge.judge(
                goal=goal,
                conversation=conversation,
                agent_final_message=result.content,
            )
            self._notify(f"  [JUDGE] {judge_result.summary()}")
            return judge_result
        except Exception as e:
            self._run_log.warn(f"Judge error: {e}", iteration=iteration)
            return None

    def _notify(self, msg: str):
        cb = self.config.progress_callback
        if cb:
            cb(msg)
