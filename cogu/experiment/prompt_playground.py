from __future__ import annotations

import copy
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, AsyncIterator

logger = logging.getLogger(__name__)


class TemplateType(Enum):
    NORMAL = "normal"
    JINJA2 = "jinja2"
    GO_TEMPLATE = "go_template"


class VariableType(Enum):
    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    OBJECT = "object"
    ARRAY = "array"
    PLACEHOLDER = "placeholder"
    MULTI_PART = "multi_part"


@dataclass
class VariableDef:
    key: str = ""
    label: str = ""
    type: VariableType = VariableType.STRING
    default: Any = None
    required: bool = False
    description: str = ""
    options: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "type": self.type.value,
                "default": self.default, "required": self.required,
                "description": self.description, "options": self.options}


@dataclass
class VariableVal:
    key: str = ""
    value: Any = None

    def to_dict(self) -> dict:
        return {"key": self.key, "value": self.value}


@dataclass
class ToolDef:
    name: str = ""
    description: str = ""
    type: str = "function"
    parameters: dict[str, Any] = field(default_factory=dict)
    mock_response: Any = None
    handler: Optional[Callable] = None

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "type": self.type, "parameters": self.parameters}


@dataclass
class SnippetRef:
    snippet_id: str = ""
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageDef:
    role: str = "user"
    content: str = ""
    snippet_refs: list[SnippetRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content,
                "snippet_refs": [s.__dict__ for s in self.snippet_refs]}


@dataclass
class PromptDraft:
    prompt_id: str = ""
    name: str = ""
    description: str = ""
    template_type: TemplateType = TemplateType.NORMAL
    messages: list[MessageDef] = field(default_factory=list)
    variables: list[VariableDef] = field(default_factory=list)
    tools: list[ToolDef] = field(default_factory=list)
    model_config: dict[str, Any] = field(default_factory=dict)
    mcp_servers: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "prompt_id": self.prompt_id, "name": self.name,
            "description": self.description,
            "template_type": self.template_type.value,
            "messages": [m.to_dict() for m in self.messages],
            "variables": [v.to_dict() for v in self.variables],
            "tools": [t.to_dict() for t in self.tools],
            "model_config": self.model_config,
            "mcp_servers": self.mcp_servers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PromptCommit:
    commit_id: str = ""
    prompt_id: str = ""
    version: int = 1
    draft: PromptDef = None
    committed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "commit_id": self.commit_id, "prompt_id": self.prompt_id,
            "version": self.version, "committed_at": self.committed_at,
        }


@dataclass
class DebugStep:
    step_number: int = 0
    input_messages: list[dict] = field(default_factory=list)
    llm_response: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    elapsed_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    finished: bool = False

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "input_messages": self.input_messages,
            "llm_response": self.llm_response[:500],
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "elapsed_ms": self.elapsed_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "finished": self.finished,
        }


@dataclass
class DebugContext:
    prompt_id: str = ""
    user_id: str = ""
    mock_variables: dict[str, Any] = field(default_factory=dict)
    mock_tool_responses: dict[str, Any] = field(default_factory=dict)
    compare_configs: list[dict] = field(default_factory=list)
    single_step: bool = False
    max_iterations: int = 50
    max_duration_s: int = 1800

    def to_dict(self) -> dict:
        return {
            "prompt_id": self.prompt_id, "user_id": self.user_id,
            "mock_variables": self.mock_variables,
            "mock_tool_responses": self.mock_tool_responses,
            "compare_configs": self.compare_configs,
            "single_step": self.single_step,
            "max_iterations": self.max_iterations,
            "max_duration_s": self.max_duration_s,
        }


@dataclass
class DebugLog:
    debug_id: str = ""
    prompt_id: str = ""
    steps: list[DebugStep] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    status: str = "pending"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "debug_id": self.debug_id, "prompt_id": self.prompt_id,
            "steps": [s.to_dict() for s in self.steps],
            "total_elapsed_ms": self.total_elapsed_ms,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "status": self.status, "created_at": self.created_at,
        }


class TemplateFormatter:
    @staticmethod
    def format_normal(template: str, variables: dict[str, Any]) -> str:
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    @staticmethod
    def format_jinja2(template: str, variables: dict[str, Any]) -> str:
        result = template
        for_match = re.finditer(r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
                                result, re.DOTALL)
        for m in for_match:
            item_var, list_var, body = m.group(1), m.group(2), m.group(3)
            items = variables.get(list_var, [])
            expanded = ""
            for item in items:
                expanded += body.replace(f"{{{{{item_var}}}}}", str(item))
            result = result.replace(m.group(0), expanded)

        if_match = re.finditer(r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}',
                               result, re.DOTALL)
        for m in if_match:
            cond_var = m.group(1)
            body = m.group(2)
            if variables.get(cond_var):
                result = result.replace(m.group(0), body)
            else:
                result = result.replace(m.group(0), "")

        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    @staticmethod
    def format_go_template(template: str, variables: dict[str, Any]) -> str:
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{.{key}}}", str(value))
        range_match = re.finditer(r'{{range\s+(\w+)}}(.*?){{end}}', result, re.DOTALL)
        for m in range_match:
            list_var = m.group(1)
            body = m.group(2)
            items = variables.get(list_var, [])
            expanded = ""
            for item in items:
                expanded += body.replace("{{.}}", str(item))
            result = result.replace(m.group(0), expanded)
        return result

    @classmethod
    def format(cls, template: str, variables: dict[str, Any],
               template_type: TemplateType = TemplateType.NORMAL) -> str:
        if template_type == TemplateType.JINJA2:
            return cls.format_jinja2(template, variables)
        elif template_type == TemplateType.GO_TEMPLATE:
            return cls.format_go_template(template, variables)
        return cls.format_normal(template, variables)


class SnippetParser:
    SNIPPET_PATTERN = re.compile(r'\{\{snippet:(\w+)(?::([^}]*))?\}\}')

    @classmethod
    def parse_snippet_refs(cls, content: str) -> list[SnippetRef]:
        refs = []
        for match in cls.SNIPPET_PATTERN.finditer(content):
            snippet_id = match.group(1)
            vars_str = match.group(2) or ""
            variables: dict[str, Any] = {}
            if vars_str:
                for pair in vars_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        variables[k.strip()] = v.strip()
            refs.append(SnippetRef(snippet_id=snippet_id, variables=variables))
        return refs

    @classmethod
    def resolve_snippets(cls, content: str, snippet_store: dict[str, str],
                         variables: dict[str, Any]) -> str:
        def replacer(match):
            snippet_id = match.group(1)
            snippet_template = snippet_store.get(snippet_id, "")
            if not snippet_template:
                return match.group(0)
            vars_str = match.group(2) or ""
            local_vars = dict(variables)
            if vars_str:
                for pair in vars_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        local_vars[k.strip()] = v.strip()
            return TemplateFormatter.format_normal(snippet_template, local_vars)

        return cls.SNIPPET_PATTERN.sub(replacer, content)


class ToolResultsCollector:
    @staticmethod
    def collect(tool_calls: list[dict], tools: list[ToolDef],
                mock_responses: dict[str, Any] = None) -> list[dict]:
        results = []
        tool_map = {t.name: t for t in tools}
        for tc in tool_calls:
            tool_name = tc.get("name", tc.get("function", {}).get("name", ""))
            tool = tool_map.get(tool_name)
            if mock_responses and tool_name in mock_responses:
                results.append({
                    "tool_call_id": tc.get("id", ""),
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(mock_responses[tool_name], ensure_ascii=False),
                })
            elif tool and tool.handler:
                try:
                    args = tc.get("arguments", tc.get("function", {}).get("arguments", {}))
                    if isinstance(args, str):
                        args = json.loads(args)
                    result = tool.handler(**args)
                    results.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
                    })
                except Exception as e:
                    results.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps({"error": str(e)}),
                    })
            else:
                results.append({
                    "tool_call_id": tc.get("id", ""),
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps({"result": f"Mock response for {tool_name}"}),
                })
        return results


class PromptPlayground:
    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client
        self._prompts: dict[str, PromptDraft] = {}
        self._commits: dict[str, list[PromptCommit]] = {}
        self._debug_logs: dict[str, list[DebugLog]] = {}
        self._snippet_store: dict[str, str] = {}

    def create_prompt(self, name: str, description: str = "",
                      template_type: TemplateType = TemplateType.NORMAL) -> PromptDraft:
        prompt = PromptDraft(
            prompt_id=uuid.uuid4().hex[:12],
            name=name, description=description,
            template_type=template_type,
        )
        self._prompts[prompt.prompt_id] = prompt
        return prompt

    def get_prompt(self, prompt_id: str) -> Optional[PromptDraft]:
        return self._prompts.get(prompt_id)

    def list_prompts(self) -> list[PromptDraft]:
        return list(self._prompts.values())

    def save_draft(self, prompt_id: str, **kwargs) -> Optional[PromptDraft]:
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return None
        for key, value in kwargs.items():
            if hasattr(prompt, key):
                setattr(prompt, key, value)
        prompt.updated_at = time.time()
        return prompt

    def commit_version(self, prompt_id: str) -> Optional[PromptCommit]:
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return None
        versions = self._commits.get(prompt_id, [])
        commit = PromptCommit(
            commit_id=uuid.uuid4().hex[:12],
            prompt_id=prompt_id,
            version=len(versions) + 1,
            committed_at=time.time(),
        )
        versions.append(commit)
        self._commits[prompt_id] = versions
        return commit

    def register_snippet(self, snippet_id: str, template: str):
        self._snippet_store[snippet_id] = template

    def debug_streaming(self, prompt_id: str, context: DebugContext = None,
                        on_step: Callable = None) -> DebugLog:
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return DebugLog(debug_id=uuid.uuid4().hex[:12], prompt_id=prompt_id, status="error")

        if context is None:
            context = DebugContext(prompt_id=prompt_id)

        log = DebugLog(
            debug_id=uuid.uuid4().hex[:12],
            prompt_id=prompt_id,
            status="running",
        )

        variables = dict(context.mock_variables)
        for var_def in prompt.variables:
            if var_def.key not in variables and var_def.default is not None:
                variables[var_def.key] = var_def.default

        messages: list[dict] = []
        for msg in prompt.messages:
            content = SnippetParser.resolve_snippets(msg.content, self._snippet_store, variables)
            content = TemplateFormatter.format(content, variables, prompt.template_type)
            messages.append({"role": msg.role, "content": content})

        start_time = time.time()
        iteration = 0

        while iteration < context.max_iterations:
            if (time.time() - start_time) > context.max_duration_s:
                log.status = "timeout"
                break

            iteration += 1
            step = DebugStep(step_number=iteration, input_messages=copy.deepcopy(messages))
            step_start = time.time()

            if self.llm_client:
                try:
                    response = self.llm_client.complete(
                        messages=messages,
                        tools=[t.to_dict() for t in prompt.tools] if prompt.tools else None,
                        **prompt.model_config,
                    )
                    step.llm_response = response if isinstance(response, str) else str(response)
                    step.tool_calls = []

                    if isinstance(response, dict):
                        if "tool_calls" in response:
                            step.tool_calls = response["tool_calls"]
                        if "content" in response:
                            step.llm_response = response["content"]
                        if "usage" in response:
                            step.input_tokens = response["usage"].get("prompt_tokens", 0)
                            step.output_tokens = response["usage"].get("completion_tokens", 0)

                    if step.tool_calls:
                        tool_results = ToolResultsCollector.collect(
                            step.tool_calls, prompt.tools, context.mock_tool_responses)
                        step.tool_results = tool_results
                        messages.append({"role": "assistant", "content": step.llm_response,
                                         "tool_calls": step.tool_calls})
                        for tr in tool_results:
                            messages.append(tr)
                    else:
                        step.finished = True
                        messages.append({"role": "assistant", "content": step.llm_response})

                except Exception as e:
                    step.llm_response = f"Error: {e}"
                    step.finished = True
                    log.status = "error"
            else:
                step.llm_response = f"[No LLM] Step {iteration} mock response"
                step.finished = True

            step.elapsed_ms = (time.time() - step_start) * 1000
            log.total_input_tokens += step.input_tokens
            log.total_output_tokens += step.output_tokens
            log.steps.append(step)

            if on_step:
                on_step(step)

            if step.finished:
                log.status = "completed"
                break

            if context.single_step:
                log.status = "paused"
                break

        log.total_elapsed_ms = (time.time() - start_time) * 1000
        if log.status == "running":
            log.status = "completed"

        if prompt_id not in self._debug_logs:
            self._debug_logs[prompt_id] = []
        self._debug_logs[prompt_id].append(log)

        return log

    def debug_compare(self, prompt_id: str, compare_configs: list[dict],
                      context: DebugContext = None) -> list[DebugLog]:
        results = []
        for config in compare_configs:
            ctx = context or DebugContext(prompt_id=prompt_id)
            ctx.compare_configs = [config]
            if "mock_variables" in config:
                ctx.mock_variables.update(config["mock_variables"])
            if "mock_tool_responses" in config:
                ctx.mock_tool_responses.update(config["mock_tool_responses"])
            log = self.debug_streaming(prompt_id, context=ctx)
            results.append(log)
        return results

    def get_debug_history(self, prompt_id: str) -> list[DebugLog]:
        return self._debug_logs.get(prompt_id, [])
