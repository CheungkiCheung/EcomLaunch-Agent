"""Build the deterministic OpenSKU Launch + Growth replay fixture.

This utility uses a scripted model once to exercise the real Gateway, agent
graph, tools, uploads, subagents, run budget, and deterministic preflight. The
committed output is consumed by ReplayChatModel in CI, so CI needs no API key.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from starlette.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
TESTS = BACKEND / "tests"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))


def _register(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"opensku-replay-{uuid.uuid4().hex[:8]}@example.com",
            "password": "very-strong-password-123",
        },
    )
    response.raise_for_status()
    csrf = client.cookies.get("csrf_token")
    if not csrf:
        raise RuntimeError("registration did not set csrf_token")
    return csrf


def _create_thread(client: TestClient, csrf: str) -> str:
    thread_id = f"opensku-replay-{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {}},
        headers={"X-CSRF-Token": csrf},
    )
    response.raise_for_status()
    return thread_id


def _run(
    client: TestClient,
    *,
    csrf: str,
    thread_id: str,
    assistant_id: str,
    prompt: str,
    context: dict,
    files: list[dict] | None = None,
) -> None:
    message: dict = {"role": "user", "content": prompt}
    if files:
        message = {
            "type": "human",
            "content": [{"type": "text", "text": prompt}],
            "additional_kwargs": {"files": files},
        }
    body = {
        "assistant_id": assistant_id,
        "input": {"messages": [message]},
        "config": {"recursion_limit": 100},
        "context": context,
        "stream_mode": ["values"],
    }
    with client.stream(
        "POST",
        f"/api/threads/{thread_id}/runs/stream",
        json=body,
        headers={"X-CSRF-Token": csrf},
    ) as response:
        response.raise_for_status()
        location = response.headers.get("content-location", "")
        payload = response.read().decode("utf-8")
    if "event: end" not in payload:
        raise RuntimeError(f"run did not finish cleanly: {payload[-2000:]}")
    if not location:
        raise RuntimeError("run stream response did not include Content-Location")
    run_id = location.rstrip("/").split("/")[-1]
    run = client.get(f"/api/threads/{thread_id}/runs/{run_id}")
    run.raise_for_status()
    status = run.json().get("status")
    if status != "success":
        raise RuntimeError(f"run {run_id} finished with status {status!r}: {payload[-2000:]}")


def main() -> int:
    from _replay_fixture import build_opensku_config_yaml, opensku_growth_csvs, prepare_hermetic_extras
    from opensku_scenario_provider import GROWTH_MARKER, LAUNCH_MARKER, recorded_turns, reset_recorded_turns

    output = TESTS / "fixtures" / "replay" / "opensku_product_flows.json"
    home = Path(tempfile.mkdtemp(prefix="opensku-replay-record-"))
    config_path = home / "config.yaml"
    config_path.write_text(
        build_opensku_config_yaml(
            model_use="opensku_scenario_provider:OpenSKUScenarioModel",
            home=home,
            repo_root=REPO_ROOT,
        ),
        encoding="utf-8",
    )

    os.environ["OPENSKU_HOME"] = str(home)
    os.environ["OPENSKU_CONFIG_PATH"] = str(config_path)
    os.environ["OPENSKU_PROJECT_ROOT"] = str(REPO_ROOT)
    os.environ["OPENSKU_EXTENSIONS_CONFIG_PATH"] = str(prepare_hermetic_extras(home))
    os.environ.setdefault("AUTH_JWT_SECRET", "opensku-replay-fixture-secret-32-bytes")

    reset_recorded_turns()
    from app.gateway.app import create_app

    with TestClient(create_app()) as client:
        csrf = _register(client)

        launch_thread = _create_thread(client, csrf)
        launch_prompt = f"{LAUNCH_MARKER}\n没有样品、没有规格表。请为 99-129 元的通勤随行杯，生成完整 Launch Validation Pack，使用 Ultra 三专家流程，并在确定性 Preflight 失败后只修复被点名的文件。"
        _run(
            client,
            csrf=csrf,
            thread_id=launch_thread,
            assistant_id="ecom-launch",
            prompt=launch_prompt,
            context={
                "mode": "ultra",
                "thinking_enabled": True,
                "is_plan_mode": True,
                "subagent_enabled": True,
            },
        )

        growth_thread = _create_thread(client, csrf)
        files = [("files", (name, content.encode("utf-8"), "text/csv")) for name, content in opensku_growth_csvs().items()]
        upload = client.post(
            f"/api/threads/{growth_thread}/uploads",
            files=files,
            headers={"X-CSRF-Token": csrf},
        )
        upload.raise_for_status()
        uploaded_files = [
            {
                "filename": item["filename"],
                "size": item["size"],
                "path": item["virtual_path"],
                "status": "uploaded",
            }
            for item in upload.json()["files"]
        ]
        growth_prompt = f"{GROWTH_MARKER}\nAnalyze the three uploaded CSV files with a real cross-file join, run the deterministic binary A/B test, and return a ship/extend/stop decision with p-value, confidence interval, and SRM status."
        _run(
            client,
            csrf=csrf,
            thread_id=growth_thread,
            assistant_id="data-inspector",
            prompt=growth_prompt,
            files=uploaded_files,
            context={
                "mode": "flash",
                "thinking_enabled": False,
                "is_plan_mode": False,
                "subagent_enabled": False,
            },
        )

    payload = {
        "scenario": "opensku_product_flows",
        "mode": "mixed",
        "model": "scripted-opensku-scenario",
        "scenarios": {
            "launch": {
                "assistant_id": "ecom-launch",
                "prompt": launch_prompt,
                "context": {
                    "mode": "ultra",
                    "thinking_enabled": True,
                    "is_plan_mode": True,
                    "subagent_enabled": True,
                },
            },
            "growth": {
                "assistant_id": "data-inspector",
                "prompt": growth_prompt,
                "context": {
                    "mode": "flash",
                    "thinking_enabled": False,
                    "is_plan_mode": False,
                    "subagent_enabled": False,
                },
            },
        },
        "turns": recorded_turns(),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(payload['turns'])} turns to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
