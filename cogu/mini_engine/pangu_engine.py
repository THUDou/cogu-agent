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


def _find_qwen_gguf_path() -> Path:
    candidates = []
    mini_base = Path(__file__).resolve().parent.parent.parent.parent / "MINI" / "models"
    if mini_base.is_dir():
        for d in mini_base.iterdir():
            if d.is_dir() and "gguf" in d.name.lower():
                for f in d.rglob("*.gguf"):
                    if "q6" in f.name.lower() or "q8" in f.name.lower() or "q5" in f.name.lower():
                        candidates.append(f)
            if d.is_dir():
                for sub in d.rglob("*.gguf"):
                    if sub not in candidates:
                        candidates.append(sub)
    home_gguf = Path.home() / ".cogu" / "models"
    if home_gguf.is_dir():
        for f in home_gguf.rglob("*.gguf"):
            if f not in candidates:
                candidates.append(f)
    for p in candidates:
        if p.exists():
            return p
    return candidates[0] if candidates else Path("")


MODEL_DIR = _find_model_dir()
GGUF_MODEL_PATH = _find_gguf_path()
QWEN_GGUF_PATH = _find_qwen_gguf_path()


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
        qwen_gguf_path: str = None,
        local_model: str = "auto",
    ):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.gguf_path = Path(gguf_path) if gguf_path else GGUF_MODEL_PATH
        self.qwen_gguf_path = Path(qwen_gguf_path) if qwen_gguf_path else QWEN_GGUF_PATH
        self.local_model = local_model
        self.backend = backend
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.context_length = context_length


class PanguTransformersBackend:
    """基于 transformers 4.53.2 + PyTorch 的推理后端（通过独立venv子进程）"""

    def __init__(self, config: PanguEngineConfig):
        self.config = config
        self._process = None
        self._loaded = False

    def _find_pangu_python(self) -> str:
        base = Path(__file__).resolve().parent.parent.parent
        candidates = [
            base / "pangu-env" / "Scripts" / "python.exe",
            base / "pangu-env" / "bin" / "python",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return sys.executable

    def load(self):
        if self._loaded:
            return

        pangu_python = self._find_pangu_python()
        script = str(Path(__file__).resolve().parent.parent.parent / "pangu-model" / "pangu_inference.py")
        env = os.environ.copy()
        env["PANGU_MODEL_DIR"] = str(self.config.model_dir)
        env["PYTHONPATH"] = str(self.config.model_dir)

        logger.info(f"[PanguEngine] Starting Pangu subprocess with {pangu_python} ...")

        import subprocess
        self._process = subprocess.Popen(
            [pangu_python, script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            bufsize=1,
        )

        line = self._process.stdout.readline().decode("utf-8").strip()
        if line != "READY":
            stderr = self._process.stderr.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Pangu subprocess failed: {line}\n{stderr}")

        self._loaded = True
        logger.info("[PanguEngine] Pangu subprocess ready.")

    def generate(self, prompt: str, system: str = "", stream: bool = False, **kwargs) -> str:
        self.load()
        req = json.dumps({
            "prompt": prompt,
            "system": system,
            "max_new_tokens": kwargs.get("max_new_tokens", self.config.max_new_tokens),
        }, ensure_ascii=False)
        self._process.stdin.write((req + "\n").encode("utf-8"))
        self._process.stdin.flush()

        line = self._process.stdout.readline().decode("utf-8").strip()
        if not line:
            return ""
        resp = json.loads(line)
        return resp.get("content", "")

    def generate_stream(self, prompt: str, system: str = "", **kwargs):
        content = self.generate(prompt, system=system, **kwargs)
        yield content

    def unload(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write(b"EXIT\n")
                self._process.stdin.flush()
                self._process.wait(timeout=10)
            except Exception:
                self._process.kill()
            self._process = None
        self._loaded = False



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
        if self.config.local_model == "qwen" and self.config.qwen_gguf_path.exists():
            try:
                import llama_cpp
                qwen_cfg = PanguEngineConfig(
                    gguf_path=str(self.config.qwen_gguf_path),
                    qwen_gguf_path=str(self.config.qwen_gguf_path),
                    context_length=self.config.context_length,
                    max_new_tokens=self.config.max_new_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                )
                return PanguGGUFBackend(qwen_cfg), "qwen-gguf"
            except ImportError:
                pass

        if self.config.local_model == "pangu":
            if self.config.gguf_path.exists():
                try:
                    import llama_cpp
                    return PanguGGUFBackend(self.config), "gguf"
                except ImportError:
                    pass
            return PanguTransformersBackend(self.config), "transformers"

        if self.config.backend != "auto":
            if self.config.backend == "gguf":
                return PanguGGUFBackend(self.config), "gguf"
            else:
                return PanguTransformersBackend(self.config), "transformers"

        if self.config.qwen_gguf_path.exists():
            try:
                import llama_cpp
                qwen_cfg = PanguEngineConfig(
                    gguf_path=str(self.config.qwen_gguf_path),
                    qwen_gguf_path=str(self.config.qwen_gguf_path),
                    context_length=self.config.context_length,
                    max_new_tokens=self.config.max_new_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                )
                return PanguGGUFBackend(qwen_cfg), "qwen-gguf"
            except ImportError:
                pass

        if self.config.gguf_path.exists():
            try:
                import llama_cpp
                return PanguGGUFBackend(self.config), "gguf"
            except ImportError:
                pass

        if self.config.model_dir.exists() and (self.config.model_dir / "model.safetensors").exists():
            return PanguTransformersBackend(self.config), "transformers"

        return PanguGGUFBackend(self.config), "gguf"


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
        content = self.generate(prompt, system=system, **kwargs)
        model_name = "Qwen3.5-0.8B" if self._backend_type == "qwen-gguf" else "openPangu-Embedded-1B"
        return {
            "id": f"local-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }