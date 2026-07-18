"""Deterministic capability registry for Commerce evidence paths."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_mapper import MappingStatus, SemanticField, SemanticMappingProfile
from app.commerce.domain.ids import DatasetId, WorkspaceId


class CapabilityName(StrEnum):
    FULFILLMENT_DIAGNOSIS = "fulfillment_diagnosis"
    REVIEW_EXPERIENCE = "review_experience"
    SELLER_PEER_COMPARISON = "seller_peer_comparison"


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class CapabilityReasonCode(StrEnum):
    AVAILABLE = "available"
    MISSING_REQUIRED_SEMANTICS = "missing_required_semantics"
    MISSING_OPTIONAL_SEMANTICS = "missing_optional_semantics"
    UNCONFIRMED_SEMANTICS = "unconfirmed_semantics"
    INSUFFICIENT_ENTITY_DIVERSITY = "insufficient_entity_diversity"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"


class CapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiversityRequirement(CapabilityModel):
    semantic_field: SemanticField
    min_unique: int = Field(ge=2)


class CapabilityDefinition(CapabilityModel):
    name: CapabilityName
    path_agent: str = Field(min_length=1)
    required_fields: frozenset[SemanticField] = Field(min_length=1)
    optional_fields: frozenset[SemanticField] = Field(default_factory=frozenset)
    dependencies: frozenset[CapabilityName] = Field(default_factory=frozenset)
    diversity_requirements: tuple[DiversityRequirement, ...] = Field(default_factory=tuple)


class CapabilityAssessment(CapabilityModel):
    name: CapabilityName
    path_agent: str
    status: CapabilityStatus
    reason_codes: frozenset[CapabilityReasonCode]
    available_fields: frozenset[SemanticField]
    missing_required_fields: frozenset[SemanticField]
    missing_optional_fields: frozenset[SemanticField]
    unmet_dependencies: frozenset[CapabilityName] = Field(default_factory=frozenset)


class CapabilityProfile(CapabilityModel):
    schema_version: str = "1.0"
    dataset_id: DatasetId
    workspace_id: WorkspaceId
    capabilities: tuple[CapabilityAssessment, ...]

    def capability(self, name: CapabilityName) -> CapabilityAssessment:
        for capability in self.capabilities:
            if capability.name is name:
                return capability
        raise KeyError(f"Unknown capability {name.value}")

    @property
    def routable_path_agents(self) -> frozenset[str]:
        return frozenset(
            capability.path_agent
            for capability in self.capabilities
            if capability.status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
        )


class CapabilityRegistry:
    """Evaluate data capabilities from confirmed semantics and profile facts."""

    DEFINITIONS = (
        CapabilityDefinition(
            name=CapabilityName.FULFILLMENT_DIAGNOSIS,
            path_agent="FulfillmentPathAgent",
            required_fields=frozenset(
                {
                    SemanticField.ORDER_ID,
                    SemanticField.PURCHASED_AT,
                    SemanticField.APPROVED_AT,
                    SemanticField.CARRIER_HANDOFF_AT,
                    SemanticField.DELIVERED_AT,
                    SemanticField.ESTIMATED_DELIVERY_AT,
                    SemanticField.ORDER_ITEM_ORDER_ID,
                    SemanticField.SELLER_ID,
                }
            ),
            optional_fields=frozenset({SemanticField.ORDER_STATUS, SemanticField.CUSTOMER_STATE}),
        ),
        CapabilityDefinition(
            name=CapabilityName.REVIEW_EXPERIENCE,
            path_agent="ReviewExperiencePathAgent",
            required_fields=frozenset(
                {
                    SemanticField.ORDER_ID,
                    SemanticField.REVIEW_ORDER_ID,
                    SemanticField.REVIEW_SCORE,
                }
            ),
            optional_fields=frozenset(
                {
                    SemanticField.REVIEW_TITLE,
                    SemanticField.REVIEW_COMMENT,
                }
            ),
        ),
        CapabilityDefinition(
            name=CapabilityName.SELLER_PEER_COMPARISON,
            path_agent="SellerPeerPathAgent",
            required_fields=frozenset(
                {
                    SemanticField.ORDER_ID,
                    SemanticField.ORDER_ITEM_ORDER_ID,
                    SemanticField.SELLER_ID,
                    SemanticField.PRODUCT_ID,
                    SemanticField.PRODUCT_CATEGORY,
                    SemanticField.PURCHASED_AT,
                }
            ),
            optional_fields=frozenset(
                {
                    SemanticField.REVIEW_SCORE,
                    SemanticField.CUSTOMER_STATE,
                    SemanticField.SELLER_STATE,
                }
            ),
            dependencies=frozenset({CapabilityName.FULFILLMENT_DIAGNOSIS}),
            diversity_requirements=(
                DiversityRequirement(semantic_field=SemanticField.SELLER_ID, min_unique=2),
            ),
        ),
    )

    def assess(self, profile: DatasetProfile, mappings: SemanticMappingProfile) -> CapabilityProfile:
        confirmed = {
            mapping.semantic_field
            for mapping in mappings.mappings
            if mapping.status is MappingStatus.CONFIRMED
        }
        unconfirmed = {
            mapping.semantic_field
            for mapping in mappings.mappings
            if mapping.status is MappingStatus.NEEDS_CONFIRMATION
        }
        assessments: list[CapabilityAssessment] = []

        for definition in self.DEFINITIONS:
            missing_required = definition.required_fields - confirmed
            missing_optional = definition.optional_fields - confirmed
            unmet_dependencies = frozenset(
                dependency
                for dependency in definition.dependencies
                if self._assessment_status(assessments, dependency) is CapabilityStatus.UNAVAILABLE
            )
            reason_codes: set[CapabilityReasonCode] = set()

            if missing_required:
                reason_codes.add(CapabilityReasonCode.MISSING_REQUIRED_SEMANTICS)
                if missing_required & unconfirmed:
                    reason_codes.add(CapabilityReasonCode.UNCONFIRMED_SEMANTICS)
            if unmet_dependencies:
                reason_codes.add(CapabilityReasonCode.DEPENDENCY_UNAVAILABLE)

            diversity_failed = any(
                self._max_unique_count(profile, mappings, requirement.semantic_field) < requirement.min_unique
                for requirement in definition.diversity_requirements
            )
            if diversity_failed:
                reason_codes.add(CapabilityReasonCode.INSUFFICIENT_ENTITY_DIVERSITY)

            if missing_required or unmet_dependencies or diversity_failed:
                status = CapabilityStatus.UNAVAILABLE
            elif missing_optional:
                status = CapabilityStatus.PARTIAL
                reason_codes.add(CapabilityReasonCode.MISSING_OPTIONAL_SEMANTICS)
            else:
                status = CapabilityStatus.AVAILABLE
                reason_codes.add(CapabilityReasonCode.AVAILABLE)

            assessments.append(
                CapabilityAssessment(
                    name=definition.name,
                    path_agent=definition.path_agent,
                    status=status,
                    reason_codes=frozenset(reason_codes),
                    available_fields=frozenset((definition.required_fields | definition.optional_fields) & confirmed),
                    missing_required_fields=frozenset(missing_required),
                    missing_optional_fields=frozenset(missing_optional),
                    unmet_dependencies=unmet_dependencies,
                )
            )

        return CapabilityProfile(
            dataset_id=profile.dataset_id,
            workspace_id=profile.workspace_id,
            capabilities=tuple(assessments),
        )

    @staticmethod
    def _assessment_status(
        assessments: list[CapabilityAssessment],
        name: CapabilityName,
    ) -> CapabilityStatus | None:
        for assessment in assessments:
            if assessment.name is name:
                return assessment.status
        return None

    @staticmethod
    def _max_unique_count(
        profile: DatasetProfile,
        mappings: SemanticMappingProfile,
        semantic_field: SemanticField,
    ) -> int:
        counts = []
        for mapping in mappings.mappings:
            if mapping.semantic_field is not semantic_field or mapping.status is not MappingStatus.CONFIRMED:
                continue
            counts.append(profile.table(mapping.table_name).column(mapping.column_name).unique_count)
        return max(counts, default=0)
