
import concurrent.futures
import json
import os
import sys
import argparse
import tempfile
import threading
import time
from pathlib import Path

from config import load_prefixed_env_file, resolve_env_path

ENV_PATH = resolve_env_path()
IMAGE_ENV_PREFIXES = (
    "IMAGE_",
    "GEMINI_",
    "OPENAI_",
    "MINIMAX_",
    "STABILITY_",
    "BFL_",
    "IDEOGRAM_",
    "QWEN_",
    "DASHSCOPE_",
    "ZHIPU_",
    "BIGMODEL_",
    "VOLCENGINE_",
    "ARK_",
    "MODELSCOPE_",
    "SILICONFLOW_",
    "FAL_",
    "REPLICATE_",
    "OPENROUTER_",
)
DEPRECATED_IMAGE_KEYS = {
    "IMAGE_API_KEY",
    "IMAGE_MODEL",
    "IMAGE_BASE_URL",
}

ALL_ASPECT_RATIOS = [
    "1:1", "1:4", "1:8",
    "2:3", "3:2", "3:4", "4:1", "4:3",
    "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"
]

ALL_IMAGE_SIZES = ["512px", "1K", "2K", "4K"]

BACKEND_REGISTRY = {
    "gemini": {
        "module": "backend_gemini",
        "tier": "core",
        "label": "Google Gemini",
        "default_model": "gemini-3.1-flash-image-preview",
        "key_hint": "GEMINI_API_KEY",
        "aliases": ["google"],
    },
    "openai": {
        "module": "backend_openai",
        "tier": "core",
        "label": "OpenAI / OpenAI-compatible",
        "default_model": "gpt-image-2",
        "key_hint": "OPENAI_API_KEY",
        "aliases": ["openai-compatible", "openai_compatible"],
    },
    "minimax": {
        "module": "backend_minimax",
        "tier": "experimental",
        "label": "MiniMax Image",
        "default_model": "image-01",
        "key_hint": "MINIMAX_API_KEY",
        "aliases": ["minimaxi"],
    },
    "qwen": {
        "module": "backend_qwen",
        "tier": "core",
        "label": "Alibaba Qwen Image",
        "default_model": "qwen-image-2.0-pro",
        "key_hint": "QWEN_API_KEY / DASHSCOPE_API_KEY",
        "aliases": ["alibaba", "dashscope"],
    },
    "zhipu": {
        "module": "backend_zhipu",
        "tier": "core",
        "label": "Zhipu GLM-Image",
        "default_model": "glm-image",
        "key_hint": "ZHIPU_API_KEY / BIGMODEL_API_KEY",
        "aliases": ["bigmodel", "glm", "glm-image"],
    },
    "volcengine": {
        "module": "backend_volcengine",
        "tier": "core",
        "label": "Volcengine Seedream",
        "default_model": "doubao-seedream-4-5-251128",
        "key_hint": "VOLCENGINE_API_KEY / ARK_API_KEY",
        "aliases": ["ark", "doubao", "seedream"],
    },
    "modelscope": {
        "module": "backend_modelscope",
        "tier": "experimental",
        "label": "ModelScope",
        "default_model": "Tongyi-MAI/Z-Image-Turbo",
        "key_hint": "MODELSCOPE_API_KEY",
        "aliases": ["modelscope", "model-scope"]
    },
    "stability": {
        "module": "backend_stability",
        "tier": "extended",
        "label": "Stability AI",
        "default_model": "stable-image-core",
        "key_hint": "STABILITY_API_KEY",
        "aliases": ["stabilityai", "stability-ai"],
    },
    "bfl": {
        "module": "backend_bfl",
        "tier": "extended",
        "label": "Black Forest Labs FLUX",
        "default_model": "flux-pro-1.1-ultra",
        "key_hint": "BFL_API_KEY",
        "aliases": ["flux", "black-forest-labs", "black_forest_labs"],
    },
    "ideogram": {
        "module": "backend_ideogram",
        "tier": "extended",
        "label": "Ideogram",
        "default_model": "ideogram-v3",
        "key_hint": "IDEOGRAM_API_KEY",
    },
    "siliconflow": {
        "module": "backend_siliconflow",
        "tier": "experimental",
        "label": "SiliconFlow",
        "default_model": "Qwen/Qwen-Image",
        "key_hint": "SILICONFLOW_API_KEY",
        "aliases": ["silicon"],
    },
    "fal": {
        "module": "backend_fal",
        "tier": "experimental",
        "label": "fal.ai",
        "default_model": "fal-ai/imagen3/fast",
        "key_hint": "FAL_KEY / FAL_API_KEY",
        "aliases": ["fal-ai"],
    },
    "replicate": {
        "module": "backend_replicate",
        "tier": "experimental",
        "label": "Replicate",
        "default_model": "black-forest-labs/flux-1.1-pro",
        "key_hint": "REPLICATE_API_TOKEN / REPLICATE_API_KEY",
    },
    "openrouter": {
        "module": "backend_openrouter",
        "tier": "experimental",
        "label": "OpenRouter",
        "default_model": "google/gemini-3.1-flash-image-preview",
        "key_hint": "OPENROUTER_API_KEY",
    },
}

TIER_ORDER = {"core": 0, "extended": 1, "experimental": 2}
SUPPORTED_BACKENDS = tuple(sorted(BACKEND_REGISTRY))


def _load_image_env_file() -> None:
    replacements = {
        "IMAGE_API_KEY": "GEMINI_API_KEY / OPENAI_API_KEY / QWEN_API_KEY / ZHIPU_API_KEY / ...",
        "IMAGE_MODEL": "GEMINI_MODEL / OPENAI_MODEL / QWEN_MODEL / ZHIPU_MODEL / ...",
        "IMAGE_BASE_URL": "GEMINI_BASE_URL / OPENAI_BASE_URL / QWEN_BASE_URL / ZHIPU_BASE_URL / ...",
    }
    deprecated_messages = {
        key: (
            "Global image config keys have been removed.\n"
            f"Use IMAGE_BACKEND plus provider-specific keys instead, such as {replacement}."
        )
        for key, replacement in replacements.items()
    }
    load_prefixed_env_file(IMAGE_ENV_PREFIXES, deprecated_keys=deprecated_messages)


def _validate_runtime_config() -> None:
    for key in DEPRECATED_IMAGE_KEYS:
        if key not in os.environ:
            continue
        replacement = {
            "IMAGE_API_KEY": "GEMINI_API_KEY / OPENAI_API_KEY / QWEN_API_KEY / ZHIPU_API_KEY / ...",
            "IMAGE_MODEL": "GEMINI_MODEL / OPENAI_MODEL / QWEN_MODEL / ZHIPU_MODEL / ...",
            "IMAGE_BASE_URL": "GEMINI_BASE_URL / OPENAI_BASE_URL / QWEN_BASE_URL / ZHIPU_BASE_URL / ...",
        }[key]
        raise ValueError(
            f"Unsupported image config key: {key}\n"
            "Global image config keys have been removed.\n"
            f"Use IMAGE_BACKEND plus provider-specific keys instead, such as {replacement}."
        )


def _build_backend_aliases() -> dict[str, str]:
    aliases = {}
    for canonical_name, config in BACKEND_REGISTRY.items():
        aliases[canonical_name] = canonical_name
        for alias in config.get("aliases", []):
            aliases[alias] = canonical_name
    return aliases


BACKEND_ALIASES = _build_backend_aliases()


_BACKEND_PIP_HINTS = {
    "gemini": "google-genai",
    "openai": "openai",
}


def _load_backend(canonical_name: str) -> tuple[object, str]:
    module_name = f"image_backends.{BACKEND_REGISTRY[canonical_name]['module']}"
    try:
        module = __import__(module_name, fromlist=["*"])
    except ImportError as exc:
        pip_name = _BACKEND_PIP_HINTS.get(canonical_name, exc.name or "<dependency>")
        print(
            f"Error: backend '{canonical_name}' needs a package that is not installed.\n"
            f"Missing: {exc.name}\n"
            f"Run: pip install {pip_name}",
            file=sys.stderr,
        )
        sys.exit(1)
    return module, canonical_name


def _print_backend_list() -> None:
    print("Supported image backends:\n")
    tiers = ("core", "extended", "experimental")
    for tier in tiers:
        print(f"{tier.upper()}:")
        for name, info in sorted(
            BACKEND_REGISTRY.items(),
            key=lambda item: (TIER_ORDER[item[1]["tier"]], item[0]),
        ):
            if info["tier"] != tier:
                continue
            print(
                f"  {name:<12} {info['label']} | default={info['default_model']} | keys={info['key_hint']}"
            )
        print()
    print("Recommendation: prefer CORE backends for everyday PPT generation.")
    print(f"Config fallback file: {ENV_PATH}")


def _resolve_backend() -> tuple[object, str]:
    backend_name = os.environ.get("IMAGE_BACKEND", "").strip().lower()
    if backend_name:
        canonical = BACKEND_ALIASES.get(backend_name)
        if not canonical:
            supported = ", ".join(SUPPORTED_BACKENDS)
            print(f"Error: Unknown IMAGE_BACKEND='{backend_name}'. Supported: {supported}")
            sys.exit(1)
        return _load_backend(canonical)

    supported = ", ".join(SUPPORTED_BACKENDS)
    print(
        "Error: No image backend configured.\n"
        "\n"
        "Set IMAGE_BACKEND explicitly in one of these places:\n"
        f"  1. Current process environment\n"
        f"  2. {ENV_PATH}\n"
        "\n"
        f"Supported backends: {supported}\n"
        "\n"
        "Example:\n"
        "  IMAGE_BACKEND=openai\n"
        "  OPENAI_API_KEY=sk-xxx\n"
    )
    sys.exit(1)


DEFAULT_MANIFEST_CONCURRENCY = 3

STATUS_PENDING = "Pending"
STATUS_GENERATED = "Generated"
STATUS_FAILED = "Failed"
STATUS_NEEDS_MANUAL = "Needs-Manual"
VALID_STATUSES = {STATUS_PENDING, STATUS_GENERATED, STATUS_FAILED, STATUS_NEEDS_MANUAL}
RETRYABLE_STATUSES = {STATUS_PENDING, STATUS_FAILED}
REQUIRED_ITEM_FIELDS = ("filename", "prompt", "aspect_ratio", "status")


def load_manifest(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: {exc.msg} "
            f"(line {exc.lineno}, col {exc.colno})"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: top level must be a JSON object, "
            f"got {type(data).__name__}"
        )

    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"{path}: 'items' must be a non-empty array")

    seen_filenames: set[str] = set()
    for i, item in enumerate(items):
        prefix = f"{path}: items[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be an object")
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                raise ValueError(f"{prefix} missing required field '{field}'")
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(
                    f"{prefix} field '{field}' must be a non-empty string"
                )
        if item["status"] not in VALID_STATUSES:
            raise ValueError(
                f"{prefix} status '{item['status']}' is invalid. "
                f"Valid: {sorted(VALID_STATUSES)}"
            )
        fname = item["filename"]
        if fname in seen_filenames:
            raise ValueError(f"{prefix} duplicate filename '{fname}'")
        seen_filenames.add(fname)

    return data


def save_manifest(path: str, data: dict) -> None:
    target = Path(path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=target.stem + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _run_manifest(manifest: dict, manifest_path: str, backend_module, *,
                  initial_concurrency: int,
                  image_size: str,
                  output_dir: str,
                  model: str | None) -> tuple[int, int, int]:
    from image_backends.backend_common import is_rate_limit_error

    items = manifest["items"]
    pending_idx = [
        i for i, it in enumerate(items) if it["status"] in RETRYABLE_STATUSES
    ]
    total = len(pending_idx)
    skipped = len(items) - total

    if total == 0:
        print(
            f"[Manifest] Nothing to do — all {len(items)} items already in "
            "a terminal state (Generated / Needs-Manual)."
        )
        return 0, 0, skipped

    print(
        f"\n[Manifest] {total} item(s) to generate, "
        f"{skipped} already done. concurrency={initial_concurrency}\n"
    )

    queue: list[int] = list(pending_idx)
    ok_count = 0
    fail_count = 0
    current = max(1, initial_concurrency)
    state_lock = threading.Lock()

    def _one(idx: int):
        item = items[idx]
        try:
            saved_path = backend_module.generate(
                prompt=item["prompt"],
                aspect_ratio=item["aspect_ratio"],
                image_size=item.get("image_size", image_size),
                output_dir=output_dir,
                filename=Path(item["filename"]).stem,
                model=item.get("model", model),
            )
            return idx, saved_path, None
        except Exception as exc:  # noqa: BLE001 — backend raises arbitrary types
            return idx, None, exc

    while queue:
        batch_size = min(current, len(queue))
        batch_idx = queue[:batch_size]
        queue = queue[batch_size:]

        print(
            f"--- Batch of {batch_size} (concurrency={current}, "
            f"remaining_after={len(queue)}) ---"
        )

        rate_limited = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as ex:
            futures = [ex.submit(_one, i) for i in batch_idx]
            for fut in concurrent.futures.as_completed(futures):
                idx, saved_path, exc = fut.result()
                item = items[idx]
                with state_lock:
                    if exc is None:
                        item["status"] = STATUS_GENERATED
                        item.pop("last_error", None)
                        ok_count += 1
                        print(f"  [OK]   {item['filename']}")
                    elif is_rate_limit_error(exc):
                        rate_limited = True
                        queue.append(idx)
                        print(f"  [RATE] {item['filename']} — requeued")
                    else:
                        item["status"] = STATUS_FAILED
                        item["last_error"] = str(exc)[:500]
                        fail_count += 1
                        print(f"  [FAIL] {item['filename']}: {exc}")
                    save_manifest(manifest_path, manifest)

        if rate_limited and current > 1:
            new_current = max(1, current // 2)
            print(
                f"\n  ⚠ Rate-limit hit — concurrency {current} → {new_current}, "
                "pausing 10s before next batch\n"
            )
            current = new_current
            time.sleep(10)
        elif queue:
            time.sleep(2)

    print(
        f"\n[Manifest] Done: {ok_count} ok / {fail_count} failed "
        f"({skipped} pre-skipped). Manifest written to {manifest_path}"
    )
    return ok_count, fail_count, skipped


def _resolve_concurrency(cli_value: int | None) -> int:
    if cli_value is not None:
        return max(1, cli_value)
    env_val = os.environ.get("IMAGE_CONCURRENCY", "").strip()
    if env_val.isdigit():
        return max(1, int(env_val))
    return DEFAULT_MANIFEST_CONCURRENCY


def render_manifest_md(manifest: dict) -> str:
    lines: list[str] = []
    lines.append("# Image Generation Prompts")
    lines.append("")
    lines.append("> Auto-generated from `image_prompts.json` by `image_gen.py --render-md`.")
    lines.append("> Do not hand-edit — re-run the command to refresh.")
    lines.append("")

    project = manifest.get("project")
    generated_at = manifest.get("generated_at")
    color_scheme = manifest.get("color_scheme") or {}
    anchor = manifest.get("deck_style_anchor")

    if project:
        lines.append(f"> Project: {project}")
    if generated_at:
        lines.append(f"> Generated: {generated_at}")
    if color_scheme:
        cs = " | ".join(
            f"{k.capitalize()} {v}" for k, v in color_scheme.items()
        )
        lines.append(f"> Color scheme: {cs}")
    if anchor:
        lines.append(f"> Deck Style Anchor: {anchor}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, item in enumerate(manifest["items"], start=1):
        lines.append(f"### Image {i}: {item['filename']}")
        lines.append("")
        lines.append("| Attribute | Value |")
        lines.append("|---|---|")
        for label, key in (
            ("Purpose", "purpose"),
            ("Type", "type"),
            ("Aspect ratio", "aspect_ratio"),
            ("Image size", "image_size"),
            ("Status", "status"),
        ):
            value = item.get(key)
            if value:
                lines.append(f"| {label} | {value} |")
        if item.get("last_error"):
            lines.append(f"| Last error | {item['last_error']} |")
        lines.append("")
        lines.append("**Prompt**:")
        lines.append("")
        lines.append(item["prompt"])
        lines.append("")
        if item.get("alt_text"):
            lines.append("**Alt Text**:")
            lines.append(f"> {item['alt_text']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_manifest_md_to_file(manifest_path: str, manifest: dict | None = None) -> str:
    if manifest is None:
        manifest = load_manifest(manifest_path)
    md_path = str(Path(manifest_path).with_suffix(".md"))
    Path(md_path).write_text(render_manifest_md(manifest), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate images using AI image model providers."
    )
    parser.add_argument(
        "prompt", nargs="?", default="a beautiful landscape",
        help="The text prompt for image generation."
    )
    parser.add_argument(
        "--aspect_ratio", default="1:1", choices=ALL_ASPECT_RATIOS,
        help=f"Aspect ratio. Default: 1:1."
    )
    parser.add_argument(
        "--image_size", default="1K",
        help=f"Image size. Choices: {ALL_IMAGE_SIZES}. Default: 1K. (case-insensitive)"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory. Default: current directory."
    )
    parser.add_argument(
        "--filename", "-f", default=None,
        help="Output filename (without extension). Overrides auto-naming."
    )
    parser.add_argument(
        "--model", "-m", default=None,
        help="Model name. Default depends on backend."
    )
    parser.add_argument(
        "--backend", "-b", default=None, choices=SUPPORTED_BACKENDS,
        help="Override IMAGE_BACKEND env var."
    )
    parser.add_argument(
        "--list-backends", action="store_true",
        help="List available backends grouped by support tier and exit."
    )
    parser.add_argument(
        "--manifest", default=None, metavar="IMAGE_PROMPTS_JSON",
        help=(
            "Path to image_prompts.json. Runs every Pending/Failed item in "
            "parallel; writes status back to the manifest as each completes."
        ),
    )
    parser.add_argument(
        "--concurrency", type=int, default=None,
        help=(
            "Max concurrent requests in --manifest mode. Defaults to "
            f"IMAGE_CONCURRENCY env or {DEFAULT_MANIFEST_CONCURRENCY}. "
            "Auto-halves on rate-limit; 1 is the serial fallback."
        ),
    )
    parser.add_argument(
        "--render-md", dest="render_md", default=None, metavar="IMAGE_PROMPTS_JSON",
        help=(
            "Render <json>'s read-only Markdown sidecar (image_prompts.md) "
            "next to the manifest, then exit. No backend / network needed."
        ),
    )

    args = parser.parse_args()

    if args.list_backends:
        _print_backend_list()
        return

    if args.render_md:
        if not os.path.isfile(args.render_md):
            print(f"Error: manifest file not found: {args.render_md}")
            sys.exit(1)
        try:
            manifest = load_manifest(args.render_md)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        md_path = render_manifest_md_to_file(args.render_md, manifest)
        print(f"Rendered Markdown sidecar: {md_path}")
        return

    try:
        _load_image_env_file()
        _validate_runtime_config()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.backend:
        os.environ["IMAGE_BACKEND"] = args.backend

    backend, backend_name = _resolve_backend()
    print(f"Using backend: {backend_name}\n")

    if args.manifest:
        if not os.path.isfile(args.manifest):
            print(f"Error: manifest file not found: {args.manifest}")
            sys.exit(1)
        try:
            manifest = load_manifest(args.manifest)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        concurrency = _resolve_concurrency(args.concurrency)
        try:
            _, failed, _ = _run_manifest(
                manifest, args.manifest, backend,
                initial_concurrency=concurrency,
                image_size=args.image_size,
                output_dir=args.output or str(Path(args.manifest).parent),
                model=args.model,
            )
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Partial progress preserved in manifest.")
            sys.exit(130)
        md_path = render_manifest_md_to_file(args.manifest, manifest)
        print(f"Rendered Markdown sidecar: {md_path}")
        sys.exit(1 if failed else 0)

    try:
        backend.generate(
            prompt=args.prompt,
            aspect_ratio=args.aspect_ratio,
            image_size=args.image_size,
            output_dir=args.output,
            filename=args.filename,
            model=args.model,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
