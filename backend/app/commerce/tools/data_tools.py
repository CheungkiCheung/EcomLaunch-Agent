"""Parent/Subagent-facing deterministic Commerce data context Tools."""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from langchain.tools import tool
from pydantic import Field

from app.commerce.api.data_service import CommerceDataService, DatasetView
from app.commerce.chat.context import CommerceThreadContextService
from app.commerce.data.normalized import EntityType, NormalizedDataset
from app.commerce.data.semantic_mapper import SemanticField
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import DatasetId, FactId
from app.commerce.metrics.registry import (
    MetricEngine,
    MetricName,
    MetricSnapshot,
    MetricWindow,
    PeerCohortPolicy,
    PeerCohortUnavailableError,
)
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime

_SOURCE_FACT_PREVIEW_LIMIT = 4
_DEFAULT_RECENT_WINDOW_DAYS = 60
FactIdInput = Annotated[str, Field(pattern=r"^fact_[0-9a-f]{32}$")]


def _build_context_service() -> CommerceThreadContextService:
    storage_root = Path(os.getenv("COMMERCE_STORAGE_ROOT", ".deer-flow/commerce/data"))
    context_root_value = os.getenv("COMMERCE_THREAD_CONTEXT_ROOT")
    return CommerceThreadContextService(
        data_service=CommerceDataService(storage_root=storage_root),
        context_root=Path(context_root_value) if context_root_value else None,
    )


def _thread_identity(runtime: Runtime) -> tuple[str, str]:
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        raise RuntimeError("Commerce ToolRuntime 缺少运行上下文")
    thread_id = str(context.get("thread_id") or "").strip()
    if not thread_id:
        raise RuntimeError("Commerce ToolRuntime 缺少 thread_id")
    return resolve_runtime_user_id(runtime), thread_id


def _runtime_can_read_externalized_results(runtime: Runtime) -> bool:
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        return True
    available = context.get("available_tool_names")
    if available is None:
        return True
    return bool({"read_file", "read_file_tool"}.intersection(available))


def _uploads_dir(runtime: Runtime) -> Path:
    state = getattr(runtime, "state", None)
    thread_data = state.get("thread_data") if isinstance(state, dict) else None
    uploads_path = thread_data.get("uploads_path") if isinstance(thread_data, dict) else None
    if not uploads_path:
        raise RuntimeError("Commerce ToolRuntime 缺少 thread_data.uploads_path；请先通过线程上传文件")
    return Path(str(uploads_path))


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _capability_summary(view: DatasetView) -> list[dict[str, Any]]:
    return [
        {
            "name": capability.name.value,
            "status": capability.status.value,
            "reason_codes": sorted(reason.value for reason in capability.reason_codes),
            "missing_required_fields": sorted(field.value for field in capability.missing_required_fields),
            "missing_optional_fields": sorted(field.value for field in capability.missing_optional_fields),
        }
        for capability in view.capabilities.capabilities
    ]


def _dataset_summary(view: DatasetView) -> dict[str, Any]:
    return {
        "dataset_id": str(view.manifest.dataset_id),
        "workspace_id": str(view.manifest.workspace_id),
        "created_at": view.manifest.created_at.isoformat(),
        "filenames": [file.original_name for file in view.manifest.files if file.parent_source_id is None],
        "tables": [
            {
                "table_name": table.table_name,
                "row_count": table.row_count,
                "column_count": table.column_count,
            }
            for table in view.profile.tables
        ],
        "capabilities": _capability_summary(view),
        "warnings": list(view.manifest.warnings),
    }


def _compact_profile_payload(view: DatasetView) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    confirmed_fields: list[str] = []
    needs_confirmation: list[dict[str, str]] = []
    for mapping in view.mappings.mappings:
        status = mapping.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "confirmed":
            confirmed_fields.append(mapping.semantic_field.value)
        elif status == "needs_confirmation":
            needs_confirmation.append(
                {
                    "table_name": mapping.table_name,
                    "column_name": mapping.column_name,
                    "candidate_semantic_field": mapping.semantic_field.value,
                }
            )
    return {
        "schema_version": view.profile.schema_version,
        "dataset_id": str(view.profile.dataset_id),
        "workspace_id": str(view.profile.workspace_id),
        "tables": [
            {
                "table_name": table.table_name,
                "row_count": table.row_count,
                "column_count": table.column_count,
                "duplicate_row_rate": table.duplicate_row_rate,
                "primary_key_candidates": list(table.primary_key_candidates),
                "time_candidates": list(table.time_candidates),
                "columns": [
                    {
                        "name": column.name,
                        "inferred_type": column.inferred_type.value,
                    }
                    for column in table.columns
                ],
                "columns_with_missing_values": [
                    {
                        "name": column.name,
                        "missing_rate": column.missing_rate,
                    }
                    for column in table.columns
                    if column.missing_rate > 0
                ],
            }
            for table in view.profile.tables
        ],
        "join_risks": [risk.model_dump(mode="json") for risk in view.profile.join_risks],
        "semantic_mapping_summary": {
            "status_counts": status_counts,
            "confirmed_fields": sorted(set(confirmed_fields)),
            "needs_confirmation": needs_confirmation,
        },
    }


def _resolve_view(
    service: CommerceThreadContextService,
    *,
    user_id: str,
    thread_id: str,
    dataset_id: str | None,
) -> DatasetView:
    context = service.resolve(user_id=user_id, thread_id=thread_id)
    selected = DatasetId(dataset_id) if dataset_id is not None else context.active_dataset_id
    if selected is None:
        raise ValueError("当前 Chat 尚未选择 Commerce Dataset；请先调用 commerce_ingest_uploads 或 commerce_select_dataset")
    return service.data_service.get_view(context.workspace_id, selected)


def _resolve_normalized(
    service: CommerceThreadContextService,
    *,
    user_id: str,
    thread_id: str,
    dataset_id: str | None,
) -> tuple[DatasetView, NormalizedDataset]:
    view = _resolve_view(
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    normalized = service.data_service.normalize(
        view.manifest.workspace_id,
        view.manifest.dataset_id,
    )
    return view, normalized


def _metric_window(start: str, end: str) -> MetricWindow:
    try:
        return MetricWindow(
            start=datetime.fromisoformat(start.replace("Z", "+00:00")),
            end=datetime.fromisoformat(end.replace("Z", "+00:00")),
        )
    except ValueError as exc:
        raise ValueError("指标窗口必须使用有效 ISO-8601 时间，且 start 早于 end") from exc


def _metric_names(
    values: list[MetricName | str] | None,
) -> tuple[MetricName, ...] | None:
    if values is None:
        return None
    if not values:
        raise ValueError("metric_names 不能为空列表")
    parsed = tuple(MetricName(value) for value in values)
    if len(parsed) != len(set(parsed)):
        raise ValueError("metric_names 不能重复")
    return parsed


def _resolve_seller_external_key(
    normalized: NormalizedDataset,
    seller_reference: str | None,
) -> str:
    """Resolve either a normalized Entity ID or an external seller key.

    ``commerce_list_entities`` intentionally exposes both identifiers. Models
    and callers should prefer ``external_key`` for business Tools, but accepting
    the stable internal ``ent_...`` ID here keeps that representation detail
    from turning into a failed investigation or a retry loop.
    """

    sellers = normalized.entities_of_type(EntityType.SELLER)
    if seller_reference is None:
        if len(sellers) == 1:
            return sellers[0].external_key
        if not sellers:
            raise ValueError("Dataset 中没有可识别的卖家实体")
        raise ValueError(
            f"Dataset 中存在 {len(sellers)} 个卖家；请先调用 commerce_list_entities 选择目标卖家"
        )

    reference = seller_reference.strip()
    if not reference:
        raise ValueError("seller_id 不能为空")
    seller = next(
        (
            entity
            for entity in sellers
            if entity.external_key == reference or str(entity.id) == reference
        ),
        None,
    )
    if seller is None:
        raise ValueError(f"Dataset 中不存在 seller_id 或 seller_entity_id={reference}")
    return seller.external_key


def _observation_payload(observation) -> dict[str, Any]:
    serialized = observation.model_dump(mode="json")
    source_fact_ids = list(serialized["source_fact_ids"])
    return {
        "id": serialized["id"],
        "metric_name": serialized["metric_name"],
        "semantic_status": serialized["semantic_status"],
        "value": serialized["value"],
        "unit": serialized["unit"],
        "formula_version": serialized["formula_version"],
        "sample_size": serialized["sample_size"],
        "numerator": serialized["numerator"],
        "denominator": serialized["denominator"],
        "unknown_reason": serialized["unknown_reason"],
        "source_fact_count": len(source_fact_ids),
        "source_fact_ids_truncated": (len(source_fact_ids) > _SOURCE_FACT_PREVIEW_LIMIT),
        "source_fact_ids": source_fact_ids[:_SOURCE_FACT_PREVIEW_LIMIT],
    }


def _snapshot_payload(snapshot: MetricSnapshot) -> dict[str, Any]:
    return {
        "seller_id": snapshot.seller_id,
        "seller_entity_id": str(snapshot.seller_entity_id),
        "window": snapshot.window.model_dump(mode="json"),
        "observations": [_observation_payload(observation) for observation in snapshot.observations],
    }


def _filter_snapshot(
    snapshot: MetricSnapshot,
    names: tuple[MetricName, ...] | None,
) -> MetricSnapshot:
    if names is None:
        return snapshot
    selected = set(names)
    return snapshot.model_copy(update={"observations": tuple(observation for observation in snapshot.observations if MetricName(observation.metric_name) in selected)})


def _seller_coverage_payload(
    normalized: NormalizedDataset,
    *,
    seller_id: str | None,
    top_category_limit: int,
) -> dict[str, Any]:
    seller_id = _resolve_seller_external_key(normalized, seller_id)
    facts_by_entity: dict[Any, dict[str, Any]] = defaultdict(dict)
    for fact in normalized.facts:
        if fact.entity_id is not None:
            facts_by_entity[fact.entity_id][fact.name] = fact

    def observed(facts: dict[str, Any], field: SemanticField):
        fact = facts.get(field.value)
        if fact is None or fact.semantic_status is not SemanticStatus.OBSERVED or fact.value is None:
            return None
        return fact

    seller_entity = next(
        (entity for entity in normalized.entities_of_type(EntityType.SELLER) if entity.external_key == seller_id),
        None,
    )
    linked_order_ids: set[str] = set()
    linked_product_ids: list[str] = []
    source_fact_ids: list[str] = []
    linked_item_count = 0
    for entity in normalized.entities_of_type(EntityType.ORDER_ITEM):
        facts = facts_by_entity[entity.id]
        seller = observed(facts, SemanticField.SELLER_ID)
        order = observed(facts, SemanticField.ORDER_ITEM_ORDER_ID)
        if seller is None or order is None or str(seller.value) != seller_id:
            continue
        linked_item_count += 1
        linked_order_ids.add(str(order.value))
        source_fact_ids.extend((str(seller.id), str(order.id)))
        product = observed(facts, SemanticField.PRODUCT_ID)
        if product is not None:
            linked_product_ids.append(str(product.value))
            source_fact_ids.append(str(product.id))

    if not linked_order_ids:
        raise ValueError(f"Dataset 中不存在 seller_id={seller_id} 的关联订单")

    linked_orders = [entity for entity in normalized.entities_of_type(EntityType.ORDER) if entity.external_key in linked_order_ids]
    linked_orders.sort(key=lambda entity: entity.external_key)
    resolved_order_ids = {entity.external_key for entity in linked_orders}

    purchase_values: list[datetime] = []
    status_counts: Counter[str] = Counter()
    coverage_fields = (
        SemanticField.PURCHASED_AT,
        SemanticField.APPROVED_AT,
        SemanticField.CARRIER_HANDOFF_AT,
        SemanticField.DELIVERED_AT,
        SemanticField.ESTIMATED_DELIVERY_AT,
    )
    field_observed_counts: Counter[str] = Counter()
    for entity in linked_orders:
        facts = facts_by_entity[entity.id]
        purchase = observed(facts, SemanticField.PURCHASED_AT)
        if purchase is not None and isinstance(purchase.value, datetime):
            purchase_values.append(purchase.value)
            source_fact_ids.append(str(purchase.id))
        status = observed(facts, SemanticField.ORDER_STATUS)
        if status is not None:
            status_counts[str(status.value)] += 1
            source_fact_ids.append(str(status.id))
        for field in coverage_fields:
            fact = observed(facts, field)
            if fact is not None:
                field_observed_counts[field.value] += 1

    product_categories: dict[str, str] = {}
    for entity in normalized.entities_of_type(EntityType.PRODUCT):
        category = observed(
            facts_by_entity[entity.id],
            SemanticField.PRODUCT_CATEGORY,
        )
        if category is not None:
            product_categories[entity.external_key] = str(category.value)
    category_counts = Counter(product_categories[product_id] for product_id in linked_product_ids if product_id in product_categories)

    review_count = 0
    review_score_observed_count = 0
    for entity in normalized.entities_of_type(EntityType.REVIEW):
        facts = facts_by_entity[entity.id]
        order = observed(facts, SemanticField.REVIEW_ORDER_ID)
        if order is None or str(order.value) not in linked_order_ids:
            continue
        review_count += 1
        if observed(facts, SemanticField.REVIEW_SCORE) is not None:
            review_score_observed_count += 1

    def iso_z(value: datetime) -> str:
        normalized_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return normalized_value.isoformat().replace("+00:00", "Z")

    def default_recent_windows() -> dict[str, Any] | None:
        """Return two deterministic adjacent windows for a natural 'recent' query."""
        if not purchase_values:
            return None
        coverage_start = min(purchase_values)
        latest_purchase = max(purchase_values)
        latest_utc = latest_purchase.replace(tzinfo=UTC) if latest_purchase.tzinfo is None else latest_purchase.astimezone(UTC)
        coverage_start_utc = coverage_start.replace(tzinfo=UTC) if coverage_start.tzinfo is None else coverage_start.astimezone(UTC)
        current_end = datetime.combine(
            latest_utc.date() + timedelta(days=1),
            time.min,
            tzinfo=UTC,
        )
        available_days = max(
            1,
            int((current_end - coverage_start_utc).total_seconds() // 86400),
        )
        window_days = min(
            _DEFAULT_RECENT_WINDOW_DAYS,
            max(1, available_days // 2),
        )
        duration = timedelta(days=window_days)
        current_start = current_end - duration
        baseline_end = current_start
        baseline_start = baseline_end - duration
        return {
            "strategy": "latest_two_adjacent_equal_windows",
            "window_days": window_days,
            "baseline": {
                "start": iso_z(baseline_start),
                "end": iso_z(baseline_end),
            },
            "current": {
                "start": iso_z(current_start),
                "end": iso_z(current_end),
            },
            "semantics": "half_open_[start,end)",
            "selection_reason": ("用户未指定窗口时，默认比较数据中最近两个相邻、等长、不重叠的完整窗口；答案必须披露该默认选择。"),
        }

    eligible_count = len(linked_orders)
    return {
        "seller_id": seller_id,
        "seller_entity_id": str(seller_entity.id) if seller_entity else None,
        "order_count": eligible_count,
        "linked_order_id_count": len(linked_order_ids),
        "unresolved_order_id_count": len(linked_order_ids - resolved_order_ids),
        "order_item_count": linked_item_count,
        "purchase_time_range": {
            "min": iso_z(min(purchase_values)) if purchase_values else None,
            "max": iso_z(max(purchase_values)) if purchase_values else None,
            "observed_count": len(purchase_values),
            "unknown_count": eligible_count - len(purchase_values),
        },
        "default_recent_windows": default_recent_windows(),
        "order_status_counts": dict(sorted(status_counts.items())),
        "field_coverage": {
            field.value: {
                "eligible_count": eligible_count,
                "observed_count": field_observed_counts[field.value],
                "unknown_count": (eligible_count - field_observed_counts[field.value]),
                "observed_rate": (str(Decimal(field_observed_counts[field.value]) / Decimal(eligible_count)) if eligible_count else None),
            }
            for field in coverage_fields
        },
        "product_count": len(set(linked_product_ids)),
        "top_product_categories": [
            {"category": category, "order_item_count": count}
            for category, count in sorted(
                category_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:top_category_limit]
        ],
        "review_count": review_count,
        "review_score_observed_count": review_score_observed_count,
        "source_fact_count": len(set(source_fact_ids)),
        "source_fact_ids_truncated": len(set(source_fact_ids)) > _SOURCE_FACT_PREVIEW_LIMIT,
        "source_fact_ids": sorted(set(source_fact_ids))[:_SOURCE_FACT_PREVIEW_LIMIT],
    }


def _compute_snapshot(
    service: CommerceThreadContextService,
    *,
    user_id: str,
    thread_id: str,
    dataset_id: str | None,
    seller_id: str,
    start: str,
    end: str,
    metric_names: list[MetricName | str] | None,
) -> tuple[DatasetView, MetricSnapshot]:
    view, normalized = _resolve_normalized(
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    seller_id = _resolve_seller_external_key(normalized, seller_id)
    snapshot = MetricEngine().compute_seller_window(
        normalized,
        seller_id=seller_id,
        window=_metric_window(start, end),
    )
    return view, _filter_snapshot(snapshot, _metric_names(metric_names))


def _metric_delta(baseline, current) -> dict[str, Any]:
    if baseline.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED} or current.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED} or baseline.value is None or current.value is None:
        return {
            "metric_name": baseline.metric_name,
            "status": "unknown",
            "absolute_change": None,
            "relative_change": None,
            "reason": baseline.unknown_reason or current.unknown_reason,
        }
    baseline_value = Decimal(str(baseline.value))
    current_value = Decimal(str(current.value))
    absolute = current_value - baseline_value
    relative = absolute / baseline_value if baseline_value != 0 else None
    return {
        "metric_name": baseline.metric_name,
        "status": "derived",
        "absolute_change": str(absolute),
        "relative_change": str(relative) if relative is not None else None,
        "baseline_observation_id": str(baseline.id),
        "current_observation_id": str(current.id),
    }


@tool("commerce_ingest_uploads", parse_docstring=True)
async def commerce_ingest_uploads_tool(
    runtime: Runtime,
    filenames: list[str] | None = None,
) -> str:
    """将当前 Chat 线程中上传的经营数据安全、幂等地接入 Commerce Dataset。

    默认自动选择 CSV、JSON、JSONL、XLSX、ZIP；同一组文件内容重复调用会复用
    已有 Dataset。该 Tool 只摄取和分析结构，不会调用模型或修改外部业务系统。

    Args:
        filenames: 可选的上传文件名列表；省略时自动选择当前线程内全部支持格式。
    """
    user_id, thread_id = _thread_identity(runtime)
    uploads_dir = _uploads_dir(runtime)
    service = _build_context_service()
    result = await asyncio.to_thread(
        service.ingest_uploads,
        user_id=user_id,
        thread_id=thread_id,
        uploads_dir=uploads_dir,
        filenames=tuple(filenames) if filenames is not None else None,
    )
    return _json(
        {
            "ok": True,
            "message": ("上传数据已接入并设为当前数据集" if result.created else "上传内容未变化，已复用原数据集并保持为当前数据集"),
            **_dataset_summary(result.view),
            "active_dataset_id": str(result.context.active_dataset_id),
            "selected_filenames": list(result.selected_filenames),
            "ignored_filenames": list(result.ignored_filenames),
            "upload_fingerprint": result.upload_fingerprint,
            "created": result.created,
            "replayed": result.replayed,
        }
    )


@tool("commerce_list_datasets", parse_docstring=True)
async def commerce_list_datasets_tool(
    runtime: Runtime,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> str:
    """列出当前用户与 Chat 线程隔离范围内的 Commerce Dataset。

    Args:
        limit: 返回数量，必须大于零。
        offset: 跳过的数据集数量，不能为负数。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    context = await asyncio.to_thread(
        service.resolve,
        user_id=user_id,
        thread_id=thread_id,
    )
    views = await asyncio.to_thread(
        service.list_datasets,
        user_id=user_id,
        thread_id=thread_id,
        limit=limit,
        offset=offset,
    )
    return _json(
        {
            "ok": True,
            "workspace_id": str(context.workspace_id),
            "active_dataset_id": (str(context.active_dataset_id) if context.active_dataset_id is not None else None),
            "datasets": [_dataset_summary(view) for view in views],
            "limit": limit,
            "offset": offset,
        }
    )


@tool("commerce_select_dataset", parse_docstring=True)
async def commerce_select_dataset_tool(
    runtime: Runtime,
    dataset_id: str,
) -> str:
    """选择当前 Chat 后续诊断应使用的已有 Commerce Dataset。

    只能选择当前用户与线程 Workspace 内的数据集，跨 Workspace 访问会失败。

    Args:
        dataset_id: commerce_list_datasets 返回的 dset_ 前缀数据集 ID。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    selected = await asyncio.to_thread(
        service.select_dataset,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=DatasetId(dataset_id),
    )
    return _json(
        {
            "ok": True,
            "message": "已切换当前 Commerce Dataset",
            "workspace_id": str(selected.workspace_id),
            "active_dataset_id": str(selected.active_dataset_id),
            "revision": selected.revision,
        }
    )


@tool("commerce_dataset_profile", parse_docstring=True)
async def commerce_dataset_profile_tool(
    runtime: Runtime,
    dataset_id: str | None = None,
    include_column_details: bool = False,
    include_semantic_mappings: bool = False,
) -> str:
    """读取当前或指定 Commerce Dataset 的确定性 Schema 与数据质量 Profile。

    Args:
        dataset_id: 可选 Dataset ID；省略时使用当前 Chat 选中的 Dataset。
        include_column_details: 是否返回示例值、数值范围等完整列 Profile；默认 false 以节省上下文。
        include_semantic_mappings: 是否返回全部语义映射明细；默认 false，仅返回状态摘要。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    view = await asyncio.to_thread(
        _resolve_view,
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    can_read_externalized = _runtime_can_read_externalized_results(runtime)
    detail_degraded = (include_column_details or include_semantic_mappings) and not can_read_externalized
    payload = view.profile.model_dump(mode="json") if include_column_details and can_read_externalized else _compact_profile_payload(view)
    payload.update(
        {
            "ok": True,
            "filenames": [item.original_name for item in view.manifest.files if item.parent_source_id is None],
            "warnings": list(view.manifest.warnings),
        }
    )
    if detail_degraded:
        payload["detail_request"] = {
            "requested_column_details": include_column_details,
            "requested_semantic_mappings": include_semantic_mappings,
            "served": "compact",
            "reason": "read_file_unavailable",
            "message": "当前 Subagent 无 read_file 权限；返回可完整消费的紧凑 Profile，避免生成不可读取的大结果引用。",
        }
    if include_semantic_mappings and can_read_externalized:
        payload["semantic_mappings"] = view.mappings.model_dump(mode="json")["mappings"]
    return _json(payload)


@tool("commerce_capabilities", parse_docstring=True)
async def commerce_capabilities_tool(
    runtime: Runtime,
    dataset_id: str | None = None,
) -> str:
    """检查当前或指定 Dataset 能可靠支持哪些 Commerce 诊断能力。

    unavailable/partial 必须按缺失字段与原因解释，不能把缺失数据当作零值。

    Args:
        dataset_id: 可选 Dataset ID；省略时使用当前 Chat 选中的 Dataset。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    view = await asyncio.to_thread(
        _resolve_view,
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    payload = view.capabilities.model_dump(mode="json")
    payload["ok"] = True
    return _json(payload)


@tool("commerce_list_entities", parse_docstring=True)
async def commerce_list_entities_tool(
    runtime: Runtime,
    dataset_id: str | None = None,
    entity_type: EntityType | None = None,
    query: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> str:
    """列出 Dataset 中可用于诊断的订单、卖家、商品、评价等规范化实体。

    Args:
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        entity_type: 可选 order/order_item/review/product/customer/seller。
        query: 可选外部业务键模糊查询。
        limit: 返回数量，范围 1 到 100；默认 20，使用 offset 分页。
        offset: 跳过数量，不能为负数。
    """
    if limit < 1 or limit > 100 or offset < 0:
        raise ValueError("limit 必须在 1 到 100 之间，offset 不能为负数")
    parsed_type = EntityType(entity_type) if entity_type is not None else None
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    view, normalized = await asyncio.to_thread(
        _resolve_normalized,
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    needle = query.strip().casefold() if query else None
    candidates = [entity for entity in normalized.entities if (parsed_type is None or entity.entity_type is parsed_type) and (needle is None or needle in entity.external_key.casefold())]
    candidates.sort(
        key=lambda item: (
            item.entity_type.value,
            item.external_key,
            str(item.id),
        )
    )
    page = candidates[offset : offset + limit]
    return _json(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "total_matching": len(candidates),
            "limit": limit,
            "offset": offset,
            "entities": [entity.model_dump(mode="json") for entity in page],
        }
    )


@tool("commerce_seller_coverage", parse_docstring=True)
async def commerce_seller_coverage_tool(
    runtime: Runtime,
    seller_id: str | None = None,
    dataset_id: str | None = None,
    top_category_limit: Annotated[int, Field(ge=1, le=20)] = 5,
) -> str:
    """精确汇总一个卖家的关联订单覆盖、时间范围、状态和关键字段完整度。

    该 Tool 使用完整规范化关联，不做抽样。它适合在窗口比较前确认卖家的精确
    最早/最晚下单时间、订单量和 carrier handoff 等字段覆盖；不得用
    ``commerce_evidence_query`` 的抽样结果替代本 Tool 的全量覆盖结论。

    Args:
        seller_id: 可选目标卖家外部业务键或规范化 ``ent_...`` 实体 ID；
            省略时仅在 Dataset 恰好有一个卖家时自动选择，否则要求先列出候选。
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        top_category_limit: 返回的商品类目数量，范围 1 到 20，默认 5。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()

    def compute():
        view, normalized = _resolve_normalized(
            service,
            user_id=user_id,
            thread_id=thread_id,
            dataset_id=dataset_id,
        )
        return view, _seller_coverage_payload(
            normalized,
            seller_id=seller_id,
            top_category_limit=top_category_limit,
        )

    view, payload = await asyncio.to_thread(compute)
    payload.update(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "coverage_semantics": "full_linked_dataset",
        }
    )
    return _json(payload)


@tool("commerce_metric_snapshot", parse_docstring=True)
async def commerce_metric_snapshot_tool(
    runtime: Runtime,
    seller_id: str,
    start: str,
    end: str,
    dataset_id: str | None = None,
    metric_names: list[MetricName] | None = None,
) -> str:
    """确定性计算一个卖家在指定半开时间窗口内的经营指标快照。

    Args:
        seller_id: Dataset 中的卖家外部业务键或规范化 ``ent_...`` 实体 ID。
        start: ISO-8601 窗口开始时间（包含）。
        end: ISO-8601 窗口结束时间（不包含）。
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        metric_names: 可选指标枚举；只允许 order_count、late_delivery_rate、
            handling_time_hours、transit_time_hours、delivery_duration_hours、
            average_review_score、low_rating_rate、peer_late_delivery_rate、
            geographic_order_count。拿不准时省略，Tool 会返回全部。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    view, snapshot = await asyncio.to_thread(
        _compute_snapshot,
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
        seller_id=seller_id,
        start=start,
        end=end,
        metric_names=metric_names,
    )
    payload = _snapshot_payload(snapshot)
    payload.update(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
        }
    )
    return _json(payload)


@tool("commerce_compare_windows", parse_docstring=True)
async def commerce_compare_windows_tool(
    runtime: Runtime,
    seller_id: str,
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str,
    dataset_id: str | None = None,
    metric_names: list[MetricName] | None = None,
) -> str:
    """确定性比较同一卖家的基线窗口与当前窗口，并返回可追溯变化量。

    Args:
        seller_id: Dataset 中的卖家外部业务键或规范化 ``ent_...`` 实体 ID。
        baseline_start: ISO-8601 基线窗口开始时间；窗口统一使用半开区间
            [start, end)，该时刻包含在窗口内。
        baseline_end: ISO-8601 基线窗口结束时间；窗口统一使用半开区间
            [start, end)，这是排他边界，不包含该时刻。相邻窗口时不得减一天、
            加一天或改成当日最后一秒。
        current_start: ISO-8601 当前窗口开始时间；窗口统一使用半开区间
            [start, end)，该时刻包含在窗口内。相邻窗口必须完全相等于
            baseline_end。
        current_end: ISO-8601 当前窗口结束时间；窗口统一使用半开区间
            [start, end)，这是排他边界，不包含该时刻。
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        metric_names: 可选指标枚举；只允许 order_count、late_delivery_rate、
            handling_time_hours、transit_time_hours、delivery_duration_hours、
            average_review_score、low_rating_rate、peer_late_delivery_rate、
            geographic_order_count。不要创造同义词；拿不准时省略。
    """
    baseline_window = _metric_window(baseline_start, baseline_end)
    current_window = _metric_window(current_start, current_end)
    if baseline_window.end > current_window.start:
        raise ValueError("基线窗口结束时间不能晚于当前窗口开始时间")
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()

    def compute():
        view, normalized = _resolve_normalized(
            service,
            user_id=user_id,
            thread_id=thread_id,
            dataset_id=dataset_id,
        )
        engine = MetricEngine()
        names = _metric_names(metric_names)
        resolved_seller_id = _resolve_seller_external_key(
            normalized,
            seller_id,
        )
        baseline = _filter_snapshot(
            engine.compute_seller_window(
                normalized,
                seller_id=resolved_seller_id,
                window=baseline_window,
            ),
            names,
        )
        current = _filter_snapshot(
            engine.compute_seller_window(
                normalized,
                seller_id=resolved_seller_id,
                window=current_window,
            ),
            names,
        )
        current_by_name = {item.metric_name: item for item in current.observations}
        deltas = [_metric_delta(item, current_by_name[item.metric_name]) for item in baseline.observations]
        return view, baseline, current, deltas, resolved_seller_id

    view, baseline, current, deltas, resolved_seller_id = await asyncio.to_thread(compute)
    return _json(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "seller_id": resolved_seller_id,
            "baseline": _snapshot_payload(baseline),
            "current": _snapshot_payload(current),
            "deltas": deltas,
            "causal_interpretation": "not_identified",
        }
    )


@tool("commerce_peer_comparison", parse_docstring=True)
async def commerce_peer_comparison_tool(
    runtime: Runtime,
    seller_id: str,
    start: str,
    end: str,
    product_category: str,
    min_orders_per_seller: Annotated[int, Field(ge=2, le=100_000)] = 20,
    match_seller_state: bool = True,
    dataset_id: str | None = None,
) -> str:
    """按结果无关的类目、地区、时间和样本规则构建卖家同类对标。

    Args:
        seller_id: 目标卖家外部业务键或规范化 ``ent_...`` 实体 ID。
        start: ISO-8601 对标窗口开始时间。
        end: ISO-8601 对标窗口结束时间。
        product_category: 只纳入该纯类目订单。
        min_orders_per_seller: 每个卖家最小可比订单数，至少 2。
        match_seller_state: 是否要求卖家所在州一致。
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()

    def compute():
        view, normalized = _resolve_normalized(
            service,
            user_id=user_id,
            thread_id=thread_id,
            dataset_id=dataset_id,
        )
        resolved_seller_id = _resolve_seller_external_key(
            normalized,
            seller_id,
        )
        try:
            comparison = MetricEngine().compute_peer_comparison(
                normalized,
                seller_id=resolved_seller_id,
                window=_metric_window(start, end),
                policy=PeerCohortPolicy(
                    product_category=product_category,
                    min_orders_per_seller=min_orders_per_seller,
                    match_seller_state=match_seller_state,
                ),
            )
        except PeerCohortUnavailableError as exc:
            return view, None, str(exc)
        return view, comparison, None

    view, comparison, unknown_reason = await asyncio.to_thread(compute)
    if comparison is None:
        return _json(
            {
                "ok": True,
                "dataset_id": str(view.manifest.dataset_id),
                "workspace_id": str(view.manifest.workspace_id),
                "status": "unavailable",
                "comparison": None,
                "unknown_reason": unknown_reason,
                "causal_interpretation": "not_identified",
            }
        )
    comparison_payload = comparison.model_dump(mode="json")
    comparison_payload["target_late_delivery_rate"] = _observation_payload(comparison.target_late_delivery_rate)
    comparison_payload["peer_late_delivery_rate"] = _observation_payload(comparison.peer_late_delivery_rate)
    comparison_payload["late_delivery_rate_gap"] = str(comparison.late_delivery_rate_gap)
    return _json(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "comparison": comparison_payload,
            "causal_interpretation": "not_identified",
        }
    )


@tool("commerce_geographic_segments", parse_docstring=True)
async def commerce_geographic_segments_tool(
    runtime: Runtime,
    seller_id: str,
    start: str,
    end: str,
    dataset_id: str | None = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> str:
    """确定性计算卖家订单的客户地域分布；缺字段时返回 unknown 而非零。

    Args:
        seller_id: 目标卖家外部业务键或规范化 ``ent_...`` 实体 ID。
        start: ISO-8601 窗口开始时间。
        end: ISO-8601 窗口结束时间。
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        limit: 按订单量降序返回的地域数量，范围 1 到 50，默认 10。
        offset: 跳过的地域数量，默认 0；用于读取后续分段。
    """
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()

    def compute():
        view, normalized = _resolve_normalized(
            service,
            user_id=user_id,
            thread_id=thread_id,
            dataset_id=dataset_id,
        )
        resolved_seller_id = _resolve_seller_external_key(
            normalized,
            seller_id,
        )
        snapshot = MetricEngine().compute_geographic_order_count(
            normalized,
            seller_id=resolved_seller_id,
            window=_metric_window(start, end),
        )
        return view, snapshot

    view, snapshot = await asyncio.to_thread(compute)
    ordered_segments = sorted(
        snapshot.segments,
        key=lambda item: (-int(item.observation.value or 0), item.customer_state),
    )
    page = ordered_segments[offset : offset + limit]
    returned_order_count = sum(int(segment.observation.value or 0) for segment in page)
    total_order_count = snapshot.total_order_count
    payload = {
        "seller_id": snapshot.seller_id,
        "seller_entity_id": str(snapshot.seller_entity_id),
        "window": snapshot.window.model_dump(mode="json"),
        "semantic_status": snapshot.semantic_status.value,
        "unknown_reason": snapshot.unknown_reason,
    }
    payload["segments"] = [
        {
            "customer_state": segment.customer_state,
            "observation": _observation_payload(segment.observation),
        }
        for segment in page
    ]
    payload.update(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "total_order_count": total_order_count,
            "total_segment_count": len(ordered_segments),
            "returned_segment_count": len(page),
            "returned_order_count": returned_order_count,
            "unreturned_order_count": (total_order_count - returned_order_count if total_order_count is not None else None),
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(page) < len(ordered_segments),
            "sort": "order_count_desc",
        }
    )
    return _json(payload)


@tool("commerce_evidence_query", parse_docstring=True)
async def commerce_evidence_query_tool(
    runtime: Runtime,
    dataset_id: str | None = None,
    fact_ids: list[FactIdInput] | None = None,
    entity_type: EntityType | None = None,
    external_key: str | None = None,
    semantic_fields: list[SemanticField] | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> str:
    """按 Fact ID、实体或语义字段查询可追溯的规范化事实与原始来源定位。

    Args:
        dataset_id: 可选 Dataset ID；省略时使用当前 Dataset。
        fact_ids: 可选 fact_ 前缀 Fact ID 列表，常来自指标 source_fact_ids。
        entity_type: 可选规范化实体类型。
        external_key: 可选实体外部业务键，需与 entity_type 配合使用。
        semantic_fields: 可选语义字段列表，例如 order.delivered_at。
        limit: 返回数量，范围 1 到 100；默认 20，使用 offset 分页。
        offset: 跳过数量，不能为负数。
    """
    if limit < 1 or limit > 100 or offset < 0:
        raise ValueError("limit 必须在 1 到 100 之间，offset 不能为负数")
    parsed_ids = {FactId(value) for value in fact_ids} if fact_ids else None
    parsed_type = EntityType(entity_type) if entity_type is not None else None
    if external_key is not None and parsed_type is None:
        raise ValueError("external_key 查询必须同时提供 entity_type")
    parsed_fields = {SemanticField(value).value for value in semantic_fields} if semantic_fields else None
    user_id, thread_id = _thread_identity(runtime)
    service = _build_context_service()
    view, normalized = await asyncio.to_thread(
        _resolve_normalized,
        service,
        user_id=user_id,
        thread_id=thread_id,
        dataset_id=dataset_id,
    )
    entity_ids = {entity.id for entity in normalized.entities if (parsed_type is None or entity.entity_type is parsed_type) and (external_key is None or entity.external_key == external_key)}
    matches = [fact for fact in normalized.facts if (parsed_ids is None or fact.id in parsed_ids) and (parsed_type is None or fact.entity_id in entity_ids) and (parsed_fields is None or fact.name in parsed_fields)]
    matches.sort(key=lambda item: str(item.id))
    page = matches[offset : offset + limit]
    found_ids = {fact.id for fact in matches}
    return _json(
        {
            "ok": True,
            "dataset_id": str(view.manifest.dataset_id),
            "workspace_id": str(view.manifest.workspace_id),
            "total_matching": len(matches),
            "limit": limit,
            "offset": offset,
            "facts": [fact.model_dump(mode="json") for fact in page],
            "not_found_fact_ids": sorted(str(value) for value in (parsed_ids or set()) - found_ids),
        }
    )
