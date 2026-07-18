from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from deerflow.tools.builtins.opensku_artifact_validator import validate_opensku_artifacts_tool


REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_for_outputs(outputs_path: Path) -> SimpleNamespace:
    workspace = outputs_path.parent / "workspace"
    uploads = outputs_path.parent / "uploads"
    workspace.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        state={
            "thread_data": {
                "workspace_path": str(workspace),
                "uploads_path": str(uploads),
                "outputs_path": str(outputs_path),
            }
        },
        context={"thread_id": "thread-opensku-validator"},
        config={"configurable": {"thread_id": "thread-opensku-validator"}},
    )


def test_validate_opensku_artifacts_tool_passes_golden_bundle(tmp_path):
    outputs = tmp_path / "user-data" / "outputs"
    shutil.copytree(REPO_ROOT / "evals" / "opensku" / "fixtures" / "golden" / "golden-001", outputs)

    result = validate_opensku_artifacts_tool.func(
        runtime=_runtime_for_outputs(outputs),
        bundle_path="/mnt/user-data/outputs",
    )

    assert "status=PASS" in result
    assert "artifact_count=10" in result


def test_validate_opensku_artifacts_tool_reports_broken_bundle(tmp_path):
    outputs = tmp_path / "user-data" / "outputs"
    shutil.copytree(REPO_ROOT / "evals" / "opensku" / "fixtures" / "broken" / "broken-001", outputs)

    result = validate_opensku_artifacts_tool.func(
        runtime=_runtime_for_outputs(outputs),
        bundle_path="/mnt/user-data/outputs",
    )

    assert "status=FAIL" in result
    assert "- " in result
