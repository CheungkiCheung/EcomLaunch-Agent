from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import run_live_llm_canary as canary


def test_live_canary_skips_safely_without_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENSKU_CANARY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert canary.main(["--output-dir", str(tmp_path)]) == 0

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "status": "skipped",
        "reason": "OPENSKU_CANARY_API_KEY/OPENAI_API_KEY is not configured",
        "profile": "full",
    }


def test_live_canary_config_is_real_bounded_and_offline(tmp_path: Path) -> None:
    config = yaml.safe_load(
        canary._build_live_config(
            home=tmp_path,
            api_key="test-key",
            base_url="https://example.test/v1",
            model="canary-model",
        )
    )

    assert config["models"][0]["use"] == "langchain_openai:ChatOpenAI"
    assert config["models"][0]["model"] == "canary-model"
    assert "replay" not in config["models"][0]["use"].lower()
    assert {tool["name"] for tool in config["tools"]} <= canary.CANARY_TOOLS
    assert config["sandbox"]["allow_host_bash"] is False
    assert config["memory"]["enabled"] is False
    assert config["summarization"]["enabled"] is False
    assert config["title"]["enabled"] is False
    assert all(specialist["tools"] == [] for specialist in config["subagents"]["custom_agents"].values())


def test_live_canary_extracts_tool_results_by_call_id() -> None:
    state = {
        "messages": [
            {
                "type": "ai",
                "content": "",
                "tool_calls": [
                    {"id": "call-1", "name": "present_files", "args": {}},
                ],
            },
            {
                "type": "tool",
                "tool_call_id": "call-1",
                "content": "Successfully presented files",
            },
        ]
    }

    assert canary._tool_results(state) == {"present_files": ["Successfully presented files"]}


def test_live_canary_applies_hard_runtime_budgets(
    tmp_path: Path,
) -> None:
    with patch.dict(
        os.environ,
        {
            "OPENSKU_CANARY_MAX_MODEL_CALLS": "9",
            "OPENSKU_CANARY_MAX_TOTAL_TOKENS": "64000",
            "OPENSKU_CANARY_MAX_EXECUTION_SECONDS": "240",
        },
    ):
        canary._prepare_runtime(
            tmp_path,
            tmp_path / "config.yaml",
            api_key="test-key",
            base_url="https://example.test/v1",
        )

        project_root = Path(os.environ["OPENSKU_PROJECT_ROOT"])
        for agent_name in ("ecom-launch", "openskufast"):
            config = yaml.safe_load(
                (project_root / "agents" / agent_name / "config.yaml").read_text(
                    encoding="utf-8",
                )
            )
            assert config["run_budget"]["max_lead_model_calls"] == 9
            assert config["run_budget"]["max_total_tokens"] == 64000
            assert config["run_budget"]["max_execution_seconds"] == 240
