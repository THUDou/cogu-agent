import hashlib
from dataclasses import dataclass


@dataclass
class CommandHash:
    algorithm: str = "sha256"
    digest: str = ""
    full_command: str = ""

    @property
    def short(self) -> str:
        return self.digest[:24] if self.digest else ""

    def verify(self, other: "CommandHash") -> bool:
        return self.digest == other.digest


def command_hash(command: str, args: list[str] = None, env: dict = None) -> CommandHash:
    parts = [command]
    if args:
        parts.extend(args)
    raw = " ".join(parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return CommandHash(digest=digest, full_command=raw)


def command_preview(command: str, args: list[str] = None, env: dict = None) -> str:
    parts = [command]
    if args:
        parts.extend(args)
    preview = " ".join(parts)
    if env:
        safe_keys = [k for k in env if k in ("PATH", "HOME", "LANG", "LC_ALL")]
        if safe_keys:
            preview += f" [env: {', '.join(safe_keys)}]"
    return preview


def boot_validate(
    server_configs: dict,
    confirmed_hashes: dict,
) -> list[str]:
    errors = []
    for name, config in server_configs.items():
        if config.get("transport") != "stdio":
            continue
        command = config.get("command", "")
        args = config.get("args", [])
        current_hash = command_hash(command, args)
        confirmed = confirmed_hashes.get(name)
        if not confirmed:
            errors.append(f"Server '{name}' has no confirmed command hash")
        elif not current_hash.verify(confirmed):
            errors.append(
                f"Server '{name}' command hash mismatch: "
                f"expected {confirmed.short}, got {current_hash.short}"
            )
    return errors
