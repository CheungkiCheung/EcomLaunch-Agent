"""Versioned deterministic metric definitions and seller-window engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.commerce.data.normalized import EntityType, NormalizedDataset, NormalizedEntity
from app.commerce.data.semantic_mapper import SemanticField
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import CohortId, EntityId, FactId, MetricObservationId
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

    @field_validator("start", "end")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

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


class PeerCohortPolicy(MetricModel):
    """Outcome-agnostic cohort eligibility rules for seller comparison."""

    formula_version: str = "peer-cohort@1.0.0"
    product_category: str = Field(min_length=1)
    min_orders_per_seller: int = Field(default=20, ge=2)
    match_seller_state: bool = True
    single_seller_orders_only: Literal[True] = True
    pure_category_orders_only: Literal[True] = True


class PeerCohortMember(MetricModel):
    seller_id: str = Field(min_length=1)
    seller_entity_id: EntityId
    eligible_order_count: int = Field(ge=1)
    late_order_count: int = Field(ge=0)
    late_delivery_rate: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_consistent_rate(self) -> Self:
        if self.late_order_count > self.eligible_order_count:
            raise ValueError("late_order_count cannot exceed eligible_order_count")
        expected = Decimal(self.late_order_count) / Decimal(self.eligible_order_count)
        if self.late_delivery_rate != expected:
            raise ValueError("late_delivery_rate must match late_order_count / eligible_order_count")
        return self


class PeerComparisonSnapshot(MetricModel):
    cohort_id: CohortId
    cohort_formula_version: str = Field(min_length=1)
    target_seller_id: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    seller_state: str | None = Field(default=None, min_length=1)
    window: MetricWindow
    target: PeerCohortMember
    peers: tuple[PeerCohortMember, ...] = Field(min_length=1)
    target_late_delivery_rate: MetricObservation
    peer_late_delivery_rate: MetricObservation

    @model_validator(mode="after")
    def require_cohort_consistency(self) -> Self:
        if self.target.seller_id != self.target_seller_id:
            raise ValueError("Peer cohort target seller does not match target_seller_id")
        peer_seller_ids = tuple(member.seller_id for member in self.peers)
        if self.target_seller_id in peer_seller_ids:
            raise ValueError("Peer cohort cannot include the target seller as a peer")
        if len(set(peer_seller_ids)) != len(peer_seller_ids):
            raise ValueError("Peer cohort seller IDs must be unique")
        if self.target_late_delivery_rate.metric_name != MetricName.LATE_DELIVERY_RATE.value:
            raise ValueError("Target cohort observation must be late_delivery_rate")
        if self.peer_late_delivery_rate.metric_name != MetricName.PEER_LATE_DELIVERY_RATE.value:
            raise ValueError("Peer cohort observation must be peer_late_delivery_rate")
        if self.target_late_delivery_rate.denominator != self.target.eligible_order_count:
            raise ValueError("Target observation denominator must match target eligible orders")
        peer_order_count = sum(member.eligible_order_count for member in self.peers)
        if self.peer_late_delivery_rate.denominator != peer_order_count:
            raise ValueError("Peer observation denominator must match pooled peer orders")
        return self

    @property
    def late_delivery_rate_gap(self) -> Decimal:
        return Decimal(str(self.target_late_delivery_rate.value)) - Decimal(str(self.peer_late_delivery_rate.value))


class GeographicSegment(MetricModel):
    customer_state: str = Field(min_length=1)
    observation: MetricObservation

    @model_validator(mode="after")
    def require_geographic_metric(self) -> Self:
        if self.observation.metric_name != MetricName.GEOGRAPHIC_ORDER_COUNT.value:
            raise ValueError("Geographic segment requires geographic_order_count observation")
        return self


class GeographicMetricSnapshot(MetricModel):
    seller_id: str = Field(min_length=1)
    seller_entity_id: EntityId
    window: MetricWindow
    semantic_status: SemanticStatus
    segments: tuple[GeographicSegment, ...] = ()
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_status_consistency(self) -> Self:
        if self.semantic_status is SemanticStatus.UNKNOWN:
            if self.segments:
                raise ValueError("Unknown geographic snapshot cannot carry segments")
            if self.unknown_reason is None:
                raise ValueError("Unknown geographic snapshot requires unknown_reason")
        elif not self.segments:
            raise ValueError("Known geographic snapshot requires segments")
        states = tuple(segment.customer_state for segment in self.segments)
        if len(set(states)) != len(states):
            raise ValueError("Geographic customer-state segments must be unique")
        return self

    @property
    def total_order_count(self) -> int | None:
        if self.semantic_status is SemanticStatus.UNKNOWN:
            return None
        return sum(int(segment.observation.value) for segment in self.segments)

    def segment(self, customer_state: str) -> GeographicSegment:
        for segment in self.segments:
            if segment.customer_state == customer_state:
                return segment
        raise KeyError(f"No geographic segment for customer state {customer_state}")


class PeerCohortUnavailableError(ValueError):
    """Raised when deterministic eligibility rules cannot form a valid cohort."""


@dataclass(frozen=True)
class _ComparableOrder:
    order_id: str
    seller_id: str
    late: bool
    source_fact_ids: tuple[FactId, ...]


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
                    SemanticField.ORDER_ITEM_ORDER_ID,
                    SemanticField.PRODUCT_ID,
                    SemanticField.PRODUCT_CATEGORY,
                    SemanticField.PURCHASED_AT,
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
            required_fields=frozenset(
                {
                    SemanticField.ORDER_ITEM_ORDER_ID,
                    SemanticField.SELLER_ID,
                    SemanticField.PURCHASED_AT,
                    SemanticField.ORDER_CUSTOMER_ID,
                    SemanticField.CUSTOMER_ID,
                    SemanticField.CUSTOMER_STATE,
                }
            ),
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

    def compute_peer_comparison(
        self,
        normalized: NormalizedDataset,
        *,
        seller_id: str,
        window: MetricWindow,
        policy: PeerCohortPolicy,
    ) -> PeerComparisonSnapshot:
        facts_by_entity = self._facts_by_entity(normalized)
        seller_states = self._seller_states(normalized, facts_by_entity)
        target_state = seller_states.get(seller_id)
        if policy.match_seller_state and target_state is None:
            raise PeerCohortUnavailableError("Target seller state is unavailable")

        comparable = self._comparable_orders(
            normalized,
            facts_by_entity,
            window=window,
            policy=policy,
            target_state=target_state,
        )
        orders_by_seller: dict[str, list[_ComparableOrder]] = defaultdict(list)
        for order in comparable:
            orders_by_seller[order.seller_id].append(order)

        eligible = {member_seller_id: orders for member_seller_id, orders in orders_by_seller.items() if len(orders) >= policy.min_orders_per_seller}
        if seller_id not in eligible:
            actual = len(orders_by_seller.get(seller_id, ()))
            raise PeerCohortUnavailableError(f"Target seller has {actual} comparable orders; requires {policy.min_orders_per_seller}")

        peer_seller_ids = tuple(sorted(set(eligible) - {seller_id}))
        if not peer_seller_ids:
            raise PeerCohortUnavailableError("No eligible peer sellers remain after deterministic cohort filters")

        target_entity = self._seller_entity(normalized, seller_id)
        target_orders = eligible[seller_id]
        target_member = self._peer_member(normalized, seller_id, target_orders)
        peer_members = tuple(self._peer_member(normalized, peer_seller_id, eligible[peer_seller_id]) for peer_seller_id in peer_seller_ids)
        peer_orders = [order for peer_seller_id in peer_seller_ids for order in eligible[peer_seller_id]]
        dimension_key = self._cohort_dimension_key(policy, target_state, peer_seller_ids)

        target_rate = self._rate_observation(
            normalized,
            target_entity,
            window,
            MetricName.LATE_DELIVERY_RATE,
            target_orders,
            dimension_key=f"target:{dimension_key}",
        )
        peer_rate = self._rate_observation(
            normalized,
            target_entity,
            window,
            MetricName.PEER_LATE_DELIVERY_RATE,
            peer_orders,
            dimension_key=f"peers:{dimension_key}",
        )
        cohort_key = f"{normalized.dataset_id}:{seller_id}:{window.start.isoformat()}:{window.end.isoformat()}:{policy.formula_version}:{dimension_key}"
        return PeerComparisonSnapshot(
            cohort_id=CohortId(f"cohort_{uuid5(NAMESPACE_URL, cohort_key).hex}"),
            cohort_formula_version=policy.formula_version,
            target_seller_id=seller_id,
            product_category=policy.product_category,
            seller_state=target_state if policy.match_seller_state else None,
            window=window,
            target=target_member,
            peers=peer_members,
            target_late_delivery_rate=target_rate,
            peer_late_delivery_rate=peer_rate,
        )

    def compute_geographic_order_count(
        self,
        normalized: NormalizedDataset,
        *,
        seller_id: str,
        window: MetricWindow,
    ) -> GeographicMetricSnapshot:
        facts_by_entity = self._facts_by_entity(normalized)
        seller_entity = self._seller_entity(normalized, seller_id)
        seller_order_ids, _ = self._seller_orders(normalized, facts_by_entity, seller_id)
        orders = self._selected_orders(normalized, facts_by_entity, seller_order_ids, window)
        customer_states = self._customer_states(normalized, facts_by_entity)
        order_item_sources = self._seller_order_item_sources(normalized, facts_by_entity, seller_id)
        state_sources: dict[str, list[FactId]] = defaultdict(list)
        state_counts: dict[str, int] = defaultdict(int)

        for order_entity, order_facts in orders:
            customer = self._known(order_facts, SemanticField.ORDER_CUSTOMER_ID)
            if customer is None:
                continue
            customer_state = customer_states.get(str(customer.value))
            if customer_state is None:
                continue
            state, customer_source_ids = customer_state
            state_counts[state] += 1
            state_sources[state].extend(customer_source_ids)
            state_sources[state].append(customer.id)
            state_sources[state].extend(order_item_sources.get(order_entity.external_key, ()))
            for field in (SemanticField.ORDER_ID, SemanticField.PURCHASED_AT):
                fact = self._known(order_facts, field)
                if fact is not None:
                    state_sources[state].append(fact.id)

        if not state_counts:
            return GeographicMetricSnapshot(
                seller_id=seller_id,
                seller_entity_id=seller_entity.id,
                window=window,
                semantic_status=SemanticStatus.UNKNOWN,
                unknown_reason="No customer.state facts could be joined to selected seller orders",
            )

        segments = tuple(
            GeographicSegment(
                customer_state=state,
                observation=self._derived(
                    normalized,
                    seller_entity,
                    window,
                    MetricName.GEOGRAPHIC_ORDER_COUNT,
                    value=count,
                    sample_size=count,
                    numerator=count,
                    denominator=None,
                    source_ids=self._dedupe(state_sources[state]),
                    dimension_key=f"customer_state={state}",
                ),
            )
            for state, count in sorted(state_counts.items())
        )
        return GeographicMetricSnapshot(
            seller_id=seller_id,
            seller_entity_id=seller_entity.id,
            window=window,
            semantic_status=SemanticStatus.DERIVED,
            segments=segments,
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

    def _seller_order_item_sources(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
        seller_id: str,
    ) -> dict[str, tuple[FactId, ...]]:
        sources: dict[str, list[FactId]] = defaultdict(list)
        for entity in normalized.entities_of_type(EntityType.ORDER_ITEM):
            facts = facts_by_entity[entity.id]
            seller = self._known(facts, SemanticField.SELLER_ID)
            order = self._known(facts, SemanticField.ORDER_ITEM_ORDER_ID)
            if seller is None or order is None or str(seller.value) != seller_id:
                continue
            sources[str(order.value)].extend((seller.id, order.id))
        return {order_id: self._dedupe(values) for order_id, values in sources.items()}

    def _seller_states(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
    ) -> dict[str, str]:
        return {seller_id: state for seller_id, (state, _) in self._seller_state_details(normalized, facts_by_entity).items()}

    def _seller_state_details(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
    ) -> dict[str, tuple[str, tuple[FactId, ...]]]:
        result: dict[str, tuple[str, tuple[FactId, ...]]] = {}
        for entity in normalized.entities_of_type(EntityType.SELLER):
            facts = facts_by_entity[entity.id]
            seller = self._known(facts, SemanticField.SELLER_ID)
            state = self._known(facts, SemanticField.SELLER_STATE)
            if seller is not None and state is not None:
                result[str(seller.value)] = (str(state.value), (seller.id, state.id))
        return result

    def _customer_states(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
    ) -> dict[str, tuple[str, tuple[FactId, ...]]]:
        result: dict[str, tuple[str, tuple[FactId, ...]]] = {}
        for entity in normalized.entities_of_type(EntityType.CUSTOMER):
            facts = facts_by_entity[entity.id]
            customer = self._known(facts, SemanticField.CUSTOMER_ID)
            state = self._known(facts, SemanticField.CUSTOMER_STATE)
            if customer is not None and state is not None:
                result[str(customer.value)] = (str(state.value), (customer.id, state.id))
        return result

    def _product_categories(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
    ) -> dict[str, tuple[str, tuple[FactId, ...]]]:
        result: dict[str, tuple[str, tuple[FactId, ...]]] = {}
        for entity in normalized.entities_of_type(EntityType.PRODUCT):
            facts = facts_by_entity[entity.id]
            product = self._known(facts, SemanticField.PRODUCT_ID)
            category = self._known(facts, SemanticField.PRODUCT_CATEGORY)
            if product is not None and category is not None:
                result[str(product.value)] = (str(category.value), (product.id, category.id))
        return result

    def _comparable_orders(
        self,
        normalized: NormalizedDataset,
        facts_by_entity: dict[EntityId, dict[str, Fact]],
        *,
        window: MetricWindow,
        policy: PeerCohortPolicy,
        target_state: str | None,
    ) -> tuple[_ComparableOrder, ...]:
        categories = self._product_categories(normalized, facts_by_entity)
        seller_state_details = self._seller_state_details(normalized, facts_by_entity)
        seller_states = {seller_id: state for seller_id, (state, _) in seller_state_details.items()}
        item_rows: dict[str, list[tuple[str, str, tuple[FactId, ...]]]] = defaultdict(list)
        for entity in normalized.entities_of_type(EntityType.ORDER_ITEM):
            facts = facts_by_entity[entity.id]
            order = self._known(facts, SemanticField.ORDER_ITEM_ORDER_ID)
            seller = self._known(facts, SemanticField.SELLER_ID)
            product = self._known(facts, SemanticField.PRODUCT_ID)
            if order is None or seller is None or product is None:
                continue
            item_rows[str(order.value)].append(
                (
                    str(seller.value),
                    str(product.value),
                    (order.id, seller.id, product.id),
                )
            )

        comparable: list[_ComparableOrder] = []
        for entity in normalized.entities_of_type(EntityType.ORDER):
            facts = facts_by_entity[entity.id]
            purchased = self._known(facts, SemanticField.PURCHASED_AT)
            delivered = self._known(facts, SemanticField.DELIVERED_AT)
            estimated = self._known(facts, SemanticField.ESTIMATED_DELIVERY_AT)
            if purchased is None or delivered is None or estimated is None:
                continue
            if not isinstance(purchased.value, datetime) or not window.start <= purchased.value < window.end:
                continue

            items = item_rows.get(entity.external_key, ())
            seller_ids = {seller_id for seller_id, _, _ in items}
            if policy.single_seller_orders_only and len(seller_ids) != 1:
                continue
            member_seller_id = next(iter(seller_ids))
            if policy.match_seller_state and seller_states.get(member_seller_id) != target_state:
                continue

            item_categories: set[str] = set()
            source_ids: list[FactId] = []
            category_complete = True
            for _, product_id, item_source_ids in items:
                category = categories.get(product_id)
                if category is None:
                    category_complete = False
                    break
                category_name, category_source_ids = category
                item_categories.add(category_name)
                source_ids.extend(item_source_ids)
                source_ids.extend(category_source_ids)
            if not category_complete:
                continue
            if policy.pure_category_orders_only and item_categories != {policy.product_category}:
                continue

            state_detail = seller_state_details.get(member_seller_id)
            if state_detail is not None:
                source_ids.extend(state_detail[1])
            for field in (
                SemanticField.ORDER_ID,
                SemanticField.PURCHASED_AT,
                SemanticField.DELIVERED_AT,
                SemanticField.ESTIMATED_DELIVERY_AT,
            ):
                fact = self._known(facts, field)
                if fact is not None:
                    source_ids.append(fact.id)

            comparable.append(
                _ComparableOrder(
                    order_id=entity.external_key,
                    seller_id=member_seller_id,
                    late=delivered.value > estimated.value,
                    source_fact_ids=self._dedupe(source_ids),
                )
            )
        return tuple(comparable)

    def _peer_member(
        self,
        normalized: NormalizedDataset,
        seller_id: str,
        orders: list[_ComparableOrder],
    ) -> PeerCohortMember:
        late_count = sum(order.late for order in orders)
        return PeerCohortMember(
            seller_id=seller_id,
            seller_entity_id=self._seller_entity(normalized, seller_id).id,
            eligible_order_count=len(orders),
            late_order_count=late_count,
            late_delivery_rate=Decimal(late_count) / Decimal(len(orders)),
        )

    def _rate_observation(
        self,
        normalized: NormalizedDataset,
        seller: NormalizedEntity,
        window: MetricWindow,
        name: MetricName,
        orders: list[_ComparableOrder],
        *,
        dimension_key: str,
    ) -> MetricObservation:
        late_count = sum(order.late for order in orders)
        return self._derived(
            normalized,
            seller,
            window,
            name,
            value=Decimal(late_count) / Decimal(len(orders)),
            sample_size=len(orders),
            numerator=late_count,
            denominator=len(orders),
            source_ids=self._dedupe([source_id for order in orders for source_id in order.source_fact_ids]),
            dimension_key=dimension_key,
        )

    @staticmethod
    def _cohort_dimension_key(
        policy: PeerCohortPolicy,
        seller_state: str | None,
        peer_seller_ids: tuple[str, ...],
    ) -> str:
        peers = ",".join(peer_seller_ids)
        return f"category={policy.product_category};seller_state={seller_state or '*'};min_orders={policy.min_orders_per_seller};peers={peers}"

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
        dimension_key: str | None = None,
    ) -> MetricObservation:
        definition = self._registry.definition(name)
        observation_id = self._observation_id(
            normalized,
            seller,
            window,
            name,
            dimension_key=dimension_key,
        )
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
        *,
        dimension_key: str | None = None,
    ) -> MetricObservationId:
        key = f"{normalized.dataset_id}:{seller.id}:{name.value}:{window.start.isoformat()}:{window.end.isoformat()}"
        if dimension_key is not None:
            key = f"{key}:{dimension_key}"
        return MetricObservationId(f"mobs_{uuid5(NAMESPACE_URL, key).hex}")

    @staticmethod
    def _dedupe(values: list[FactId] | tuple[FactId, ...]) -> tuple[FactId, ...]:
        return tuple(dict.fromkeys(values))
