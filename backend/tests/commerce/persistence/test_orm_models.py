"""Commerce ORM and independent schema contracts."""

from __future__ import annotations

import sqlite3

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from app.commerce.persistence.base import CommerceBase
from app.commerce.persistence.migrations import upgrade_commerce_schema
from app.commerce.persistence.models import (
    CaseRow,
    DomainEventRow,
    EvidenceRow,
    HypothesisRow,
    RunCheckpointRow,
    RunLeaseRow,
    RunRow,
)


def test_commerce_tables_use_an_application_owned_metadata_registry():
    assert CaseRow.metadata is CommerceBase.metadata
    assert DomainEventRow.metadata is CommerceBase.metadata
    assert RunRow.metadata is CommerceBase.metadata
    assert RunCheckpointRow.metadata is CommerceBase.metadata
    assert RunLeaseRow.metadata is CommerceBase.metadata
    assert set(CommerceBase.metadata.tables) == {
        "commerce_cases",
        "commerce_domain_events",
        "commerce_evidence",
        "commerce_hypotheses",
        "commerce_runs",
        "commerce_run_checkpoints",
        "commerce_run_leases",
    }


def test_commerce_tables_compile_for_sqlite_and_postgresql():
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        case_ddl = str(CreateTable(CaseRow.__table__).compile(dialect=dialect))
        event_ddl = str(CreateTable(DomainEventRow.__table__).compile(dialect=dialect))
        evidence_ddl = str(CreateTable(EvidenceRow.__table__).compile(dialect=dialect))
        hypothesis_ddl = str(CreateTable(HypothesisRow.__table__).compile(dialect=dialect))
        run_ddl = str(CreateTable(RunRow.__table__).compile(dialect=dialect))
        checkpoint_ddl = str(
            CreateTable(RunCheckpointRow.__table__).compile(dialect=dialect)
        )
        lease_ddl = str(CreateTable(RunLeaseRow.__table__).compile(dialect=dialect))

        assert "commerce_cases" in case_ddl
        assert "commerce_domain_events" in event_ddl
        assert "case_sequence" in event_ddl
        assert "run_sequence" in event_ddl
        assert "schema_version" in event_ddl
        assert "commerce_evidence" in evidence_ddl
        assert "commerce_hypotheses" in hypothesis_ddl
        assert "PRIMARY KEY" in hypothesis_ddl
        assert "commerce_runs" in run_ddl
        assert "idempotency_key_sha256" in run_ddl
        assert "commerce_run_checkpoints" in checkpoint_ddl
        assert "checkpoint_json" in checkpoint_ddl
        assert "commerce_run_leases" in lease_ddl
        assert "fencing_token" in lease_ddl


def test_independent_commerce_migration_entry_creates_only_commerce_tables(tmp_path):
    database_path = tmp_path / "migrated.db"

    upgrade_commerce_schema(f"sqlite+aiosqlite:///{database_path}")

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert tables == {
        "commerce_alembic_version",
        "commerce_cases",
        "commerce_domain_events",
        "commerce_evidence",
        "commerce_hypotheses",
        "commerce_runs",
        "commerce_run_checkpoints",
        "commerce_run_leases",
    }
