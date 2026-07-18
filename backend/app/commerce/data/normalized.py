"""Entity-scoped normalized facts and the Olist-specific adapter."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.commerce.data.intake import DataBundleManifest
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import (
    FieldMapping,
    MappingStatus,
    SemanticField,
    SemanticMappingProfile,
)
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import DatasetId, EntityId, FactId, WorkspaceId
from app.commerce.domain.models import Fact, SourceRef


class EntityType(StrEnum):
    ORDER = "order"
    ORDER_ITEM = "order_item"
    REVIEW = "review"
    PRODUCT = "product"
    CUSTOMER = "customer"
    SELLER = "seller"


class NormalizedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NormalizedEntity(NormalizedModel):
    id: EntityId
    workspace_id: WorkspaceId
    dataset_id: DatasetId
    entity_type: EntityType
    external_key: str = Field(min_length=1)
    source_table: str = Field(min_length=1)
    source_record_locator: str = Field(min_length=1)


class NormalizedDataset(NormalizedModel):
    schema_version: str = "1.0"
    dataset_id: DatasetId
    workspace_id: WorkspaceId
    entities: tuple[NormalizedEntity, ...]
    facts: tuple[Fact, ...]

    def entities_of_type(self, entity_type: EntityType) -> tuple[NormalizedEntity, ...]:
        return tuple(entity for entity in self.entities if entity.entity_type is entity_type)

    def facts_named(self, name: str) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.name == name)

    def fact(self, entity_id: EntityId, name: str) -> Fact:
        matches = [fact for fact in self.facts if fact.entity_id == entity_id and fact.name == name]
        if len(matches) != 1:
            raise KeyError(f"Expected one Fact for {entity_id}:{name}, found {len(matches)}")
        return matches[0]


class OlistAdapter:
    """Translate confirmed Olist semantics into stable entity-scoped Facts."""

    SEMANTIC_VERSION = "commerce-semantics@1.0.0"

    _DATETIME_FIELDS = frozenset(
        {
            SemanticField.PURCHASED_AT,
            SemanticField.APPROVED_AT,
            SemanticField.CARRIER_HANDOFF_AT,
            SemanticField.DELIVERED_AT,
            SemanticField.ESTIMATED_DELIVERY_AT,
            SemanticField.SHIPPING_LIMIT_AT,
            SemanticField.REVIEW_CREATED_AT,
            SemanticField.REVIEW_ANSWERED_AT,
        }
    )
    _INTEGER_FIELDS = frozenset({SemanticField.REVIEW_SCORE})
    _DECIMAL_FIELDS = frozenset({SemanticField.ITEM_PRICE, SemanticField.FREIGHT_VALUE})

    def __init__(self, *, storage_root: Path):
        self._reader = DataProfiler(storage_root=storage_root)

    def normalize(
        self,
        manifest: DataBundleManifest,
        mappings: SemanticMappingProfile,
    ) -> NormalizedDataset:
        confirmed_by_table: dict[str, list[FieldMapping]] = {}
        for mapping in mappings.mappings:
            if mapping.status is MappingStatus.CONFIRMED:
                confirmed_by_table.setdefault(mapping.table_name, []).append(mapping)

        files = {file.id: file for file in manifest.files}
        entities: list[NormalizedEntity] = []
        facts: list[Fact] = []

        for table in manifest.tables:
            table_mappings = confirmed_by_table.get(table.table_name, [])
            if not table_mappings:
                continue
            entity_type = self._entity_type(table.table_name)
            source_file = files[table.source_file_id]
            rows = self._reader.read_rows(manifest, table)
            for row_index, row in enumerate(rows, start=1):
                external_key, locator = self._external_key(
                    entity_type,
                    row,
                    table_mappings,
                    row_index,
                )
                entity_id = EntityId(
                    f"ent_{uuid5(NAMESPACE_URL, f'{manifest.dataset_id}:{table.table_name}:{external_key}').hex}"
                )
                entity = NormalizedEntity(
                    id=entity_id,
                    workspace_id=manifest.workspace_id,
                    dataset_id=manifest.dataset_id,
                    entity_type=entity_type,
                    external_key=external_key,
                    source_table=table.table_name,
                    source_record_locator=locator,
                )
                entities.append(entity)

                for mapping in table_mappings:
                    raw_value = row.get(mapping.column_name)
                    source = SourceRef(
                        source_id=source_file.id,
                        dataset_id=manifest.dataset_id,
                        table_name=table.table_name,
                        record_locator=locator,
                        column_name=mapping.column_name,
                    )
                    fact_id = FactId(
                        f"fact_{uuid5(NAMESPACE_URL, f'{entity_id}:{mapping.semantic_field.value}:{mapping.column_name}').hex}"
                    )
                    if self._is_missing(raw_value):
                        facts.append(
                            Fact(
                                id=fact_id,
                                workspace_id=manifest.workspace_id,
                                entity_id=entity_id,
                                name=mapping.semantic_field.value,
                                semantic_version=self.SEMANTIC_VERSION,
                                semantic_status=SemanticStatus.UNKNOWN,
                                value=None,
                                source=source,
                                unknown_reason="Source field is empty",
                            )
                        )
                    else:
                        facts.append(
                            Fact(
                                id=fact_id,
                                workspace_id=manifest.workspace_id,
                                entity_id=entity_id,
                                name=mapping.semantic_field.value,
                                semantic_version=self.SEMANTIC_VERSION,
                                semantic_status=SemanticStatus.OBSERVED,
                                value=self._convert(mapping.semantic_field, raw_value),
                                source=source,
                            )
                        )

        return NormalizedDataset(
            dataset_id=manifest.dataset_id,
            workspace_id=manifest.workspace_id,
            entities=tuple(entities),
            facts=tuple(facts),
        )

    @staticmethod
    def _entity_type(table_name: str) -> EntityType:
        normalized = table_name.lower()
        if "review" in normalized:
            return EntityType.REVIEW
        if "item" in normalized:
            return EntityType.ORDER_ITEM
        if "product" in normalized:
            return EntityType.PRODUCT
        if "customer" in normalized:
            return EntityType.CUSTOMER
        if "seller" in normalized:
            return EntityType.SELLER
        if "order" in normalized:
            return EntityType.ORDER
        raise ValueError(f"OlistAdapter does not recognize table: {table_name}")

    @classmethod
    def _external_key(
        cls,
        entity_type: EntityType,
        row: dict[str, Any],
        mappings: list[FieldMapping],
        row_index: int,
    ) -> tuple[str, str]:
        values = {mapping.semantic_field: row.get(mapping.column_name) for mapping in mappings}
        if entity_type is EntityType.ORDER:
            value = cls._required_key(values, SemanticField.ORDER_ID)
            return value, f"order_id={value}"
        if entity_type is EntityType.PRODUCT:
            value = cls._required_key(values, SemanticField.PRODUCT_ID)
            return value, f"product_id={value}"
        if entity_type is EntityType.CUSTOMER:
            value = cls._required_key(values, SemanticField.CUSTOMER_ID)
            return value, f"customer_id={value}"
        if entity_type is EntityType.SELLER:
            value = cls._required_key(values, SemanticField.SELLER_ID)
            return value, f"seller_id={value}"
        if entity_type is EntityType.ORDER_ITEM:
            order_id = cls._required_key(values, SemanticField.ORDER_ITEM_ORDER_ID)
            seller_id = cls._required_key(values, SemanticField.SELLER_ID)
            product_id = cls._required_key(values, SemanticField.PRODUCT_ID)
            key = f"{order_id}:{seller_id}:{product_id}:{row_index}"
            return key, f"order_id={order_id};row={row_index}"
        order_id = cls._required_key(values, SemanticField.REVIEW_ORDER_ID)
        key = f"{order_id}:{row_index}"
        return key, f"order_id={order_id};row={row_index}"

    @staticmethod
    def _required_key(values: dict[SemanticField, Any], semantic_field: SemanticField) -> str:
        value = values.get(semantic_field)
        if value is None or str(value).strip() == "":
            raise ValueError(f"Missing Olist entity key: {semantic_field.value}")
        return str(value)

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    @classmethod
    def _convert(cls, semantic_field: SemanticField, value: Any):
        if semantic_field in cls._DATETIME_FIELDS:
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if semantic_field in cls._INTEGER_FIELDS:
            return int(value)
        if semantic_field in cls._DECIMAL_FIELDS:
            return Decimal(str(value).strip())
        return str(value)
