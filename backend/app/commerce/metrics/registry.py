"""Versioned deterministic metric definitions and seller-window engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commerce.data.normalized import EntityType, NormalizedDataset, NormalizedEntity
from app.commerce.data.semantic_mapper import SemanticField
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import EntityId, FactId, MetricObservationId
from app.commerce.domain.models import Fact, MetricObservation


class MetricName(StrEnum):
    ORDER_COUNT = "order_count"
    LATE_DELIVERY_RATE = "late_delivery_rate"
    HANDLING_TIME_HOURS = "handling_time_hours"
    TRANSIT_TIME_HOURS = "transit_time_hours"
    DELIVERY_DURATION_HOURS = "delivery_duration_hours"
    AVERAGE_REVIEW_SCORE = "average_review_score"
    LOW_RATING_RATE = "low_rating_rate"
    PEER_LATE_DELIVERY_RATE = "peer_late_delivery_rate"
    GEOGRAPHIC_ORDER_COUNT = "geographic_order_count"


class MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricDefinition(MetricModel):
    name: MetricName
    formula_version: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    required_fields: frozenset[SemanticField] = Field(min_length=1)
    description: str = Field(min_length=1)


class MetricWindow(MetricModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def require_ordered_window(self) -> Self:
        if self.start >= self.end:
            raise ValueError("MetricWindow start must be before end")
        return self


class MetricSnapshot(MetricModel):
    seller_id: str = Field(min_length=1)
    seller_entity_id: EntityId
    window: MetricWindow
    observations: tuple[MetricObservation, ...]

    def metric(self, name: MetricName) -> MetricObservation:
        for observation in self.observations:
            if observation.metric_name == name.value:
                return observation
        raise KeyError(f"Metric not present in snapshot: {name.value}")


class MetricRegistry:
    definitions = (
        MetricDefinition(
            name=MetricName.ORDER_COUNT,
            formula_version="order_count@1.0.0",
            unit="count",
            required_fields=frozenset({SemanticField.ORDER_ID, SemanticField.PURCHASED_AT, SemanticField.SELLER_ID}),
            description="Distinct seller orders purchased inside the half-open window.",
        ),
        MetricDefinition(
            name=MetricName.LATE_DELIVERY_RATE,
            formula_version="late_delivery_rate@1.0.0",
            unit="ratio",
            required_fields=frozenset({SemanticField.DELIVERED_AT, SemanticField.ESTIMATED_DELIVERY_AT}),
            description="Orders delivered after their estimated delivery timestamp divided by eligible orders.",
        ),
        MetricDefinition(
            name=MetricName.HANDLING_TIME_HOURS,
            formula_version="handling_time_hours@1.0.0",
            unit="hours",
            required_fields=frozenset({SemanticField.APPROVED_AT, SemanticField.CARRIER_HANDOFF_AT}),
            description="Mean hours from order approval to carrier handoff.",
        ),
        MetricDefinition(
            name=MetricName.TRANSIT_TIME_HOURS,
            formula_version="transit_time_hours@1.0.0",
            unit="hours",
            required_fields=frozenset({SemanticField.CARRIER_HANDOFF_AT, SemanticField.DELIVERED_AT}),
            description="Mean hours from carrier handoff to customer delivery.",
        ),
        MetricDefinition(
            name=MetricName.DELIVERY_DURATION_HOURS,
            formula_version="delivery_duration_hours@1.0.0",
            unit="hours",
            required_fields=frozenset({SemanticField.PURCHASED_AT, SemanticField.DELIVERED_AT}),
            description="Mean hours from purchase to customer delivery.",
        ),
        MetricDefinition(
            name=MetricName.AVERAGE_REVIEW_SCORE,
            formula_version="average_review_score@1.0.0",
            unit="score",
            required_fields=frozenset({SemanticField.REVIEW_ORDER_ID, SemanticField.REVIEW_SCORE}),
            description="Mean order-level review score for selected orders.",
        ),
        MetricDefinition(
            name=MetricName.LOW_RATING_RATE,
            formula_version="low_rating_rate@1.0.0",
            unit="ratio",
            required_fields=frozenset({SemanticField.REVIEW_ORDER_ID, SemanticField.REVIEW_SCORE}),
            description="Order-level review scores at or below two divided by reviewed orders.",
        ),
        MetricDefinition(
            name=MetricName.PEER_LATE_DELIVERY_RATE,
            formula_version="peer_late_delivery_rate@1.0.0",
            unit="ratio",
            required_fields=frozenset(
                {
                    SemanticField.SELLER_ID,
                    SemanticField.PRODUCT_ID,
                    SemanticField.PRODUCT_CATEGORY,
                    SemanticField.DELIVERED_AT,
                    SemanticField.ESTIMATED_DELIVERY_AT,
                }
            ),
            description="Late-delivery rate for a comparable multi-seller cohort.",
        ),
        MetricDefinition(
            name=MetricName.GEOGRAPHIC_ORDER_COUNT,
            formula_version="geographic_order_count@1.0.0",
            unit="count",
            required_fields=frozenset({SemanticField.ORDER_CUSTOMER_ID, SemanticField.CUSTOMER_ID, SemanticField.CUSTOMER_STATE}),
            description="Order count grouped by customer geography.",
        ),
    )

    def definition(self, name: MetricName) -> MetricDefinition:
        for definition in self.definitions:
            if definition.name is name:
                return definition
        raise KeyError(name.value)


class MetricEngine:
    """Compute traceable seller-window metrics from normalized Facts."""

    def __init__(self, *, registry: MetricRegistry | None = None):
        self._registry = registry or MetricRegistry()

    def compute_seller_window(
        self,
        normalized: NormalizedDataset,
        *,
        seller_id: str,
        window: MetricWindow,
    ) -> MetricSnapshot:
        facts_by_entity = self._facts_by_entity(normalized)
        seller_entity = self._seller_entity(normalized, seller_id)
        seller_order_ids, item_source_ids = self._seller_orders(normalized, facts_by_entity, seller_id)
        orders = self._selected_orders(normalized, facts_by_entity, seller_order_ids, window)

        observations = (
            self._order_count(normalized, seller_entity, window, orders, item_source_ids),
            self._late_delivery_rate(normalized, seller_entity, window, orders),
            self._duration_metric(
                normalized,
                seller_entity,
                window,
                orders,
                name=MetricName.HANDLING_TIME_HOURS,
                start_field=SemanticField.APPROVED_AT,
                end_field=SemanticField.CARRIER_HANDOFF_AT,
            ),
            self._duration_metric(
                normalized,
                seller_entity,
                window,
                orders,
                name=MetricName.TRANSIT_TIME_HOURS,
                start_field=SemanticField.CARRIER_HANDOFF_AT,
                end_field=SemanticField.DELIVERED_AT,
            ),
            self._duration_metric(
                normalized,
                seller_entity,
                window,
                orders,
                name=MetricName.DELIVERY_DURATION_HOURS,
                start_field=SemanticField.PURCHASED_AT,
                end_field=SemanticField.DELIVERED_AT,
            ),
            *self._review_metrics(normalized, seller_entity, window, facts_by_entity, orders),
        )
        return MetricSnapshot(
            seller_id=seller_id,
            seller_entity_id=seller_entity.id,
            window=window,
            observations=observations,
        )

    @staticmethod
    def _facts_by_entity(normalized: NormalizedDataset) -> dict[EntityId, dict[str, Fact]]:
        result: dict[EntityId, dict[str, Fact]] = defaultdict(dict)
        for fact in normalized.facts:
            if fact.entity_id is not None:
                result[fact.entity_id][fact.name] = fact
        return result

    @staticmethod
    def _seller_entity(normalized: NormalizedDataset, seller_id: str) -> NormalizedEntity:
        for entity in normalized.entities_of_type(EntityType.SELLER):
            if entity.external_key == seller_id:
                return entity
        return NormalizedEntity(
            id=EntityId(f"ent_{uuid5(NAMESPACE_URL, f'{normalized.dataset_id}:seller:{seller_id}').hex}"),
            workspace_id=normalized.workspace_id,
            dataset_id=normalized.dataset_id,
            entity_type=EntityType.SELLER,
            external_key=seller_id,
            source_table="order_items",
            source_record_locator=f"seller_id={seller_id}",
        )

    @staticmethod
    def _known(facts: dict[str, Fact], field: SemanticField) -> Fact | None:
        fact = facts.get(field.value)
        if fact is None or fact.semantic_status is not SemanticStatus.OBSERVED:
            return None
        return fact

    def _seller_orders(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
        seller_id: str,
    ) -> tuple[set[str], tuple[FactId, ...]]:
        order_ids: set[str] = set()
        source_ids: list[FactId] = []
        for entity in normalized.entities_of_type(EntityType.ORDER_ITEM):
            facts = facts_by_entity[entity.id]
            seller = self._known(facts, SemanticField.SELLER_ID)
            order = self._known(facts, SemanticField.ORDER_ITEM_ORDER_ID)
            if seller is None or order is None or str(seller.value) != seller_id:
                continue
            order_ids.add(str(order.value))
            source_ids.extend((seller.id, order.id))
        return order_ids, self._dedupe(source_ids)

    def _selected_orders(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
        seller_order_ids: set[str],
        window: MetricWindow,
    ) -> list[tuple[NormalizedEntity, dict[str, Fact]]]:
        selected = []
        for entity in normalized.entities_of_type(EntityType.ORDER):
            if entity.external_key not in seller_order_ids:
                continue
            facts = facts_by_entity[entity.id]
            purchased = self._known(facts, SemanticField.PURCHASED_AT)
            if purchased is None or not isinstance(purchased.value, datetime):
                continue
            if window.start <= purchased.value < window.end:
                selected.append((entity, facts))
        return selected

    def _order_count(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        orders: list[tuple[NormalizedEntity, dict[str, Fact]]],
        item_source_ids: tuple[FactId, ...],
    ) -> MetricObservation:
        sources = list(item_source_ids)
        for _, facts in orders:
            for field in (SemanticField.ORDER_ID, SemanticField.PURCHASED_AT):
                fact = self._known(facts, field)
                if fact:
                    sources.append(fact.id)
        return self._derived(
            normalized,
            seller,
            window,
            MetricName.ORDER_COUNT,
            value=len(orders),
            sample_size=len(orders),
            numerator=len(orders),
            denominator=None,
            source_ids=self._dedupe(sources),
        )

    def _late_delivery_rate(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        orders: list[tuple[NormalizedEntity, dict[str, Fact]]],
    ) -> MetricObservation:
        eligible: list[tuple[datetime, datetime]] = []
        source_ids: list[FactId] = []
        for _, facts in orders:
            delivered = self._known(facts, SemanticField.DELIVERED_AT)
            estimated = self._known(facts, SemanticField.ESTIMATED_DELIVERY_AT)
            if delivered is None or estimated is None:
                continue
            eligible.append((delivered.value, estimated.value))
            source_ids.extend((delivered.id, estimated.id))
        if not eligible:
            return self._unknown(normalized, seller, window, MetricName.LATE_DELIVERY_RATE, "No eligible delivery timestamps")
        late_count = sum(delivered > estimated for delivered, estimated in eligible)
        return self._derived(
            normalized,
            seller,
            window,
            MetricName.LATE_DELIVERY_RATE,
            value=Decimal(late_count) / Decimal(len(eligible)),
            sample_size=len(eligible),
            numerator=late_count,
            denominator=len(eligible),
            source_ids=self._dedupe(source_ids),
        )

    def _duration_metric(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        orders: list[tuple[NormalizedEntity, dict[str, Fact]]],
        *,
        name: MetricName,
        start_field: SemanticField,
        end_field: SemanticField,
    ) -> MetricObservation:
        values: list[Decimal] = []
        source_ids: list[FactId] = []
        for _, facts in orders:
            start = self._known(facts, start_field)
            end = self._known(facts, end_field)
            if start is None or end is None:
                continue
            seconds = Decimal(str((end.value - start.value).total_seconds()))
            values.append(seconds / Decimal(3600))
            source_ids.extend((start.id, end.id))
        if not values:
            return self._unknown(normalized, seller, window, name, f"No eligible {start_field.value}/{end_field.value} pairs")
        return self._derived(
            normalized,
            seller,
            window,
            name,
            value=sum(values) / Decimal(len(values)),
            sample_size=len(values),
            numerator=None,
            denominator=None,
            source_ids=self._dedupe(source_ids),
        )

    def _review_metrics(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
        orders: list[tuple[NormalizedEntity, dict[str, Fact]]],
    ) -> tuple[MetricObservation, MetricObservation]:
        selected_order_ids = {entity.external_key for entity, _ in orders}
        scores_by_order: dict[str, list[Decimal]] = defaultdict(list)
        source_ids: list[FactId] = []
        review_score_exists = False
        for entity in normalized.entities_of_type(EntityType.REVIEW):
            facts = facts_by_entity[entity.id]
            order = self._known(facts, SemanticField.REVIEW_ORDER_ID)
            score = self._known(facts, SemanticField.REVIEW_SCORE)
            if score is not None:
                review_score_exists = True
            if order is None or score is None or str(order.value) not in selected_order_ids:
                continue
            scores_by_order[str(order.value)].append(Decimal(str(score.value)))
            source_ids.extend((order.id, score.id))

        if not review_score_exists:
            reason = "Required semantic review.score is unavailable"
            return (
                self._unknown(normalized, seller, window, MetricName.AVERAGE_REVIEW_SCORE, reason),
                self._unknown(normalized, seller, window, MetricName.LOW_RATING_RATE, reason),
            )
        if not scores_by_order:
            reason = "No review.score facts for selected orders"
            return (
                self._unknown(normalized, seller, window, MetricName.AVERAGE_REVIEW_SCORE, reason),
                self._unknown(normalized, seller, window, MetricName.LOW_RATING_RATE, reason),
            )

        order_scores = [sum(scores) / Decimal(len(scores)) for scores in scores_by_order.values()]
        low_count = sum(score <= Decimal(2) for score in order_scores)
        sources = self._dedupe(source_ids)
        return (
            self._derived(
                normalized,
                seller,
                window,
                MetricName.AVERAGE_REVIEW_SCORE,
                value=sum(order_scores) / Decimal(len(order_scores)),
                sample_size=len(order_scores),
                numerator=None,
                denominator=None,
                source_ids=sources,
            ),
            self._derived(
                normalized,
                seller,
                window,
                MetricName.LOW_RATING_RATE,
                value=Decimal(low_count) / Decimal(len(order_scores)),
                sample_size=len(order_scores),
                numerator=low_count,
                denominator=len(order_scores),
                source_ids=sources,
            ),
        )

    def _derived(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        name: MetricName,
        *,
        value: Any,
        sample_size: int,
        numerator: int | Decimal | None,
        denominator: int | Decimal | None,
        source_ids: tuple[FactId, ...],
    ) -> MetricObservation:
        definition = self._registry.definition(name)
        observation_id = self._observation_id(normalized, seller, window, name)
        return MetricObservation(
            id=observation_id,
            workspace_id=normalized.workspace_id,
            entity_id=seller.id,
            metric_name=name.value,
            semantic_status=SemanticStatus.DERIVED,
            value=value,
            unit=definition.unit,
            formula_version=definition.formula_version,
            source_fact_ids=source_ids,
            window_start=window.start,
            window_end=window.end,
            sample_size=sample_size,
            numerator=numerator,
            denominator=denominator,
        )

    def _unknown(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        name: MetricName,
        reason: str,
    ) -> MetricObservation:
        definition = self._registry.definition(name)
        return MetricObservation(
            id=self._observation_id(normalized, seller, window, name),
            workspace_id=normalized.workspace_id,
            entity_id=seller.id,
            metric_name=name.value,
            semantic_status=SemanticStatus.UNKNOWN,
            value=None,
            unit=definition.unit,
            formula_version=definition.formula_version,
            source_fact_ids=(),
            window_start=window.start,
            window_end=window.end,
            sample_size=0,
            unknown_reason=reason,
        )

    @staticmethod
    def _observation_id(
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        name: MetricName,
    ) -> MetricObservationId:
        key = f"{normalized.dataset_id}:{seller.id}:{name.value}:{window.start.isoformat()}:{window.end.isoformat()}"
        return MetricObservationId(f"mobs_{uuid5(NAMESPACE_URL, key).hex}")

    @staticmethod
    def _dedupe(values: list[FactId] | tuple[FactId, ...]) -> tuple[FactId, ...]:
        return tuple(dict.fromkeys(values))
