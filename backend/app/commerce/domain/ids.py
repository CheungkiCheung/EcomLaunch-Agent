"""Runtime-validated, JSON-friendly identifiers for Commerce entities."""

from __future__ import annotations

import re
from typing import ClassVar, Self
from uuid import uuid4

from pydantic_core import core_schema


class TypedId(str):
    """A prefixed UUID-hex string that cannot be confused with another ID type."""

    PREFIX: ClassVar[str]
    _UUID_HEX_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"[0-9a-f]{32}")

    def __new__(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError(f"{cls.__name__} must be created from a string")

        prefix = f"{cls.PREFIX}_"
        body = value.removeprefix(prefix)
        if not value.startswith(prefix) or cls._UUID_HEX_PATTERN.fullmatch(body) is None:
            raise ValueError(f"Invalid {cls.__name__}: expected {prefix}<32 lowercase hex chars>")
        return str.__new__(cls, value)

    @classmethod
    def new(cls) -> Self:
        return cls(f"{cls.PREFIX}_{uuid4().hex}")

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(strict=True),
            serialization=core_schema.to_string_ser_schema(),
        )


class WorkspaceId(TypedId):
    PREFIX = "wsp"


class DataSourceId(TypedId):
    PREFIX = "src"


class DatasetId(TypedId):
    PREFIX = "dset"


class EntityId(TypedId):
    PREFIX = "ent"


class FactId(TypedId):
    PREFIX = "fact"


class MetricId(TypedId):
    PREFIX = "metric"


class MetricObservationId(TypedId):
    PREFIX = "mobs"


class CohortId(TypedId):
    PREFIX = "cohort"


class AnomalyId(TypedId):
    PREFIX = "anom"


class CapabilityId(TypedId):
    PREFIX = "cap"


class EvidenceId(TypedId):
    PREFIX = "evd"


class CaseId(TypedId):
    PREFIX = "case"


class HypothesisId(TypedId):
    PREFIX = "hyp"


class ActionId(TypedId):
    PREFIX = "act"


class ApprovalId(TypedId):
    PREFIX = "appr"


class FollowUpId(TypedId):
    PREFIX = "follow"


class RunId(TypedId):
    PREFIX = "run"


class EventId(TypedId):
    PREFIX = "evt"


class TraceId(TypedId):
    PREFIX = "trace"


class CorrelationId(TypedId):
    PREFIX = "corr"


class AgentTaskId(TypedId):
    PREFIX = "task"


class EvaluationCaseId(TypedId):
    PREFIX = "evalcase"


class ExperimentId(TypedId):
    PREFIX = "exp"


class EvaluationRunId(TypedId):
    PREFIX = "evalrun"


class SkillCandidateId(TypedId):
    PREFIX = "skillcand"
