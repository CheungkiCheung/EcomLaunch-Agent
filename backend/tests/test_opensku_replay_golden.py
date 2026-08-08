"""Golden product-flow replay through the real OpenSKU gateway.

These tests execute the real agents, subagents, upload path, tools, run-budget
middleware, deterministic launch preflight, and artifact API. The only fake is
the hash-keyed recorded chat model, so CI needs no provider key.
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _replay_fixture import build_opensku_config_yaml, opensku_growth_csvs, prepare_hermetic_extras
from starlette.testclient import TestClient

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "replay" / "opensku_product_flows.json"
PACK_FILES = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}


def _reset_process_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    from deerflow.config import app_config as app_config_module
    from deerflow.config import paths as paths_module
    from deerflow.persistence import engine as engine_module

    for module, attr in (
        (app_config_module, "_app_config"),
        (app_config_module, "_app_config_path"),
        (app_config_module, "_app_config_mtime"),
        (paths_module, "_paths_singleton"),
        (engine_module, "_engine"),
        (engine_module, "_session_factory"),
    ):
        monkeypatch.setattr(module, attr, None, raising=False)


_RUNTIME_MODULE_NAMES = (
    "deerflow.tools.tools",
    "deerflow.tools.builtins.task_tool",
    "deerflow.tools.builtins",
    "deerflow.tools",
    "deerflow.subagents.executor",
    "deerflow.subagents",
)
_MISSING = object()


@pytest.fixture()
def _real_subagent_runtime_modules() -> Iterator[None]:
    """Undo the lightweight suite-wide executor mock for this integration test.

    ``tests/conftest.py`` deliberately pre-mocks the executor to keep small unit
    tests free of an old circular-import edge. This golden test exercises the
    real subagent runtime, so it must import the production module instead. The
    original module graph is restored afterward so later tests patch the same
    module objects they imported during collection.
    """
    deerflow_package = sys.modules.get("deerflow")
    parent_attributes: dict[str, object] = {}
    if isinstance(deerflow_package, ModuleType):
        for attribute in ("tools", "subagents"):
            parent_attributes[attribute] = getattr(deerflow_package, attribute, _MISSING)

    original_modules = {name: sys.modules.get(name, _MISSING) for name in _RUNTIME_MODULE_NAMES}
    for name in _RUNTIME_MODULE_NAMES:
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        for name in _RUNTIME_MODULE_NAMES:
            sys.modules.pop(name, None)
        for name, module in original_modules.items():
            if module is not _MISSING:
                sys.modules[name] = module

        if isinstance(deerflow_package, ModuleType):
            for attribute, value in parent_attributes.items():
                if value is _MISSING:
                    deerflow_package.__dict__.pop(attribute, None)
                else:
                    setattr(deerflow_package, attribute, value)


def _register(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"opensku-golden-{uuid.uuid4().hex[:10]}@example.com",
            "password": "very-strong-password-123",
        },
    )
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("csrf_token")
    assert csrf
    return csrf


def _create_thread(client: TestClient, csrf: str, agent_name: str) -> str:
    thread_id = f"opensku-golden-{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {"agent_name": agent_name}},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    return thread_id


def _run_wait(
    client: TestClient,
    *,
    csrf: str,
    thread_id: str,
    scenario: dict[str, Any],
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "user", "content": scenario["prompt"]}
    if files:
        message = {
            "type": "human",
            "content": [{"type": "text", "text": scenario["prompt"]}],
            "additional_kwargs": {"files": files},
        }
    response = client.post(
        f"/api/threads/{thread_id}/runs/wait",
        json={
            "assistant_id": scenario["assistant_id"],
            "input": {"messages": [message]},
            "config": {"recursion_limit": 100},
            "context": scenario["context"],
            "stream_mode": ["values"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    runs = client.get(f"/api/threads/{thread_id}/runs")
    assert runs.status_code == 200, runs.text
    assert runs.json()[0]["status"] == "success", runs.text
    return response.json()


def _tool_names(state: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for message in state.get("messages", []):
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict) and isinstance(call.get("name"), str):
                names.append(call["name"])
    return names


@pytest.mark.no_auto_user
def test_opensku_launch_and_growth_product_flows_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _real_subagent_runtime_modules: None,
) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    scenarios = fixture["scenarios"]
    home = tmp_path / "home"
    home.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        build_opensku_config_yaml(
            model_use="replay_provider:ReplayChatModel",
            home=home,
            repo_root=Path(__file__).resolve().parents[2],
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENSKU_HOME", str(home))
    monkeypatch.setenv("OPENSKU_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OPENSKU_PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("OPENSKU_EXTENSIONS_CONFIG_PATH", str(prepare_hermetic_extras(home)))
    monkeypatch.setenv("OPENSKU_REPLAY_FIXTURE", str(FIXTURE_PATH))
    monkeypatch.setenv("AUTH_JWT_SECRET", "opensku-replay-golden-secret-32-bytes")

    _reset_process_singletons(monkeypatch)
    import replay_provider

    from app.gateway.app import create_app

    replay_provider.reset_replay_misses()
    with TestClient(create_app()) as client:
        csrf = _register(client)

        launch_thread = _create_thread(client, csrf, "ecom-launch")
        launch_state = _run_wait(
            client,
            csrf=csrf,
            thread_id=launch_thread,
            scenario=scenarios["launch"],
        )
        launch_tools = _tool_names(launch_state)
        assert launch_tools[:3] == ["task", "task", "task"]
        assert launch_tools.count("write_file") == 7
        assert launch_tools.count("str_replace") == 2
        assert launch_tools.count("present_files") == 2
        launch_text = json.dumps(launch_state, ensure_ascii=False)
        assert "evidence-ledger.json is not valid readable JSON" in launch_text
        assert "launch-calendar.csv must contain a header and at least one non-empty data row" in launch_text
        artifacts = launch_state.get("artifacts") or []
        assert {Path(path).name for path in artifacts} == PACK_FILES

        artifact = client.get(f"/api/threads/{launch_thread}/artifacts/mnt/user-data/outputs/evidence-ledger.json")
        assert artifact.status_code == 200, artifact.text
        assert artifact.json()["entries"][0]["label"] == "observed_public"

        growth_thread = _create_thread(client, csrf, "data-inspector")
        upload = client.post(
            f"/api/threads/{growth_thread}/uploads",
            files=[("files", (name, content.encode("utf-8"), "text/csv")) for name, content in opensku_growth_csvs().items()],
            headers={"X-CSRF-Token": csrf},
        )
        assert upload.status_code == 200, upload.text
        uploaded_items = upload.json()["files"]
        assert {item["filename"] for item in uploaded_items} == {
            "customers.csv",
            "assignments.csv",
            "outcomes.csv",
        }
        growth_state = _run_wait(
            client,
            csrf=csrf,
            thread_id=growth_thread,
            scenario=scenarios["growth"],
            files=[
                {
                    "filename": item["filename"],
                    "size": item["size"],
                    "path": item["virtual_path"],
                    "status": "uploaded",
                }
                for item in uploaded_items
            ],
        )
        assert _tool_names(growth_state) == ["inspect_data", "query_data", "analyze_ab_test"]
        growth_text = json.dumps(growth_state, ensure_ascii=False)
        assert "SHIP WITH MONITORING" in growth_text
        assert "p = 0.0477" in growth_text
        assert "+10.00 pp" in growth_text
        assert "+0.20 to +19.80 pp" in growth_text
        assert "SRM is not detected" in growth_text

    assert not replay_provider.replay_misses()
