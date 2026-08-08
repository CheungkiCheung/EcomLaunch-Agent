"""Runtime path resolution for standalone harness usage."""

import os
from pathlib import Path


def aliased_env(primary: str, legacy: str) -> tuple[str, str] | None:
    """Return the first non-empty OpenSKU env value and the name that supplied it."""
    if value := os.getenv(primary):
        return value, primary
    if value := os.getenv(legacy):
        return value, legacy
    return None


def project_root() -> Path:
    """Return the caller project root for runtime-owned files."""
    configured = aliased_env("OPENSKU_PROJECT_ROOT", "DEER_FLOW_PROJECT_ROOT")
    if configured:
        env_root, env_name = configured
        root = Path(env_root).resolve()
        if not root.exists():
            raise ValueError(f"{env_name} is set to '{env_root}', but the resolved path '{root}' does not exist.")
        if not root.is_dir():
            raise ValueError(f"{env_name} is set to '{env_root}', but the resolved path '{root}' is not a directory.")
        return root
    return Path.cwd().resolve()


def runtime_home() -> Path:
    """Return the writable OpenSKU state directory."""
    configured = aliased_env("OPENSKU_HOME", "DEER_FLOW_HOME")
    if configured:
        env_home, _ = configured
        return Path(env_home).resolve()
    return project_root() / ".deer-flow"


def resolve_path(value: str | os.PathLike[str], *, base: Path | None = None) -> Path:
    """Resolve absolute paths as-is and relative paths against the project root."""
    path = Path(value)
    if not path.is_absolute():
        path = (base or project_root()) / path
    return path.resolve()


def existing_project_file(names: tuple[str, ...]) -> Path | None:
    """Return the first existing named file under the project root."""
    root = project_root()
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None
