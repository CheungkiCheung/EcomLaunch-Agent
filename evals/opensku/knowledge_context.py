from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


STAGES = (
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
)

MATURITY_RANK = {
    "draft": 1,
    "verified": 2,
    "proven": 3,
}


@dataclass(frozen=True)
class KnowledgePattern:
    id: str
    type: str
    statement: str
    maturity: str
    maturities: tuple[str, ...]
    occurrence_count: int
    scope: str
    evidence_ids: tuple[str, ...]
    source_case_ids: tuple[str, ...]
    source_run_ids: tuple[str, ...]
    stage_matches: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgePattern":
        statement = _string_value(data.get("statement"))
        source_case_ids = _string_tuple(data.get("source_case_ids"))
        maturities = _string_tuple(data.get("maturities"))
        explicit_maturity = _string_value(data.get("maturity"))
        maturity = _highest_maturity([explicit_maturity, *maturities])
        return cls(
            id=_string_value(data.get("id")),
            type=_string_value(data.get("type")) or "guideline",
            statement=statement,
            maturity=maturity,
            maturities=maturities or ((maturity,) if maturity else tuple()),
            occurrence_count=_int_value(data.get("occurrence_count")),
            scope=_string_value(data.get("scope")) or "workflow",
            evidence_ids=_string_tuple(data.get("evidence_ids")),
            source_case_ids=source_case_ids,
            source_run_ids=_string_tuple(data.get("source_run_ids")),
            stage_matches=_infer_stage_matches(data, statement=statement, source_case_ids=source_case_ids),
        )

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "maturity": self.maturity,
            "stage_matches": list(self.stage_matches),
            "occurrence_count": self.occurrence_count,
            "statement": self.statement,
            "scope": self.scope,
            "evidence_ids": list(self.evidence_ids),
            "source_case_ids": list(self.source_case_ids),
            "source_run_ids": list(self.source_run_ids),
        }


def load_knowledge_patterns(knowledge_dir: Path) -> list[KnowledgePattern]:
    patterns_path = knowledge_dir if knowledge_dir.name == "patterns.json" else knowledge_dir / "patterns.json"
    data = json.loads(patterns_path.read_text(encoding="utf-8"))
    raw_patterns = data.get("patterns", []) if isinstance(data, dict) else []
    if not isinstance(raw_patterns, list):
        raise ValueError(f"patterns must be a JSON array in {patterns_path}")
    return [KnowledgePattern.from_dict(item) for item in raw_patterns if isinstance(item, dict)]


def select_knowledge_patterns(
    patterns: Sequence[KnowledgePattern],
    *,
    case: dict[str, Any] | None,
    limit: int = 5,
) -> list[KnowledgePattern]:
    if limit <= 0:
        return []
    scored = [(_score_pattern(pattern, case=case), pattern) for pattern in patterns if pattern.id and pattern.statement]
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [pattern for score, pattern in scored if score > 0][:limit]


def format_knowledge_context(
    patterns: Sequence[KnowledgePattern],
    *,
    knowledge_dir: Path | None = None,
) -> str:
    if not patterns:
        return ""
    source = f" Source: {knowledge_dir / 'patterns.json'}." if knowledge_dir is not None else ""
    lines = [
        "Relevant OpenSKU reusable knowledge:",
        (
            "Use these source-linked patterns as constraints and reminders for this run."
            " Do not copy a previous decision unless the current evidence supports it."
            f"{source}"
        ),
    ]
    for pattern in patterns:
        stages = ",".join(pattern.stage_matches) if pattern.stage_matches else "all"
        lines.append(
            f"- {pattern.id} [{pattern.type}, {pattern.maturity}, occurrences={pattern.occurrence_count}, stages={stages}]: {pattern.statement}"
        )
    return "\n".join(lines)


def patterns_for_manifest(patterns: Sequence[KnowledgePattern]) -> list[dict[str, Any]]:
    return [pattern.to_manifest_dict() for pattern in patterns]


def resolve_knowledge_dir(path: Path) -> Path:
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / path


def _score_pattern(pattern: KnowledgePattern, *, case: dict[str, Any] | None) -> int:
    case = case or {}
    case_stage = _string_value(case.get("stage"))
    if pattern.type == "decision" and case_stage and pattern.stage_matches and case_stage not in pattern.stage_matches:
        return 0
    case_text = " ".join(
        [
            _string_value(case.get("stage")),
            _string_value(case.get("category")),
            _string_value(case.get("brief")),
            " ".join(str(item) for item in case.get("forbidden_claims", []) if isinstance(item, str)),
        ]
    ).lower()
    text = f"{pattern.statement} {pattern.scope} {pattern.type}".lower()
    score = pattern.occurrence_count + MATURITY_RANK.get(pattern.maturity, 0)

    if _has_any(text, ["private", "metric", "gmv", "ctr", "cvr", "roi", "ad spend", "sales volume", "public fixtures"]):
        score += 1000
    if _has_any(text, ["artifact writer", "validator", "html/csv", "tool call", "runtime artifact"]):
        score += 900

    if pattern.type == "pitfall":
        score += 80
    elif pattern.type == "process":
        score += 70
    elif pattern.type == "guideline":
        score += 60
    elif pattern.type == "model":
        score += 30
    elif pattern.type == "decision":
        score += 10

    if case_stage and case_stage in pattern.stage_matches:
        score += 120
    elif not pattern.stage_matches:
        score += 20

    if _has_any(case_text, ["benchmark", "fixture", "public", "private metric", "forbidden", "gmv", "ctr", "cvr", "roi"]):
        if _has_any(text, ["public fixtures", "private commerce metrics", "metric"]):
            score += 120
        if _has_any(text, ["artifact writer", "validator"]):
            score += 80

    return score


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else tuple()
    if not isinstance(value, list):
        return tuple()
    return tuple(item for item in value if isinstance(item, str) and item)


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _highest_maturity(values: Sequence[str]) -> str:
    candidates = [value for value in values if value in MATURITY_RANK]
    if not candidates:
        return "draft"
    return max(candidates, key=lambda item: MATURITY_RANK[item])


def _infer_stage_matches(
    data: dict[str, Any],
    *,
    statement: str,
    source_case_ids: Sequence[str],
) -> tuple[str, ...]:
    explicit_values: list[str] = []
    for key in ["stage", "stage_match", "stages", "stage_matches", "applicable_stages"]:
        value = data.get(key)
        if isinstance(value, str):
            explicit_values.append(value)
        elif isinstance(value, list):
            explicit_values.extend(item for item in value if isinstance(item, str))
    explicit_stages = _stages_from_text(" ".join(explicit_values))
    if explicit_stages:
        return _ordered_stages(explicit_stages)

    statement_stages = _stages_from_text(" ".join([statement, _string_value(data.get("reuse_key"))]))
    if data.get("type") == "decision" and statement_stages:
        return _ordered_stages(statement_stages)

    text = " ".join([statement, _string_value(data.get("reuse_key")), *source_case_ids])
    stages = _stages_from_text(text)
    return _ordered_stages(stages)


def _stages_from_text(text: str) -> set[str]:
    normalized = text.lower()
    stages = {stage for stage in STAGES if stage in normalized}
    alias_map = {
        "idea": "idea_only",
        "supplier": "supplier_sample",
        "prelaunch": "pre_launch_test",
        "pre_launch": "pre_launch_test",
        "softlaunch": "soft_launch",
        "soft_launch": "soft_launch",
        "scale": "scale_iterate",
    }
    for alias, stage in alias_map.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            stages.add(stage)
    return stages


def _ordered_stages(stages: set[str]) -> tuple[str, ...]:
    return tuple(stage for stage in STAGES if stage in stages)
