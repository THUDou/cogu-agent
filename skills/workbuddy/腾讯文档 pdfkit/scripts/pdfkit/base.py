
import argparse
import io
import json
import os
import sys
import traceback



_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "json": str,  # 先收字符串，后续 json.loads
}


def _build_parser(params_schema, description=""):
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="JSON config file; keys are merged with CLI args (CLI takes precedence)",
    )

    for p in params_schema:
        name = p["name"]
        ptype = p.get("type", "str")
        required = p.get("required", False)
        default = p.get("default", None)
        choices = p.get("choices", None)
        help_text = p.get("help", "")

        flag = f"--{name}"

        if ptype == "bool":
            parser.add_argument(
                flag,
                action="store_true",
                default=default if default is not None else False,
                help=help_text,
            )
            parser.add_argument(
                f"--no-{name}",
                dest=name,
                action="store_false",
                help=f"Disable {name}",
            )
        else:
            kwargs = {
                "type": _TYPE_MAP.get(ptype, str),
                "default": default,
                "help": help_text,
            }
            if required:
                kwargs["required"] = True
            if choices:
                kwargs["choices"] = choices
            parser.add_argument(flag, **kwargs)

    return parser


def _parse_cli(params_schema, description=""):
    parser = _build_parser(params_schema, description)
    args = parser.parse_args()
    params = vars(args)

    config_path = params.pop("config", None)
    if config_path:
        if not os.path.exists(config_path):
            parser.error(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        merged = dict(config_data)
        for k, v in params.items():
            if v is not None:
                merged[k] = v
        params = merged

    json_fields = {p["name"] for p in params_schema if p.get("type") == "json"}
    for field in json_fields:
        val = params.get(field)
        if isinstance(val, str):
            try:
                params[field] = json.loads(val)
            except json.JSONDecodeError as e:
                parser.error(f"Invalid JSON for --{field}: {e}")

    params = {k: v for k, v in params.items() if v is not None}

    return params


def _parse_stdin():
    return json.loads(sys.stdin.read())



def main(handler, params_schema=None, description=""):
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            elif hasattr(sys.stdout, "buffer"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass
        try:
            if hasattr(sys.stdin, "reconfigure"):
                sys.stdin.reconfigure(encoding="utf-8")
            elif hasattr(sys.stdin, "buffer"):
                sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
        except Exception:
            pass

    _original_stdout = sys.stdout
    _stderr_capture = io.StringIO()
    sys.stderr = _stderr_capture

    def _write_json(obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        out = _original_stdout
        if hasattr(out, "buffer"):
            out.buffer.write(data)
            out.buffer.flush()
        else:
            out.write(data.decode("utf-8"))
            out.flush()

    try:
        if len(sys.argv) > 1 and params_schema:
            params = _parse_cli(params_schema, description)
        else:
            params = _parse_stdin()

        _capture = io.StringIO()
        sys.stdout = _capture

        result = handler(params)

        sys.stdout = _original_stdout
        _write_json({"ok": True, "data": result})

    except SystemExit as e:
        sys.stdout = _original_stdout
        sys.stderr = sys.__stderr__
        raise

    except Exception as e:
        sys.stdout = _original_stdout
        stderr_content = _stderr_capture.getvalue()
        error_info = {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        if stderr_content:
            error_info["stderr"] = stderr_content[-500:]
        _write_json(error_info)

    sys.stdout.flush()
