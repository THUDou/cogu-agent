"""
openPangu-Embedded-1B 本地推理引擎

支持两种推理后端:
1. transformers + PyTorch (CPU/GPU) — 直接加载 safetensors
2. llama-cpp-python (GGUF) — 加载量化后的 GGUF 格式 (需预先转换)

提供 OpenAI 兼容 API 接口，可无缝接入 COGU Agent 的 MultiProviderClient。
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


def _find_model_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        candidates = [
            base / "pangu-model",
            base / "_internal" / "pangu-model",
        ]
    else:
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "pangu-model",
        ]
    candidates.append(Path.home() / ".cogu" / "pangu-model")
    for d in candidates:
        if (d / "model.safetensors").exists():
            return d
    return candidates[0]


def _find_gguf_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        candidates = [
            base / "pangu-model" / "openPangu-Embedded-1B-Q4_K_M.gguf",
            base / "_internal" / "pangu-model" / "openPangu-Embedded-1B-Q4_K_M.gguf",
        ]
    else:
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "gguf" / "openPangu-Embedded-1B-Q4_K_M.gguf",
        ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


MODEL_DIR = _find_model_dir()
GGUF_MODEL_PATH = _find_gguf_path()


class PanguEngineConfig:
    def __init__(
        self,
        model_dir: str = None,
        gguf_path: str = None,
        backend: str = "auto",
        device: str = "auto",
        max_new_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        context_length: int = 4096,
    ):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.gguf_path = Path(gguf_path) if gguf_path else GGUF_MODEL_PATH
        self.backend = backend
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.context_length = context_length


class PanguTransformersBackend:
    """基于 transformers + PyTorch 的推理后端"""

    def __init__(self, config: PanguEngineConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"[PanguEngine] Loading model from {self.config.model_dir} ...")

        device_map = self.config.device
        if device_map == "auto":
            import torch
            device_map = "cuda" if torch.cuda.is_available() else "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.config.model_dir),
            use_fast=False,
            trust_remote_code=True,
            local_files_only=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.config.model_dir),
            trust_remote_code=True,
            torch_dtype="auto",
            device_map=device_map,
            local_files_only=True,
        )

        self._loaded = True
        logger.info("[PanguEngine] Model loaded successfully.")

    def generate(self, prompt: str, system: str = "", stream: bool = False, **kwargs) -> str:
        self.load()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        max_new_tokens = kwargs.get("max_new_tokens", self.config.max_new_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)
        top_p = kwargs.get("top_p", self.config.top_p)

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if temperature > 0 else 1.0,
            top_p=top_p,
            do_sample=temperature > 0,
            eos_token_id=45892,
        )

        input_len = inputs.input_ids.shape[1]
        generated = outputs[0, input_len:]
        return self.tokenizer.decode(generated, skip_special_tokens=True)

    def generate_stream(self, prompt: str, system: str = "", **kwargs) -> Generator[str, None, None]:
        self.load()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        from transformers import TextIteratorStreamer
        import threading

        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=kwargs.get("max_new_tokens", self.config.max_new_tokens),
            temperature=kwargs.get("temperature", self.config.temperature) or 1.0,
            top_p=kwargs.get("top_p", self.config.top_p),
            do_sample=True,
            eos_token_id=45892,
        )

        thread = threading.Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for chunk in streamer:
            if chunk:
                yield chunk

        thread.join()

    def unload(self):
        self.model = None
        self.tokenizer = None
        self._loaded = False
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


class PanguGGUFBackend:
    """基于 llama-cpp-python (GGUF) 的推理后端"""

    def __init__(self, config: PanguEngineConfig):
        self.config = config
        self.llm = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return

        from llama_cpp import Llama

        gguf_path = self.config.gguf_path
        if not gguf_path.exists():
            raise FileNotFoundError(
                f"GGUF model not found at {gguf_path}. "
                "Please run convert_to_gguf.py first to convert the model."
            )

        logger.info(f"[PanguEngine] Loading GGUF model from {gguf_path} ...")

        self.llm = Llama(
            model_path=str(gguf_path),
            n_ctx=self.config.context_length,
            verbose=False,
        )

        self._loaded = True
        logger.info("[PanguEngine] GGUF model loaded successfully.")

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        self.load()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=kwargs.get("max_new_tokens", self.config.max_new_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            top_p=kwargs.get("top_p", self.config.top_p),
        )

        return response["choices"][0]["message"]["content"]

    def generate_stream(self, prompt: str, system: str = "", **kwargs) -> Generator[str, None, None]:
        self.load()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=kwargs.get("max_new_tokens", self.config.max_new_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            top_p=kwargs.get("top_p", self.config.top_p),
            stream=True,
        )

        for chunk in response:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content

    def unload(self):
        self.llm = None
        self._loaded = False
        import gc
        gc.collect()


class PanguEngine:
    """
    openPangu-Embedded-1B 推理引擎

    自动选择可用的后端:
    - 优先 GGUF (llama-cpp-python) 如果 GGUF 文件存在
    - 否则使用 transformers + PyTorch

    用法:
        engine = PanguEngine()
        result = engine.generate("你好", system="你是一个助手")
        for chunk in engine.generate_stream("你好"):
            print(chunk, end="")
    """

    def __init__(self, config: PanguEngineConfig = None):
        self.config = config or PanguEngineConfig()
        self._backend = None
        self._backend_type = None

    def _select_backend(self):
        if self.config.backend != "auto":
            if self.config.backend == "gguf":
                return PanguGGUFBackend(self.config), "gguf"
            else:
                return PanguTransformersBackend(self.config), "transformers"

        if self.config.gguf_path.exists():
            try:
                import llama_cpp
                return PanguGGUFBackend(self.config), "gguf"
            except ImportError:
                pass

        return PanguTransformersBackend(self.config), "transformers"

    @property
    def backend(self):
        if self._backend is None:
            self._backend, self._backend_type = self._select_backend()
        return self._backend

    @property
    def backend_type(self) -> str:
        if self._backend_type is None:
            self._backend, self._backend_type = self._select_backend()
        return self._backend_type

    def load(self):
        self.backend.load()

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        return self.backend.generate(prompt, system=system, **kwargs)

    def generate_stream(self, prompt: str, system: str = "", **kwargs) -> Generator[str, None, None]:
        return self.backend.generate_stream(prompt, system=system, **kwargs)

    def unload(self):
        if self._backend:
            self._backend.unload()
            self._backend = None
            self._backend_type = None

    def to_openai_format(self, prompt: str, system: str = "", **kwargs) -> dict:
        """返回 OpenAI 兼容格式的响应"""
        content = self.generate(prompt, system=system, **kwargs)
        return {
            "id": f"pangu-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "openPangu-Embedded-1B",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }