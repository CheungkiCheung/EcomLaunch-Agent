from __future__ import annotations

import sys
from pathlib import Path

from langchain.tools import tool

from deerflow.sandbox.tools import get_thread_data, mask_local_paths_in_output, resolve_and_validate_user_data_path, validate_local_tool_path
from deerflow.tools.types import Runtime


def _ensure_repo_root_on_path() -> None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "evals" / "opensku" / "validators" / "core.py").exists():
            repo_root = str(parent)
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            return


def _resolve_bundle_path(runtime: Runtime, bundle_path: str) -> Path:
    thread_data = get_thread_data(runtime)
    if thread_data is not None and bundle_path.startswith("/mnt/user-data/"):
        validate_local_tool_path(bundle_path, thread_data, read_only=True)
        return Path(resolve_and_validate_user_data_path(bundle_path, thread_data))
    return Path(bundle_path)


@tool("validate_opensku_artifacts", parse_docstring=True)
def validate_opensku_artifacts_tool(runtime: Runtime, bundle_path: str = "/mnt/user-data/outputs") -> str:
    """Validate an OpenSKU artifact bundle before presenting files.

    Use this tool after writing OpenSKU/EcomLaunch artifacts and before calling
    `present_files`. If the result is FAIL, fix the listed files and call this
    tool again until it returns PASS.

    Args:
        bundle_path: Absolute path to the artifact directory. Use `/mnt/user-data/outputs` for normal OpenSKU runs.
    """
    try:
        _ensure_repo_root_on_path()
        from evals.opensku.validators.core import validate_artifact_bundle

        resolved_bundle_path = _resolve_bundle_path(runtime, bundle_path)
        result = validate_artifact_bundle(resolved_bundle_path)
        lines = [
            f"bundle={resolved_bundle_path}",
            f"artifact_count={result.artifact_count}",
            f"status={'PASS' if result.ok else 'FAIL'}",
        ]
        for error in result.errors:
            lines.append(f"- {error}")
        output = "\n".join(lines)
        return mask_local_paths_in_output(output, get_thread_data(runtime))
    except Exception as exc:
        return f"status=ERROR\n- validate_opensku_artifacts failed: {type(exc).__name__}: {exc}"
