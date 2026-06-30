
import importlib
import os
import pkgutil
import sys


def _discover_commands():
    commands_dir = os.path.join(os.path.dirname(__file__), "commands")
    commands = {}

    for finder, module_name, is_pkg in pkgutil.iter_modules([commands_dir]):
        if module_name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"pdfkit.commands.{module_name}")
            cmd_name = getattr(mod, "COMMAND", module_name)
            commands[cmd_name] = {
                "module": mod,
                "description": getattr(mod, "DESCRIPTION", ""),
                "params": getattr(mod, "PARAMS", []),
                "handler": getattr(mod, "handler", None),
            }
        except Exception as e:
            print(f"[WARN] Failed to load command '{module_name}': {e}", file=sys.stderr)

    return commands


def _print_command_list(commands):
    print("pdfkit lite — Available commands:\n")
    categories = {}
    for name, info in sorted(commands.items()):
        mod = info["module"]
        category = getattr(mod, "CATEGORY", "other")
        if category not in categories:
            categories[category] = []
        categories[category].append((name, info["description"]))

    category_labels = {
        "read": "Reading & Analysis",
        "edit": "Editing & Modification",
        "organize": "Organization & Transform",
        "security": "Security & Forms",
        "ir": "PDFLens IR (Intermediate Representation)",
        "meta": "Meta & Utility",
        "other": "Other",
    }

    for cat_key in ["read", "edit", "organize", "security", "ir", "meta", "other"]:
        if cat_key not in categories:
            continue
        label = category_labels.get(cat_key, cat_key)
        print(f"  [{label}]")
        for name, desc in categories[cat_key]:
            print(f"    {name:<28} {desc}")
        print()

    print("Usage: python3 -m lite <command> --help")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        commands = _discover_commands()
        _print_command_list(commands)
        sys.exit(0)

    if sys.argv[1] == "--list":
        commands = _discover_commands()
        for name in sorted(commands):
            print(name)
        sys.exit(0)

    cmd_name = sys.argv[1]

    mod = None
    try:
        mod = importlib.import_module(f"pdfkit.commands.{cmd_name}")
    except ModuleNotFoundError:
        commands = _discover_commands()
        if cmd_name in commands:
            mod = commands[cmd_name]["module"]

    if mod is None:
        print(f"Error: Unknown command '{cmd_name}'", file=sys.stderr)
        print(f"Run 'python3 -m lite --list' to see available commands.", file=sys.stderr)
        sys.exit(1)

    handler_fn = getattr(mod, "handler", None)
    params_schema = getattr(mod, "PARAMS", None)
    description = getattr(mod, "DESCRIPTION", "")

    if handler_fn is None:
        print(f"Error: Command '{cmd_name}' has no handler function.", file=sys.stderr)
        sys.exit(1)

    sys.argv = [f"pdfkit-lite {cmd_name}"] + sys.argv[2:]

    from pdfkit.base import main as base_main
    base_main(handler_fn, params_schema=params_schema, description=description)


if __name__ == "__main__":
    main()
