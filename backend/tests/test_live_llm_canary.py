from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import yaml
from langchain_core.messages import HumanMessage

from deerflow.agents.middlewares.run_budget_middleware import RunBudgetMiddleware
from deerflow.config.agent_run_budget_config import AgentRunBudgetConfig
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
    assert all(specialist["model"] == "opensku-live-canary" for specialist in config["subagents"]["custom_agents"].values())


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


def test_live_canary_accepts_renderer_preflight_result() -> None:
    result = {
        "tool_names": ["task", "task", "task", "render_launch_pack"],
        "artifacts": sorted(canary.PACK_FILES),
        "tool_results": {"render_launch_pack": ["Successfully presented files"]},
        "llm_call_count": 6,
        "total_tokens": 100,
    }

    canary._assert_ultra(result)


def test_live_canary_flash_prompt_is_direct_answer_shape() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=4,
            max_subagent_calls=0,
            max_total_tokens=10_000,
            max_execution_seconds=30,
            direct_answer_patterns=[
                r"(?:what|which).{0,40}(?:first|priority|hypothesis|risk)"
            ],
            direct_answer_exclude_patterns=[r"Launch Validation Pack"],
        )
    )

    assert middleware._is_direct_answer_request([HumanMessage(content=canary.FLASH_PROMPT)])


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
