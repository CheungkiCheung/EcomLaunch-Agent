"""Fail-closed LLM semantic candidates; candidates never auto-confirm mappings."""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field, ValidationError

from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_mapper import (
    FieldMapping,
    MappingSource,
    MappingStatus,
    SemanticField,
    SemanticMappingProfile,
)
from app.commerce.domain.models import CommerceModel


class SemanticCandidateParseError(ValueError):
    """The model response is not a valid, profile-grounded candidate payload."""


class SemanticMappingCandidate(CommerceModel):
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    semantic_field: SemanticField
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


class SemanticCandidateEnvelope(CommerceModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    candidates: tuple[SemanticMappingCandidate, ...]


class SemanticCandidateParser:
    """Parse strict JSON and validate every candidate against the profiled schema."""

    def parse(
        self,
        response_text: str,
        profile: DatasetProfile,
    ) -> tuple[SemanticMappingCandidate, ...]:
        payload = self._decode_json(response_text)
        raw_candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(raw_candidates, list):
            raise SemanticCandidateParseError("Candidate response must contain a candidates array")

        candidates: list[SemanticMappingCandidate] = []
        seen_columns: set[tuple[str, str]] = set()
        for raw_candidate in raw_candidates:
            try:
                candidate = SemanticMappingCandidate.model_validate(raw_candidate)
            except ValidationError as exc:
                raise SemanticCandidateParseError("Candidate item failed schema validation") from exc
            key = (candidate.table_name, candidate.column_name)
            if key in seen_columns:
                raise SemanticCandidateParseError(
                    f"Candidate column is repeated: {candidate.table_name}.{candidate.column_name}"
                )
            seen_columns.add(key)
            try:
                profile.table(candidate.table_name).column(candidate.column_name)
            except KeyError as exc:
                raise SemanticCandidateParseError(
                    f"Candidate column is absent from profile: {candidate.table_name}.{candidate.column_name}"
                ) from exc
            candidates.append(candidate)
        return tuple(candidates)

    @staticmethod
    def _decode_json(response_text: str) -> dict[str, Any]:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise SemanticCandidateParseError("Candidate response is not valid JSON") from None
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise SemanticCandidateParseError("Candidate response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise SemanticCandidateParseError("Candidate response root must be an object")
        return payload


def keep_candidates_unconfirmed(
    profile: SemanticMappingProfile,
    candidates: tuple[SemanticMappingCandidate, ...],
) -> SemanticMappingProfile:
    """Attach only non-confirmed candidate mappings; existing confirmations win."""

    mappings = list(profile.mappings)
    indexed = {(mapping.table_name, mapping.column_name): index for index, mapping in enumerate(mappings)}
    for candidate in candidates:
        key = (candidate.table_name, candidate.column_name)
        existing_index = indexed.get(key)
        if existing_index is not None and mappings[existing_index].status is MappingStatus.CONFIRMED:
            continue
        candidate_mapping = FieldMapping(
            table_name=candidate.table_name,
            column_name=candidate.column_name,
            semantic_field=candidate.semantic_field,
            confidence=candidate.confidence,
            source=MappingSource.LLM_CANDIDATE,
            status=MappingStatus.NEEDS_CONFIRMATION,
            reason=candidate.reason,
        )
        if existing_index is None:
            indexed[key] = len(mappings)
            mappings.append(candidate_mapping)
        else:
            mappings[existing_index] = candidate_mapping
    confirmed = {
        f"{mapping.table_name}.{mapping.column_name}"
        for mapping in mappings
        if mapping.status is MappingStatus.CONFIRMED
    }
    # Preserve the original unresolved set and add any candidate column that is not confirmed.
    unresolved = set(profile.unresolved_columns)
    unresolved.update(
        f"{mapping.table_name}.{mapping.column_name}"
        for mapping in mappings
        if mapping.status is not MappingStatus.CONFIRMED
    )
    unresolved.difference_update(confirmed)
    return profile.model_copy(
        update={
            "mappings": tuple(mappings),
            "unresolved_columns": frozenset(unresolved),
        }
    )
