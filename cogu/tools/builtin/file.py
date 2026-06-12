import asyncio
import subprocess
import shlex
from pathlib import Path
from cogu.tools.base import FunctionTool, ToolResult, ToolSpec, ToolCapability


def create_read_tool(workspace: str = ".") -> FunctionTool:
    async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
        p = Path(workspace) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not p.exists():
            return f"Error: File not found: {file_path}"
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        end = min(offset + limit, len(lines))
        result = "".join(lines[offset:end])
        if len(lines) > 200:
            result = f"[Lines {offset+1}-{end} of {len(lines)}]\n{result}"
        return result

    return FunctionTool(
        func=read_file,
        name="read_file",
        description="Read a file from the filesystem. Supports offset and limit for large files.",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read"},
                "offset": {"type": "integer", "description": "Line offset to start reading from", "default": 0},
                "limit": {"type": "integer", "description": "Maximum lines to read", "default": 2000},
            },
            "required": ["file_path"],
        },
    )


def create_write_tool(workspace: str = ".") -> FunctionTool:
    async def write_file(file_path: str, content: str) -> str:
        p = Path(workspace) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File written: {file_path} ({len(content)} bytes)"

    return FunctionTool(
        func=write_file,
        name="write_file",
        description="Write content to a file. Creates parent directories if needed.",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["file_path", "content"],
        },
    ).with_capability(ToolCapability.WRITES_FILES)


def create_edit_tool(workspace: str = ".") -> FunctionTool:
    async def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        p = Path(workspace) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not p.exists():
            return f"Error: File not found: {file_path}"
        content = p.read_text(encoding="utf-8")
        if old_string not in content:
            return f"Error: old_string not found in {file_path}"
        new_content = content.replace(old_string, new_string, 1)
        p.write_text(new_content, encoding="utf-8")
        return f"File edited: {file_path}"

    return FunctionTool(
        func=edit_file,
        name="edit_file",
        description="Edit a file by replacing old_string with new_string. The old_string must match exactly.",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit"},
                "old_string": {"type": "string", "description": "Exact text to replace"},
                "new_string": {"type": "string", "description": "Replacement text"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    ).with_capability(ToolCapability.WRITES_FILES)


def create_shell_tool(timeout: int = 120) -> FunctionTool:
    async def shell(command: str, cwd: str = ".") -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            result = stdout.decode("utf-8", errors="replace")
            if stderr:
                result += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")
            return result or "(no output)"
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    return FunctionTool(
        func=shell,
        name="shell",
        description="Execute a shell command. Use with caution.",
        schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory", "default": "."},
            },
            "required": ["command"],
        },
    ).with_capability(ToolCapability.EXECUTES_CODE).require_approval()


def create_glob_tool(workspace: str = ".") -> FunctionTool:
    async def glob(pattern: str) -> str:
        import glob as g
        p = str(Path(workspace) / pattern)
        matches = g.glob(p, recursive=True)
        results = sorted(matches)[:200]
        return "\n".join(results) if results else "No files matched"

    return FunctionTool(
        func=glob,
        name="glob",
        description="Find files matching a glob pattern. Supports ** for recursive search.",
        schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py')"},
            },
            "required": ["pattern"],
        },
    )


def create_grep_tool(workspace: str = ".") -> FunctionTool:
    async def grep(pattern: str, path: str = ".", max_results: int = 50) -> str:
        import subprocess
        try:
            result = subprocess.run(
                ["rg", "--line-number", "--max-count", str(max_results), pattern, path],
                capture_output=True, text=True, timeout=30, cwd=workspace,
            )
            return result.stdout or "No matches found"
        except FileNotFoundError:
            return "Error: ripgrep (rg) not installed. Install it for fast search."

    return FunctionTool(
        func=grep,
        name="grep",
        description="Search for a pattern in files using ripgrep.",
        schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
                "path": {"type": "string", "description": "Directory or file to search", "default": "."},
                "max_results": {"type": "integer", "description": "Maximum results", "default": 50},
            },
            "required": ["pattern"],
        },
    )


def register_builtin_tools(registry, workspace: str = ".", shell_timeout: int = 120):
    registry.register(create_read_tool(workspace))
    registry.register(create_write_tool(workspace))
    registry.register(create_edit_tool(workspace))
    registry.register(create_shell_tool(shell_timeout))
    registry.register(create_glob_tool(workspace))
    registry.register(create_grep_tool(workspace))
