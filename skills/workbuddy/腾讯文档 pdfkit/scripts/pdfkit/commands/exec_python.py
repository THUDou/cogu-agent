import sys
import os
import tempfile

COMMAND = "exec_python"
DESCRIPTION = "安全执行用户 Python 代码片段，支持白名单模块导入和超时控制。"
CATEGORY = "meta"
PARAMS = [
    {"name": "code", "type": "str", "required": True, "help": "要执行的 Python 代码"},
    {"name": "timeout", "type": "int", "required": False, "default": 120, "help": "超时秒数"},
    {"name": "working_dir", "type": "str", "required": False, "help": "工作目录（默认系统临时目录）"},
    {"name": "variables", "type": "json", "required": False, "help": "预注入的变量（JSON 对象）"},
]

ALLOWED_MODULES = {
    "fitz", "PyPDF2", "pypdf", "pdfplumber", "pikepdf",
    "reportlab", "pdf2docx", "camelot", "tabula",
    "PIL", "Pillow",
    "json", "csv", "re", "math", "statistics",
    "collections", "itertools", "functools",
    "datetime", "time", "hashlib", "base64",
    "io", "pathlib", "glob", "shutil", "tempfile",
    "numpy", "pandas",
}

BLOCKED_BUILTINS = {"exec", "eval", "compile", "__import__"}

MAX_OUTPUT_SIZE = 1 * 1024 * 1024  # 1MB 输出限制


def safe_import(name, *args, **kwargs):
    top_level = name.split(".")[0]
    if top_level not in ALLOWED_MODULES:
        raise ImportError(
            f"模块 '{name}' 不在允许列表中。"
            f"允许的模块: {', '.join(sorted(ALLOWED_MODULES))}"
        )
    return __builtins__.__import__(name, *args, **kwargs) if hasattr(__builtins__, '__import__') else __import__(name, *args, **kwargs)


def handler(params):
    import io
    import signal
    import traceback

    code = params.get("code", "")
    if not code or not code.strip():
        raise ValueError("'code' 参数不能为空")

    timeout = params.get("timeout", 120)
    working_dir = params.get("working_dir") or tempfile.gettempdir()
    variables = params.get("variables", {})

    dangerous_patterns = [
        "os.system", "subprocess", "os.popen", "os.exec",
        "shutil.rmtree(\"/\"", "shutil.rmtree('/'",
        "__import__('os').system", "__import__('subprocess')",
    ]
    for pattern in dangerous_patterns:
        if pattern in code:
            raise ValueError(f"代码包含禁止的操作: {pattern}")

    original_dir = os.getcwd()
    os.makedirs(working_dir, exist_ok=True)
    os.chdir(working_dir)

    safe_builtins = {}
    import builtins
    for name in dir(builtins):
        if name not in BLOCKED_BUILTINS and not name.startswith("_"):
            safe_builtins[name] = getattr(builtins, name)
    safe_builtins["__import__"] = safe_import
    safe_builtins["__builtins__"] = safe_builtins

    exec_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    if isinstance(variables, dict):
        exec_globals.update(variables)

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()

    timed_out = False
    _use_sigalrm = hasattr(signal, "SIGALRM")
    old_handler = None

    if _use_sigalrm:
        def timeout_handler(signum, frame):
            nonlocal timed_out
            timed_out = True
            raise TimeoutError(f"代码执行超时（{timeout}秒）")
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    else:
        import threading
        import ctypes

        def _win_timeout():
            nonlocal timed_out
            timed_out = True
            try:
                tid = threading.main_thread().ident
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulonglong(tid),
                    ctypes.py_object(TimeoutError),
                )
            except Exception:
                pass

        _timer = threading.Timer(timeout, _win_timeout)
        _timer.daemon = True
        _timer.start()

    exec_error = None
    exec_traceback = None
    return_value = None

    try:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        try:
            compiled = compile(code, "<mcp_exec>", "exec")
            exec(compiled, exec_globals)

            if "result" in exec_globals:
                return_value = exec_globals["result"]
        except TimeoutError as e:
            exec_error = str(e) if str(e) else f"代码执行超时（{timeout}秒）"
        except Exception as e:
            exec_error = str(e)
            exec_traceback = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    finally:
        os.chdir(original_dir)
        if _use_sigalrm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        else:
            _timer.cancel()

    stdout_text = captured_stdout.getvalue()
    stderr_text = captured_stderr.getvalue()

    if len(stdout_text) > MAX_OUTPUT_SIZE:
        stdout_text = stdout_text[:MAX_OUTPUT_SIZE] + f"\n... [输出被截断，超过 {MAX_OUTPUT_SIZE // 1024}KB 限制]"
    if len(stderr_text) > MAX_OUTPUT_SIZE:
        stderr_text = stderr_text[:MAX_OUTPUT_SIZE] + f"\n... [输出被截断]"

    result = {
        "success": exec_error is None,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }

    if return_value is not None:
        try:
            import json
            json.dumps(return_value)  # 测试是否可序列化
            result["return_value"] = return_value
        except (TypeError, ValueError):
            result["return_value"] = str(return_value)

    if exec_error:
        result["error"] = exec_error
        if exec_traceback:
            result["traceback"] = exec_traceback

    if working_dir != tempfile.gettempdir():
        created_files = []
        for f in os.listdir(working_dir):
            fpath = os.path.join(working_dir, f)
            if os.path.isfile(fpath):
                created_files.append({
                    "path": fpath,
                    "size": os.path.getsize(fpath),
                })
        if created_files:
            result["created_files"] = created_files

    return result


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, params_schema=PARAMS, description=DESCRIPTION)
