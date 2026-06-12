import os
import shutil
from pathlib import Path

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _read_file(path: str, encoding: str = "utf-8", max_lines: int = 2000) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        content = p.read_text(encoding=encoding)
    except UnicodeDecodeError:
        content = p.read_bytes().hex()[:4000]
        return f"[binary file, hex dump first 4000 chars]\n{content}"
    lines = content.split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        content = "\n".join(lines)
        content += f"\n\n[truncated: {max_lines} of {len(lines)} lines, use offset/limit to read more]"
    return content


def _write_file(path: str, content: str, encoding: str = "utf-8", append: bool = False) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    p.write_text(content, encoding=encoding)
    return f"Written {len(content)} bytes to {path}"


def _list_files(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: path not found: {path}"
    if recursive:
        matches = list(p.rglob(pattern))
    else:
        matches = list(p.glob(pattern))
    lines = [str(m) for m in sorted(matches)[:500]]
    if len(matches) > 500:
        lines.append(f"... and {len(matches) - 500} more")
    return "\n".join(lines)


def _delete_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if p.is_file():
        p.unlink()
        return f"Deleted file: {path}"
    elif p.is_dir():
        shutil.rmtree(p)
        return f"Deleted directory: {path}"
    return f"Error: unknown type: {path}"


def _move_file(source: str, destination: str) -> str:
    src = Path(source)
    if not src.exists():
        return f"Error: source not found: {source}"
    dst = Path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Moved {source} -> {destination}"


def _copy_file(source: str, destination: str) -> str:
    src = Path(source)
    if not src.exists():
        return f"Error: source not found: {source}"
    dst = Path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(str(src), str(dst))
    else:
        shutil.copytree(str(src), str(dst))
    return f"Copied {source} -> {destination}"


def _make_directory(path: str) -> str:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


def _file_info(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: not found: {path}"
    st = p.stat()
    return f"Path: {path}\nSize: {st.st_size} bytes\nIs Dir: {p.is_dir()}\nModified: {st.st_mtime}"


def register_file_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_read_file, name="read_file", description="Read a file from the local filesystem. Supports text and binary files (binary shown as hex).").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("file"))
    registry.register(FunctionTool(_write_file, name="write_file", description="Write content to a file. Creates parent directories if needed. Use append=True to add to existing file.").with_capability(ToolCapability.WRITES_FILES).with_group("file"))
    registry.register(FunctionTool(_list_files, name="list_files", description="List files in a directory. Supports glob patterns and recursive listing.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("file"))
    registry.register(FunctionTool(_delete_file, name="delete_file", description="Delete a file or directory (recursive for directories).").with_capability(ToolCapability.WRITES_FILES).with_group("file"))
    registry.register(FunctionTool(_move_file, name="move_file", description="Move or rename a file/directory.").with_capability(ToolCapability.WRITES_FILES).with_group("file"))
    registry.register(FunctionTool(_copy_file, name="copy_file", description="Copy a file or directory (recursive).").with_capability(ToolCapability.WRITES_FILES).with_group("file"))
    registry.register(FunctionTool(_make_directory, name="make_directory", description="Create a directory and all parent directories.").with_capability(ToolCapability.WRITES_FILES).with_group("file"))
    registry.register(FunctionTool(_file_info, name="file_info", description="Get file metadata: size, type, modification time.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("file"))
