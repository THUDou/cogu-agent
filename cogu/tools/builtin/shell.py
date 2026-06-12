import asyncio
import os
import platform
import subprocess
import tempfile

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


async def _shell_exec(command: str, cwd: str = "", timeout: int = 120) -> str:
    if not command.strip():
        return "Error: empty command"
    shell_flag = True
    if platform.system() == "Windows":
        executable = os.environ.get("COMSPEC", "cmd.exe")
    else:
        executable = "/bin/bash"
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or None,
            executable=executable,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        result = stdout.decode("utf-8", errors="replace")
        if stderr:
            err_text = stderr.decode("utf-8", errors="replace")
            if err_text.strip():
                result += f"\n[stderr]\n{err_text}"
        if not result.strip():
            result = f"[exit code: {proc.returncode}]"
        return result
    except asyncio.TimeoutError:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


async def _python_exec(code: str, timeout: int = 60) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        result = stdout.decode("utf-8", errors="replace")
        if stderr:
            err_text = stderr.decode("utf-8", errors="replace")
            if err_text.strip():
                result += f"\n[stderr]\n{err_text}"
        if not result.strip():
            result = f"[exit code: {proc.returncode}]"
        return result
    except asyncio.TimeoutError:
        return f"Error: execution timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _env_get(key: str) -> str:
    return os.environ.get(key, f"[not set: {key}]")


def register_shell_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_shell_exec, name="shell_exec", description="Execute a shell command. Returns stdout and stderr. Timeout default 120s.").with_capability(ToolCapability.EXECUTES_CODE).with_group("shell"))
    registry.register(FunctionTool(_python_exec, name="python_exec", description="Execute Python code in a subprocess. Returns stdout and stderr. Timeout default 60s.").with_capability(ToolCapability.EXECUTES_CODE).with_group("shell"))
    registry.register(FunctionTool(_env_get, name="env_get", description="Read an environment variable value.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("shell"))
