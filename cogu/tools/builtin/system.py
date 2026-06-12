import datetime
import os
import platform
import sys

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _system_info() -> str:
    lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Architecture: {platform.machine()}",
        f"Python: {sys.version}",
        f"CPU Count: {os.cpu_count()}",
        f"Current Dir: {os.getcwd()}",
        f"Home: {os.path.expanduser('~')}",
        f"Time: {datetime.datetime.now().isoformat()}",
        f"Timezone: {datetime.datetime.now().astimezone().tzinfo}",
    ]
    return "\n".join(lines)


def _disk_usage(path: str = ".") -> str:
    try:
        import shutil
        usage = shutil.disk_usage(path)
        gb = 1024 ** 3
        lines = [
            f"Path: {path}",
            f"Total: {usage.total / gb:.1f} GB",
            f"Used: {usage.used / gb:.1f} GB",
            f"Free: {usage.free / gb:.1f} GB",
            f"Usage: {usage.used / usage.total * 100:.1f}%",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def register_system_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_system_info, name="system_info", description="Get system information: OS, Python version, CPU, time.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("system"))
    registry.register(FunctionTool(_disk_usage, name="disk_usage", description="Get disk usage statistics for a path.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("system"))
