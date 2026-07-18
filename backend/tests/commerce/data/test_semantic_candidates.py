"""Deterministic candidate parser contracts; no model calls belong here."""

from __future__ import annotations

import json

import pytest

from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_candidates import (
    SemanticCandidateParseError,
    SemanticCandidateParser,
    keep_candidates_unconfirmed,
)
from app.commerce.data.semantic_mapper import MappingSource, MappingStatus, SemanticMapper
from app.commerce.domain.ids import WorkspaceId


def _profile(tmp_path):
    source = tmp_path / "orders.csv"
    source.write_text("order_id,status\no1,delivered\n", encoding="utf-8")
    storage_root = tmp_path / "commerce-storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), (source,))
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    return profile, SemanticMapper().map(profile)


def test_parser_accepts_fenced_json_and_validates_profile_columns(tmp_path):
    profile, mappings = _profile(tmp_path)
    response = """```json
    {"candidates":[{"table_name":"orders","column_name":"status","semantic_field":"order.status","confidence":0.84,"reason":"Status-like values"}]}
    ```"""

    candidates = SemanticCandidateParser().parse(response, profile)

    assert candidates[0].column_name == "status"
    assert candidates[0].confidence == 0.84


def test_parser_rejects_unknown_or_repeated_columns(tmp_path):
    profile, _ = _profile(tmp_path)
    parser = SemanticCandidateParser()
    unknown = json.dumps(
        {
            "candidates": [
                {
                    "table_name": "orders",
                    "column_name": "missing",
                    "semantic_field": "order.status",
                    "confidence": 0.8,
                    "reason": "guess",
                }
            ]
        }
    )
    repeated = json.dumps(
        {
            "candidates": [
                {
                    "table_name": "orders",
                    "column_name": "status",
                    "semantic_field": "order.status",
                    "confidence": 0.8,
                    "reason": "one",
                },
                {
                    "table_name": "orders",
                    "column_name": "status",
                    "semantic_field": "order.status",
                    "confidence": 0.7,
                    "reason": "two",
                },
            ]
        }
    )

    with pytest.raises(SemanticCandidateParseError, match="absent"):
        parser.parse(unknown, profile)
    with pytest.raises(SemanticCandidateParseError, match="repeated"):
        parser.parse(repeated, profile)


def test_candidate_merge_never_overwrites_confirmed_mapping(tmp_path):
    profile, mappings = _profile(tmp_path)
    candidate = SemanticCandidateParser().parse(
        json.dumps(
            {
                "candidates": [
                    {
                        "table_name": "orders",
                        "column_name": "status",
                        "semantic_field": "order.status",
                        "confidence": 0.84,
                        "reason": "Status-like values",
                    }
                ]
            }
        ),
        profile,
    )

    merged = keep_candidates_unconfirmed(mappings, candidate)
    status_mapping = merged.mapping("orders", "status")

    assert status_mapping.source is MappingSource.LLM_CANDIDATE
    assert status_mapping.status is MappingStatus.NEEDS_CONFIRMATION
    assert mappings.mapping("orders", "order_id").status is MappingStatus.CONFIRMED
    assert merged.mapping("orders", "order_id").status is MappingStatus.CONFIRMED
