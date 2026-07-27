"""Runtime-facing deterministic Commerce data Tool contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.commerce.api.data_service import CommerceDataService
from app.commerce.chat.context import CommerceThreadContextService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.tools import data_tools as tool_module

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


class _Runtime:
    def __init__(
        self,
        uploads_dir: Path,
        *,
        user_id: str = "user-1",
        available_tool_names: tuple[str, ...] | None = None,
    ) -> None:
        self.context = {
            "thread_id": "thread-1",
            "run_id": "run-1",
            "user_id": user_id,
        }
        if available_tool_names is not None:
            self.context["available_tool_names"] = available_tool_names
        self.config = {"metadata": {"model_name": "deepseek-reasoner"}}
        self.state = {
            "thread_data": {
                "uploads_path": str(uploads_dir),
            }
        }


async def _invoke(tool, **kwargs):
    coroutine = getattr(tool, "coroutine", None)
    assert coroutine is not None
    return json.loads(await coroutine(**kwargs))


@pytest.fixture
def configured_tools(tmp_path: Path, monkeypatch):
    service = CommerceThreadContextService(data_service=CommerceDataService(storage_root=tmp_path / "commerce-data"))
    monkeypatch.setattr(tool_module, "_build_context_service", lambda: service)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text(
        "order_id,order_purchase_timestamp\no1,2018-01-01T00:00:00\n",
        encoding="utf-8",
    )
    return service, uploads


def _configure_gold_case(
    tmp_path: Path,
    monkeypatch,
    case_key: str,
) -> tuple[CommerceThreadContextService, Path, str]:
    service = CommerceThreadContextService(data_service=CommerceDataService(storage_root=tmp_path / "commerce-data"))
    monkeypatch.setattr(tool_module, "_build_context_service", lambda: service)
    case_dir = CASES_ROOT / case_key
    case = load_evaluation_case(case_dir)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    filenames = []
    for item in case.input_bundle.files:
        source = case_dir / item.relative_path
        target = uploads / source.name
        shutil.copyfile(source, target)
        filenames.append(target.name)
    result = service.ingest_uploads(
        user_id="user-1",
        thread_id="thread-1",
        uploads_dir=uploads,
        filenames=tuple(filenames),
    )
    return service, uploads, str(result.view.manifest.dataset_id)


@pytest.mark.anyio
async def test_ingest_list_and_select_tools_share_runtime_thread_context(configured_tools):
    service, uploads = configured_tools
    runtime = _Runtime(uploads)

    ingested = await _invoke(
        tool_module.commerce_ingest_uploads_tool,
        runtime=runtime,
        filenames=None,
    )
    listed = await _invoke(
        tool_module.commerce_list_datasets_tool,
        runtime=runtime,
        limit=20,
        offset=0,
    )
    selected = await _invoke(
        tool_module.commerce_select_dataset_tool,
        runtime=runtime,
        dataset_id=ingested["dataset_id"],
    )

    assert ingested["ok"] is True
    assert ingested["created"] is True
    assert ingested["selected_filenames"] == ["orders.csv"]
    assert listed["active_dataset_id"] == ingested["dataset_id"]
    assert listed["datasets"][0]["dataset_id"] == ingested["dataset_id"]
    assert selected["active_dataset_id"] == ingested["dataset_id"]
    context = service.resolve(user_id="user-1", thread_id="thread-1")
    assert str(context.active_dataset_id) == ingested["dataset_id"]


@pytest.mark.anyio
async def test_ingest_tool_replays_same_uploaded_content(configured_tools):
    _service, uploads = configured_tools
    runtime = _Runtime(uploads)

    first = await _invoke(
        tool_module.commerce_ingest_uploads_tool,
        runtime=runtime,
        filenames=["orders.csv"],
    )
    replay = await _invoke(
        tool_module.commerce_ingest_uploads_tool,
        runtime=runtime,
        filenames=["orders.csv"],
    )

    assert replay["dataset_id"] == first["dataset_id"]
    assert replay["created"] is False
    assert replay["replayed"] is True


@pytest.mark.anyio
async def test_tools_require_thread_identity_and_thread_data_upload_path(configured_tools):
    _service, uploads = configured_tools
    missing_thread = _Runtime(uploads)
    del missing_thread.context["thread_id"]
    missing_uploads = _Runtime(uploads)
    missing_uploads.state = {}

    with pytest.raises(RuntimeError, match="thread_id"):
        await _invoke(
            tool_module.commerce_list_datasets_tool,
            runtime=missing_thread,
            limit=20,
            offset=0,
        )
    with pytest.raises(RuntimeError, match="uploads_path"):
        await _invoke(
            tool_module.commerce_ingest_uploads_tool,
            runtime=missing_uploads,
            filenames=None,
        )


def test_configured_tool_catalog_exposes_commerce_data_tools(monkeypatch):
    from deerflow.config import get_app_config
    from deerflow.tools import get_available_tools

    monkeypatch.setenv("COMMERCE_CASE_AGENT_ENABLED", "true")
    names = {
        tool.name
        for tool in get_available_tools(
            groups=["commerce"],
            include_mcp=False,
            app_config=get_app_config(),
        )
    }

    assert {
        "commerce_ingest_uploads",
        "commerce_list_datasets",
        "commerce_select_dataset",
        "commerce_dataset_profile",
        "commerce_capabilities",
        "commerce_list_entities",
        "commerce_seller_coverage",
        "commerce_metric_snapshot",
        "commerce_compare_windows",
        "commerce_peer_comparison",
        "commerce_geographic_segments",
        "commerce_evidence_query",
    }.issubset(names)


def test_configured_commerce_tools_fail_closed_when_feature_flag_is_disabled(monkeypatch):
    from deerflow.config import get_app_config
    from deerflow.tools import get_available_tools

    monkeypatch.delenv("COMMERCE_CASE_AGENT_ENABLED", raising=False)

    names = {
        tool.name
        for tool in get_available_tools(
            groups=["commerce"],
            include_mcp=False,
            app_config=get_app_config(),
        )
    }

    assert not {name for name in names if name.startswith("commerce_")}


def test_metric_and_query_tool_schemas_expose_closed_enums_and_numeric_bounds():
    metric_schema = tool_module.commerce_compare_windows_tool.tool_call_schema.model_json_schema()
    evidence_schema = tool_module.commerce_evidence_query_tool.tool_call_schema.model_json_schema()
    geography_schema = tool_module.commerce_geographic_segments_tool.tool_call_schema.model_json_schema()

    metric_items = metric_schema["properties"]["metric_names"]["anyOf"][0]["items"]
    metric_values = set(metric_schema["$defs"][metric_items["$ref"].split("/")[-1]]["enum"])
    assert metric_values == {
        "order_count",
        "late_delivery_rate",
        "handling_time_hours",
        "transit_time_hours",
        "delivery_duration_hours",
        "average_review_score",
        "low_rating_rate",
        "peer_late_delivery_rate",
        "geographic_order_count",
    }
    assert evidence_schema["properties"]["limit"]["minimum"] == 1
    assert evidence_schema["properties"]["limit"]["maximum"] == 100
    assert evidence_schema["properties"]["offset"]["minimum"] == 0
    assert geography_schema["properties"]["limit"]["minimum"] == 1
    assert geography_schema["properties"]["limit"]["maximum"] == 50
    assert geography_schema["properties"]["offset"]["minimum"] == 0
    fact_items = evidence_schema["properties"]["fact_ids"]["anyOf"][0]["items"]
    assert fact_items["pattern"] == r"^fact_[0-9a-f]{32}$"

    window_properties = metric_schema["properties"]
    for name in (
        "baseline_start",
        "baseline_end",
        "current_start",
        "current_end",
    ):
        assert "[start, end)" in window_properties[name]["description"]
    assert "排他边界" in window_properties["baseline_end"]["description"]
    assert "不得减一天" in window_properties["baseline_end"]["description"]
    assert "必须完全相等" in window_properties["current_start"]["description"]


@pytest.mark.anyio
async def test_profile_capability_and_entity_tools_read_active_gold_dataset(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )
    runtime = _Runtime(uploads)

    profile = await _invoke(
        tool_module.commerce_dataset_profile_tool,
        runtime=runtime,
        dataset_id=None,
    )
    capabilities = await _invoke(
        tool_module.commerce_capabilities_tool,
        runtime=runtime,
        dataset_id=None,
    )
    entities = await _invoke(
        tool_module.commerce_list_entities_tool,
        runtime=runtime,
        dataset_id=None,
        entity_type="seller",
        query="4869f7",
        limit=20,
        offset=0,
    )

    assert profile["dataset_id"] == dataset_id
    assert {table["table_name"] for table in profile["tables"]} >= {
        "orders",
        "order_items",
    }
    assert all("example_values" not in column for table in profile["tables"] for column in table["columns"])
    assert "semantic_mapping_summary" in profile
    assert "semantic_mappings" not in profile
    assert len(json.dumps(profile, ensure_ascii=False)) < 7_000
    fulfillment = next(item for item in capabilities["capabilities"] if item["name"] == "fulfillment_diagnosis")
    assert fulfillment["status"] in {"available", "partial"}
    assert entities["entities"][0]["external_key"] == ("4869f7a5dfa277a7dca6462dcf3b52b2")


@pytest.mark.anyio
async def test_seller_coverage_returns_exact_linked_time_range_and_field_coverage(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )
    runtime = _Runtime(uploads)

    coverage = await _invoke(
        tool_module.commerce_seller_coverage_tool,
        runtime=runtime,
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        dataset_id=None,
        top_category_limit=5,
    )

    assert coverage["ok"] is True
    assert coverage["dataset_id"] == dataset_id
    assert coverage["seller_id"] == "4869f7a5dfa277a7dca6462dcf3b52b2"
    assert coverage["order_count"] == 554
    assert coverage["purchase_time_range"] == {
        "min": "2017-12-02T06:32:02Z",
        "max": "2018-05-31T13:19:59Z",
        "observed_count": 554,
        "unknown_count": 0,
    }
    assert coverage["default_recent_windows"] == {
        "strategy": "latest_two_adjacent_equal_windows",
        "window_days": 60,
        "baseline": {
            "start": "2018-02-01T00:00:00Z",
            "end": "2018-04-02T00:00:00Z",
        },
        "current": {
            "start": "2018-04-02T00:00:00Z",
            "end": "2018-06-01T00:00:00Z",
        },
        "semantics": "half_open_[start,end)",
        "selection_reason": ("用户未指定窗口时，默认比较数据中最近两个相邻、等长、不重叠的完整窗口；答案必须披露该默认选择。"),
    }
    assert sum(coverage["order_status_counts"].values()) == 554
    assert coverage["field_coverage"]["order.carrier_handoff_at"]["observed_count"] > 0
    assert coverage["field_coverage"]["order.carrier_handoff_at"]["eligible_count"] == 554
    assert coverage["review_count"] == 549
    assert coverage["top_product_categories"]
    assert len(json.dumps(coverage, ensure_ascii=False)) < 5_000

    coverage_by_entity_id = await _invoke(
        tool_module.commerce_seller_coverage_tool,
        runtime=runtime,
        seller_id=coverage["seller_entity_id"],
        dataset_id=None,
        top_category_limit=5,
    )

    assert coverage_by_entity_id["seller_id"] == coverage["seller_id"]
    assert coverage_by_entity_id["seller_entity_id"] == coverage["seller_entity_id"]
    assert coverage_by_entity_id["order_count"] == coverage["order_count"]
    assert coverage_by_entity_id["default_recent_windows"] == coverage["default_recent_windows"]

    coverage_by_unique_dataset = await _invoke(
        tool_module.commerce_seller_coverage_tool,
        runtime=runtime,
        seller_id=None,
        dataset_id=None,
        top_category_limit=5,
    )

    assert coverage_by_unique_dataset["seller_id"] == coverage["seller_id"]
    assert coverage_by_unique_dataset["seller_entity_id"] == coverage["seller_entity_id"]
    assert coverage_by_unique_dataset["default_recent_windows"] == coverage["default_recent_windows"]


@pytest.mark.anyio
async def test_profile_detail_request_degrades_to_compact_without_read_file(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, _dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )
    runtime = _Runtime(
        uploads,
        available_tool_names=("commerce_dataset_profile",),
    )

    profile = await _invoke(
        tool_module.commerce_dataset_profile_tool,
        runtime=runtime,
        dataset_id=None,
        include_column_details=True,
        include_semantic_mappings=True,
    )

    assert profile["detail_request"]["served"] == "compact"
    assert profile["detail_request"]["reason"] == "read_file_unavailable"
    assert "semantic_mappings" not in profile
    assert all("example_values" not in column for table in profile["tables"] for column in table["columns"])
    assert len(json.dumps(profile, ensure_ascii=False)) < 7_000


@pytest.mark.anyio
async def test_metric_comparison_and_evidence_tools_return_traceable_values(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, _dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )
    runtime = _Runtime(uploads)
    seller_id = "4869f7a5dfa277a7dca6462dcf3b52b2"

    snapshot = await _invoke(
        tool_module.commerce_metric_snapshot_tool,
        runtime=runtime,
        seller_id=seller_id,
        start="2017-12-02T00:00:00",
        end="2018-01-31T00:00:00",
        dataset_id=None,
        metric_names=["order_count", "late_delivery_rate"],
    )
    comparison = await _invoke(
        tool_module.commerce_compare_windows_tool,
        runtime=runtime,
        seller_id=seller_id,
        baseline_start="2017-12-02T00:00:00",
        baseline_end="2018-01-31T00:00:00",
        current_start="2018-01-31T00:00:00",
        current_end="2018-04-01T00:00:00",
        dataset_id=None,
        metric_names=[
            "order_count",
            "late_delivery_rate",
            "handling_time_hours",
            "transit_time_hours",
        ],
    )
    comparison_by_entity_id = await _invoke(
        tool_module.commerce_compare_windows_tool,
        runtime=runtime,
        seller_id=comparison["baseline"]["seller_entity_id"],
        baseline_start="2017-12-02T00:00:00",
        baseline_end="2018-01-31T00:00:00",
        current_start="2018-01-31T00:00:00",
        current_end="2018-04-01T00:00:00",
        dataset_id=None,
        metric_names=[
            "order_count",
            "late_delivery_rate",
            "handling_time_hours",
            "transit_time_hours",
        ],
    )
    late_rate = next(item for item in snapshot["observations"] if item["metric_name"] == "late_delivery_rate")
    evidence = await _invoke(
        tool_module.commerce_evidence_query_tool,
        runtime=runtime,
        dataset_id=None,
        fact_ids=late_rate["source_fact_ids"][:4],
        entity_type=None,
        external_key=None,
        semantic_fields=None,
        limit=20,
        offset=0,
    )

    order_count = next(item for item in snapshot["observations"] if item["metric_name"] == "order_count")
    assert order_count["value"] == 141
    assert late_rate["source_fact_ids"]
    assert comparison["baseline"]["observations"][0]["metric_name"] == "order_count"
    assert comparison["current"]["observations"][0]["value"] == 202
    assert comparison_by_entity_id["seller_id"] == seller_id
    assert comparison_by_entity_id["deltas"] == comparison["deltas"]
    assert len(json.dumps(comparison, ensure_ascii=False)) < 6_500
    assert evidence["facts"]
    assert all(item["source"] for item in evidence["facts"])


@pytest.mark.anyio
async def test_peer_and_geographic_tools_preserve_deterministic_cohort_policy(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, _dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-PEER-004",
    )
    runtime = _Runtime(uploads)
    seller_id = "e5a3438891c0bfdb9394643f95273d8e"

    peers = await _invoke(
        tool_module.commerce_peer_comparison_tool,
        runtime=runtime,
        seller_id=seller_id,
        start="2018-01-01T00:00:00",
        end="2018-07-01T00:00:00",
        product_category="fashion_bolsas_e_acessorios",
        min_orders_per_seller=20,
        match_seller_state=True,
        dataset_id=None,
    )
    geography = await _invoke(
        tool_module.commerce_geographic_segments_tool,
        runtime=runtime,
        seller_id=seller_id,
        start="2018-01-01T00:00:00",
        end="2018-07-01T00:00:00",
        dataset_id=None,
        limit=10,
        offset=0,
    )

    assert len(peers["comparison"]["peers"]) == 5
    assert peers["comparison"]["target"]["eligible_order_count"] == 59
    assert peers["comparison"]["late_delivery_rate_gap"]
    assert geography["total_order_count"] == 59
    assert next(item for item in geography["segments"] if item["customer_state"] == "SP")["observation"]["value"] == 26
    assert next(item for item in geography["segments"] if item["customer_state"] == "MG")["observation"]["value"] == 8
    assert next(item for item in geography["segments"] if item["customer_state"] == "RJ")["observation"]["value"] == 7
    assert all(len(item["observation"]["source_fact_ids"]) <= 6 for item in geography["segments"])
    assert geography["returned_segment_count"] == len(geography["segments"])
    assert geography["returned_order_count"] + geography["unreturned_order_count"] == 59
    assert len(json.dumps(geography, ensure_ascii=False)) < 7_000


@pytest.mark.anyio
async def test_geographic_tool_pages_large_segment_sets_without_losing_totals(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, _dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )
    runtime = _Runtime(uploads)

    geography = await _invoke(
        tool_module.commerce_geographic_segments_tool,
        runtime=runtime,
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        start="2017-12-02T00:00:00",
        end="2018-04-01T00:00:00",
        dataset_id=None,
        limit=8,
        offset=0,
    )

    values = [int(item["observation"]["value"]) for item in geography["segments"]]
    assert values == sorted(values, reverse=True)
    assert geography["returned_segment_count"] == 8
    assert geography["total_segment_count"] > geography["returned_segment_count"]
    assert geography["has_more"] is True
    assert geography["returned_order_count"] + geography["unreturned_order_count"] == geography["total_order_count"]
    assert len(json.dumps(geography, ensure_ascii=False)) < 6_000


@pytest.mark.anyio
async def test_peer_tool_returns_explicit_unavailable_result_when_no_cohort_exists(
    tmp_path: Path,
    monkeypatch,
):
    _service, uploads, dataset_id = _configure_gold_case(
        tmp_path,
        monkeypatch,
        "GC-FULFILLMENT-001",
    )

    result = await _invoke(
        tool_module.commerce_peer_comparison_tool,
        runtime=_Runtime(uploads),
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        start="2017-12-02T00:00:00",
        end="2018-04-01T00:00:00",
        product_category="relogios_presentes",
        min_orders_per_seller=20,
        match_seller_state=True,
        dataset_id=None,
    )

    assert result == {
        "ok": True,
        "dataset_id": dataset_id,
        "workspace_id": result["workspace_id"],
        "status": "unavailable",
        "comparison": None,
        "unknown_reason": "No eligible peer sellers remain after deterministic cohort filters",
        "causal_interpretation": "not_identified",
    }
