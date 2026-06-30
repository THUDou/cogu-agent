import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

LOCAL_SERVER_HOST = "127.0.0.1"
LOCAL_SERVER_PORT = 8199
LOCAL_SERVER_URL = f"http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}"


class LocalModelServer:
    _instance = None
    _process = None
    _started = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_running(self) -> bool:
        try:
            resp = urlopen(f"{LOCAL_SERVER_URL}/healthz", timeout=2)
            data = json.loads(resp.read())
            return data.get("status") == "ok"
        except Exception:
            return False

    @property
    def backend_type(self) -> str:
        try:
            resp = urlopen(f"{LOCAL_SERVER_URL}/healthz", timeout=2)
            data = json.loads(resp.read())
            return data.get("backend", "unknown")
        except Exception:
            return "not_running"

    def start(self, local_model: str = "auto", wait_timeout: int = 120) -> bool:
        if self.is_running:
            logger.info("[LocalModelServer] Already running.")
            return True

        if self._process is not None and self._process.poll() is None:
            logger.info("[LocalModelServer] Process already started.")
            return True

        engine_module = "cogu.mini_engine.server"
        cmd = [
            sys.executable, "-m", engine_module,
            "--host", LOCAL_SERVER_HOST,
            "--port", str(LOCAL_SERVER_PORT),
            "--local-model", local_model,
        ]

        logger.info(f"[LocalModelServer] Starting: {' '.join(cmd)}")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent.parent)

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode("utf-8", errors="replace")[:500]
                logger.error(f"[LocalModelServer] Process exited: {self._process.returncode}\n{stderr}")
                return False
            if self.is_running:
                self._started = True
                logger.info(f"[LocalModelServer] Running at {LOCAL_SERVER_URL} (backend: {self.backend_type})")
                return True
            time.sleep(2)

        logger.error("[LocalModelServer] Timed out waiting for server.")
        return False

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            self._started = False
            logger.info("[LocalModelServer] Stopped.")

    def get_provider_config(self, provider_name: str = "local_qwen"):
        from cogu.core.api_config import Provider, ProviderConfig

        if provider_name == "local_pangu":
            return ProviderConfig(
                provider=Provider.LOCAL_PANGU,
                base_url=f"{LOCAL_SERVER_URL}/v1",
                chat_path="/chat/completions",
                default_model="openPangu-Embedded-1B",
            )
        else:
            return ProviderConfig(
                provider=Provider.LOCAL_QWEN,
                base_url=f"{LOCAL_SERVER_URL}/v1",
                chat_path="/chat/completions",
                default_model="Qwen3.5-0.8B",
            )


def check_ollama_available() -> bool:
    try:
        resp = urlopen("http://localhost:11434/api/tags", timeout=3)
        data = json.loads(resp.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        return len(models) > 0
    except Exception:
        return False


def ensure_local_model_available(token_manager=None) -> Optional["ProviderConfig"]:
    from cogu.core.api_config import Provider, ProviderConfig

    server = LocalModelServer()

    if server.is_running:
        backend = server.backend_type
        if backend == "qwen-gguf":
            return server.get_provider_config("local_qwen")
        return server.get_provider_config("local_pangu")

    if not server.start():
        logger.warning("[LocalModelServer] Failed to start local model server.")
        return None

    backend = server.backend_type
    if backend == "qwen-gguf":
        return server.get_provider_config("local_qwen")
    return server.get_provider_config("local_pangu")
