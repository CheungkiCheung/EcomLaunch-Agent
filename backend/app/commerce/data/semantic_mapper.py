"""Deterministic semantic mapping with persistent human confirmations."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.commerce.data.profiler import DatasetProfile
from app.commerce.domain.ids import DatasetId, WorkspaceId


class SemanticField(StrEnum):
    ORDER_ID = "order.id"
    ORDER_STATUS = "order.status"
    PURCHASED_AT = "order.purchased_at"
    APPROVED_AT = "order.approved_at"
    CARRIER_HANDOFF_AT = "order.carrier_handoff_at"
    DELIVERED_AT = "order.delivered_at"
    ESTIMATED_DELIVERY_AT = "order.estimated_delivery_at"
    ORDER_CUSTOMER_ID = "order.customer_id"

    ORDER_ITEM_ORDER_ID = "order_item.order_id"
    SELLER_ID = "seller.id"
    PRODUCT_ID = "product.id"
    SHIPPING_LIMIT_AT = "order_item.shipping_limit_at"
    ITEM_PRICE = "order_item.price"
    FREIGHT_VALUE = "order_item.freight_value"

    REVIEW_ORDER_ID = "review.order_id"
    REVIEW_SCORE = "review.score"
    REVIEW_TITLE = "review.title"
    REVIEW_COMMENT = "review.comment"
    REVIEW_CREATED_AT = "review.created_at"
    REVIEW_ANSWERED_AT = "review.answered_at"

    PRODUCT_CATEGORY = "product.category"
    CUSTOMER_ID = "customer.id"
    CUSTOMER_UNIQUE_ID = "customer.unique_id"
    CUSTOMER_ZIP = "customer.zip"
    CUSTOMER_CITY = "customer.city"
    CUSTOMER_STATE = "customer.state"
    SELLER_ZIP = "seller.zip"
    SELLER_CITY = "seller.city"
    SELLER_STATE = "seller.state"


class MappingSource(StrEnum):
    DETERMINISTIC_RULE = "deterministic_rule"
    LLM_CANDIDATE = "llm_candidate"
    USER_CONFIRMED = "user_confirmed"


class MappingStatus(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    REJECTED = "rejected"


class SemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldMapping(SemanticModel):
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    semantic_field: SemanticField
    confidence: float = Field(ge=0.0, le=1.0)
    source: MappingSource
    status: MappingStatus
    reason: str = Field(min_length=1)


class SemanticMappingProfile(SemanticModel):
    schema_version: str = "1.0"
    dataset_id: DatasetId
    workspace_id: WorkspaceId
    mappings: tuple[FieldMapping, ...]
    unresolved_columns: frozenset[str]

    def mapping(self, table_name: str, column_name: str) -> FieldMapping:
        mapping = self.mapping_or_none(table_name, column_name)
        if mapping is None:
            raise KeyError(f"No semantic mapping for {table_name}.{column_name}")
        return mapping

    def mapping_or_none(self, table_name: str, column_name: str) -> FieldMapping | None:
        for mapping in self.mappings:
            if mapping.table_name == table_name and mapping.column_name == column_name:
                return mapping
        return None

    @property
    def confirmed_mappings(self) -> tuple[FieldMapping, ...]:
        return tuple(mapping for mapping in self.mappings if mapping.status is MappingStatus.CONFIRMED)


class SemanticConfirmation(SemanticModel):
    workspace_id: WorkspaceId
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    semantic_field: SemanticField
    confirmed_at: datetime


class WorkspaceSemanticStore:
    """Small file-backed store for explicit user semantic confirmations."""

    def __init__(self, *, storage_root: Path):
        self._storage_root = storage_root

    def confirm(
        self,
        *,
        workspace_id: WorkspaceId,
        table_name: str,
        column_name: str,
        semantic_field: SemanticField,
    ) -> SemanticConfirmation:
        confirmation = SemanticConfirmation(
            workspace_id=workspace_id,
            table_name=table_name,
            column_name=column_name,
            semantic_field=semantic_field,
            confirmed_at=datetime.now(UTC),
        )
        existing = self.load(workspace_id)
        existing[(table_name, column_name)] = confirmation
        self._write(workspace_id, existing.values())
        return confirmation

    def load(self, workspace_id: WorkspaceId) -> dict[tuple[str, str], SemanticConfirmation]:
        path = self._path(workspace_id)
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        confirmations = (SemanticConfirmation.model_validate(item) for item in payload)
        return {(item.table_name, item.column_name): item for item in confirmations}

    def _path(self, workspace_id: WorkspaceId) -> Path:
        return self._storage_root / "workspaces" / str(workspace_id) / "semantic-mappings.json"

    def _write(self, workspace_id: WorkspaceId, confirmations) -> None:
        path = self._path(workspace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(confirmations, key=lambda item: (item.table_name, item.column_name))
        payload = [item.model_dump(mode="json") for item in ordered]
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)


class SemanticMapper:
    """Apply deterministic rules first; leave ambiguous fields for confirmation."""

    AUTO_CONFIRM_THRESHOLD = 0.90

    _RULES: dict[str, dict[str, tuple[SemanticField, float]]] = {
        "orders": {
            "order_id": (SemanticField.ORDER_ID, 1.0),
            "id": (SemanticField.ORDER_ID, 0.75),
            "order_status": (SemanticField.ORDER_STATUS, 1.0),
            "status": (SemanticField.ORDER_STATUS, 0.85),
            "order_purchase_timestamp": (SemanticField.PURCHASED_AT, 1.0),
            "purchased_at": (SemanticField.PURCHASED_AT, 0.95),
            "order_approved_at": (SemanticField.APPROVED_AT, 1.0),
            "approved_at": (SemanticField.APPROVED_AT, 0.95),
            "order_delivered_carrier_date": (SemanticField.CARRIER_HANDOFF_AT, 1.0),
            "carrier_handoff_at": (SemanticField.CARRIER_HANDOFF_AT, 0.95),
            "order_delivered_customer_date": (SemanticField.DELIVERED_AT, 1.0),
            "delivered_at": (SemanticField.DELIVERED_AT, 0.95),
            "order_estimated_delivery_date": (SemanticField.ESTIMATED_DELIVERY_AT, 1.0),
            "estimated_delivery_at": (SemanticField.ESTIMATED_DELIVERY_AT, 0.95),
            "customer_id": (SemanticField.ORDER_CUSTOMER_ID, 1.0),
        },
        "order_items": {
            "order_id": (SemanticField.ORDER_ITEM_ORDER_ID, 1.0),
            "seller_id": (SemanticField.SELLER_ID, 1.0),
            "product_id": (SemanticField.PRODUCT_ID, 1.0),
            "shipping_limit_date": (SemanticField.SHIPPING_LIMIT_AT, 1.0),
            "price": (SemanticField.ITEM_PRICE, 1.0),
            "freight_value": (SemanticField.FREIGHT_VALUE, 1.0),
        },
        "reviews": {
            "order_id": (SemanticField.REVIEW_ORDER_ID, 1.0),
            "review_score": (SemanticField.REVIEW_SCORE, 1.0),
            "score": (SemanticField.REVIEW_SCORE, 0.95),
            "review_comment_title": (SemanticField.REVIEW_TITLE, 1.0),
            "review_comment_message": (SemanticField.REVIEW_COMMENT, 1.0),
            "review_creation_date": (SemanticField.REVIEW_CREATED_AT, 1.0),
            "review_answer_timestamp": (SemanticField.REVIEW_ANSWERED_AT, 1.0),
        },
        "products": {
            "product_id": (SemanticField.PRODUCT_ID, 1.0),
            "product_category_name": (SemanticField.PRODUCT_CATEGORY, 1.0),
            "category": (SemanticField.PRODUCT_CATEGORY, 0.90),
        },
        "customers": {
            "customer_id": (SemanticField.CUSTOMER_ID, 1.0),
            "customer_unique_id": (SemanticField.CUSTOMER_UNIQUE_ID, 1.0),
            "customer_zip_code_prefix": (SemanticField.CUSTOMER_ZIP, 1.0),
            "customer_city": (SemanticField.CUSTOMER_CITY, 1.0),
            "customer_state": (SemanticField.CUSTOMER_STATE, 1.0),
        },
        "sellers": {
            "seller_id": (SemanticField.SELLER_ID, 1.0),
            "seller_zip_code_prefix": (SemanticField.SELLER_ZIP, 1.0),
            "seller_city": (SemanticField.SELLER_CITY, 1.0),
            "seller_state": (SemanticField.SELLER_STATE, 1.0),
        },
    }

    def __init__(self, *, semantic_store: WorkspaceSemanticStore | None = None):
        self._semantic_store = semantic_store

    def map(self, profile: DatasetProfile) -> SemanticMappingProfile:
        confirmations = self._semantic_store.load(profile.workspace_id) if self._semantic_store else {}
        mappings: list[FieldMapping] = []
        all_columns: set[str] = set()

        for table in profile.tables:
            role = self._table_role(table.table_name)
            rules = self._RULES.get(role, {})
            for column in table.columns:
                key = (table.table_name, column.name)
                qualified = f"{table.table_name}.{column.name}"
                all_columns.add(qualified)
                if key in confirmations:
                    confirmation = confirmations[key]
                    mappings.append(
                        FieldMapping(
                            table_name=table.table_name,
                            column_name=column.name,
                            semantic_field=confirmation.semantic_field,
                            confidence=1.0,
                            source=MappingSource.USER_CONFIRMED,
                            status=MappingStatus.CONFIRMED,
                            reason="Explicit workspace semantic confirmation",
                        )
                    )
                    continue
                rule = rules.get(column.name.lower())
                if rule is None:
                    continue
                semantic_field, confidence = rule
                mappings.append(
                    FieldMapping(
                        table_name=table.table_name,
                        column_name=column.name,
                        semantic_field=semantic_field,
                        confidence=confidence,
                        source=MappingSource.DETERMINISTIC_RULE,
                        status=(
                            MappingStatus.CONFIRMED
                            if confidence >= self.AUTO_CONFIRM_THRESHOLD
                            else MappingStatus.NEEDS_CONFIRMATION
                        ),
                        reason=f"Matched deterministic {role} field rule",
                    )
                )

        mappings = self._downgrade_conflicts(mappings)
        confirmed = {
            f"{mapping.table_name}.{mapping.column_name}"
            for mapping in mappings
            if mapping.status is MappingStatus.CONFIRMED
        }
        return SemanticMappingProfile(
            dataset_id=profile.dataset_id,
            workspace_id=profile.workspace_id,
            mappings=tuple(mappings),
            unresolved_columns=frozenset(all_columns - confirmed),
        )

    @staticmethod
    def _table_role(table_name: str) -> str:
        normalized = table_name.lower()
        if "review" in normalized:
            return "reviews"
        if "item" in normalized:
            return "order_items"
        if "product" in normalized:
            return "products"
        if "seller" in normalized:
            return "sellers"
        if "customer" in normalized:
            return "customers"
        if "order" in normalized:
            return "orders"
        return "unknown"

    @staticmethod
    def _downgrade_conflicts(mappings: list[FieldMapping]) -> list[FieldMapping]:
        grouped: dict[tuple[str, SemanticField], list[int]] = defaultdict(list)
        for index, mapping in enumerate(mappings):
            if mapping.status is MappingStatus.CONFIRMED:
                grouped[(mapping.table_name, mapping.semantic_field)].append(index)

        result = list(mappings)
        for indexes in grouped.values():
            if len(indexes) <= 1:
                continue
            user_confirmed = [index for index in indexes if result[index].source is MappingSource.USER_CONFIRMED]
            keep = user_confirmed[0] if len(user_confirmed) == 1 else None
            for index in indexes:
                if index == keep:
                    continue
                result[index] = result[index].model_copy(
                    update={
                        "status": MappingStatus.NEEDS_CONFIRMATION,
                        "reason": "Conflicting columns map to the same semantic field",
                    }
                )
        return result
