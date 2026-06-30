"""EvoCUA GUI Agent核心 — S2预测 + 滑动窗口历史 + 上下文溢出降级

融合自EvoCUA mm_agents/evocua/evocua_agent.py + mm_agents/evocua/prompts.py
核心架构:
- S2模式: 工具调用范式, 14种动作空间, relative坐标系
- 滑动窗口: max_history_turns控制历史轮数, 上下文溢出时自动缩减
- S1模式: 思维链范式, Observation/Thought/Action结构化输出
"""
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from cogu.gui.screen_capture import ScreenCapture
from cogu.gui.image_processor import ImageProcessor
from cogu.gui.coordinate_mapper import CoordinateMapper
from cogu.gui.action_executor import ActionExecutor, S2_TOOL_DEF

logger = logging.getLogger("cogu.gui.gui_agent")

S2_SYSTEM_PROMPT = """# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tools_xml}
</tools>

For each function call, return a json object with function name and arguments within <tool_call>..</tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>

# Response format

Response format for every step:
1) Action: a short imperative describing what to do in the UI.
2) A single <tool_call>..</tool_call> block containing only the JSON: {{"name": <function-name>, "arguments": <args-json-object>}}.

Rules:
- Output exactly in the order: Action, <tool_call>.
- Be brief: one sentence for Action.
- Do not output anything else outside those parts.
- If finishing, use action=terminate in the tool call."""


class EvoCUAAgent:
    """EvoCUA桌面GUI自动化Agent

    融合美团EvoCUA核心能力:
    - S2工具调用模式(主力): 14种动作空间 + relative坐标系
    - S1思维链模式: Observation/Thought/Action结构化输出
    - 滑动窗口历史管理: 上下文溢出时自动缩减history_n
    - 逐字符type展开: 解决特殊字符问题
    """

    def __init__(
        self,
        model: str = "qwen3.5-4.6b",
        max_tokens: int = 32768,
        top_p: float = 0.9,
        temperature: float = 0.0,
        action_space: str = "pyautogui",
        observation_type: str = "screenshot",
        max_steps: int = 50,
        prompt_style: str = "S2",
        max_history_turns: int = 4,
        screen_size: Tuple[int, int] = (1920, 1080),
        coordinate_type: str = "relative",
        resize_factor: int = 32,
        llm_client=None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.max_steps = max_steps
        self.prompt_style = prompt_style
        self.max_history_turns = max_history_turns
        self.screen_size = screen_size
        self.coordinate_type = coordinate_type
        self.resize_factor = resize_factor
        self.llm_client = llm_client

        self.screen_capture = ScreenCapture()
        self.image_processor = ImageProcessor(factor=resize_factor)
        self.coordinate_mapper = CoordinateMapper(
            coordinate_type=coordinate_type,
            screen_size=screen_size,
            resize_factor=resize_factor,
        )
        self.action_executor = ActionExecutor(coordinate_mapper=self.coordinate_mapper)

        self.thoughts: List[str] = []
        self.actions: List[str] = []
        self.observations: List[str] = []
        self.responses: List[str] = []
        self.screenshots: List[str] = []

    def reset(self):
        """重置Agent状态"""
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.responses = []
        self.screenshots = []

    def predict(self, instruction: str, obs: Optional[Dict] = None) -> Tuple[Optional[str], List[str]]:
        """主预测循环

        Args:
            instruction: 用户指令
            obs: 观测字典, 可包含screenshot(bytes)

        Returns:
            (response, pyautogui_code_list)
        """
        if obs and "screenshot" in obs:
            screenshot_bytes = obs["screenshot"]
        else:
            screenshot_bytes = self.screen_capture.capture()

        if screenshot_bytes is None:
            logger.error("无法获取截图")
            return None, []

        try:
            from PIL import Image
            from io import BytesIO
            original_img = Image.open(BytesIO(screenshot_bytes))
            original_width, original_height = original_img.size
        except Exception as e:
            logger.warning("截图尺寸读取失败, 使用默认: %s", e)
            original_width, original_height = self.screen_size

        if self.prompt_style == "S2":
            processed_b64, p_width, p_height = self.image_processor.process(screenshot_bytes)
            self.screenshots.append(processed_b64)
            return self._predict_s2(
                instruction, processed_b64, p_width, p_height,
                original_width, original_height,
            )
        else:
            raw_b64 = self.image_processor.encode_image(screenshot_bytes)
            self.screenshots.append(raw_b64)
            return self._predict_s1(instruction, raw_b64)

    def _predict_s2(
        self, instruction, processed_b64, p_width, p_height,
        original_width, original_height,
    ) -> Tuple[Optional[str], List[str]]:
        """S2模式预测: 工具调用范式"""
        current_step = len(self.actions)
        current_history_n = self.max_history_turns

        if self.coordinate_type == "absolute":
            resolution_info = f"* The screen's resolution is {p_width}x{p_height}."
        else:
            resolution_info = "* The screen's resolution is 1000x1000."

        description_prompt = (
            "Use a mouse and keyboard to interact with a computer, and take screenshots.\n"
            "* This is an interface to a desktop GUI.\n"
            "* Some applications may take time to start, so you may need to wait.\n"
            f"{resolution_info}\n"
            "* Make sure to click elements with the cursor tip in the center."
        )

        tools_def = {
            "type": "function",
            "function": {
                "name": "computer_use",
                "description": description_prompt,
                "parameters": S2_TOOL_DEF["function"]["parameters"],
            },
        }

        system_prompt = S2_SYSTEM_PROMPT.format(tools_xml=json.dumps(tools_def))

        response = None
        while True:
            messages = self._build_s2_messages(
                instruction, processed_b64, current_step,
                current_history_n, system_prompt,
            )
            try:
                response = self._call_llm(messages)
                break
            except Exception as e:
                if self._should_giveup_on_context_error(e) and current_history_n > 0:
                    current_history_n -= 1
                    logger.warning("上下文溢出, 缩减历史: history_n=%d", current_history_n)
                else:
                    logger.error("LLM调用失败: %s", e)
                    break

        self.responses.append(response)

        low_level_instruction, pyautogui_code = self.action_executor.parse_response(
            response or "", original_width, original_height, p_width, p_height,
        )

        current_step = len(self.actions) + 1
        first_action = pyautogui_code[0] if pyautogui_code else ""
        if current_step >= self.max_steps and str(first_action).upper() not in ("DONE", "FAIL"):
            logger.warning("达到最大步数 %d, 强制终止", self.max_steps)
            low_level_instruction = "Fail: reached maximum step limit"
            pyautogui_code = ["FAIL"]

        self.actions.append(low_level_instruction)
        return response, pyautogui_code

    def _build_s2_messages(self, instruction, current_img, step, history_n, system_prompt):
        """构建S2模式消息列表(滑动窗口)"""
        messages = [{"role": "system", "content": [{"type": "text", "text": system_prompt}]}]

        previous_actions = []
        history_start_idx = max(0, step - history_n)
        for i in range(history_start_idx):
            if i < len(self.actions):
                previous_actions.append(f"Step {i+1}: {self.actions[i]}")
        previous_actions_str = "\n".join(previous_actions) if previous_actions else "None"

        history_len = min(history_n, len(self.responses))
        if history_len > 0:
            hist_responses = self.responses[-history_len:]
            hist_imgs = self.screenshots[-history_len - 1:-1]

            for i in range(history_len):
                if i < len(hist_imgs):
                    screenshot_b64 = hist_imgs[i]
                    img_url = f"data:image/png;base64,{screenshot_b64}"
                    if i == 0:
                        instruction_prompt = (
                            f"Please generate the next move according to the UI screenshot, "
                            f"instruction and previous actions.\n\n"
                            f"Instruction: {instruction}\n\n"
                            f"Previous actions:\n{previous_actions_str}"
                        )
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": img_url}},
                                {"type": "text", "text": instruction_prompt},
                            ],
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": [{"type": "image_url", "image_url": {"url": img_url}}],
                        })

                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": hist_responses[i]}],
                })

        if history_len == 0:
            instruction_prompt = (
                f"Please generate the next move according to the UI screenshot, "
                f"instruction and previous actions.\n\n"
                f"Instruction: {instruction}\n\n"
                f"Previous actions:\n{previous_actions_str}"
            )
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_img}"}},
                    {"type": "text", "text": instruction_prompt},
                ],
            })
        else:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_img}"}},
                ],
            })

        return messages

    def _predict_s1(self, instruction, raw_b64) -> Tuple[Optional[str], List[str]]:
        """S1模式预测: 思维链范式(简化版)"""
        messages = [{"role": "system", "content": "You are a GUI agent. Perform actions to complete the task."}]

        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{raw_b64}"}},
                {"type": "text", "text": f"Instruction: {instruction}\n\nGenerate the next action."},
            ],
        })

        response = self._call_llm(messages)
        self.responses.append(response)
        self.actions.append("S1 action")
        return response, []

    def _call_llm(self, messages: List[Dict]) -> Optional[str]:
        """调用LLM"""
        if self.llm_client:
            return self.llm_client(messages)

        try:
            import openai
            base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1")
            api_key = os.environ.get("OPENAI_API_KEY", "empty")
            client = openai.OpenAI(base_url=base_url, api_key=api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error("LLM调用失败: %s", e)
            raise

    @staticmethod
    def _should_giveup_on_context_error(e: Exception) -> bool:
        """判断是否为上下文长度错误"""
        error_str = str(e)
        return any(kw in error_str for kw in ("Too Large", "context_length_exceeded", "413"))