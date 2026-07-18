#!/usr/bin/env python3
"""Promote OpenSKU knowledge patterns after successful reuse.

Promotion is intentionally conservative: a pattern moves from draft to verified
only when it was injected into a later accepted live run. The script records the
reuse evidence in ``patterns.json`` and writes ``promotion-report.json``.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_KNOWLEDGE_DIR = Path("docs/knowledge/opensku")
DEFAULT_RUNS_ROOT = Path("docs/progress/runs")
MATURITY_ORDER = ["draft", "verified", "proven"]
MATURITY_RANK = {name: index for index, name in enumerate(MATURITY_ORDER)}


@dataclass(frozen=True)
class KnowledgePromotionConfig:
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR
    runs_root: Path = DEFAULT_RUNS_ROOT
    min_promotions: int = 0


@dataclass(frozen=True)
class KnowledgePromotionReport:
    status: str
    knowledge_dir: str
    runs_root: str
    scanned_run_count: int
    reuse_evidence_count: int
    promoted_count: int
    verified_reuse_pattern_count: int
    errors: list[str]


def promote_knowledge_maturity(config: KnowledgePromotionConfig) -> KnowledgePromotionReport:
    patterns_path = config.knowledge_dir / "patterns.json"
    data = _read_json(patterns_path)
    errors: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("patterns"), list):
        errors.append(f"{patterns_path}: expected object with patterns array")
        report = KnowledgePromotionReport(
            status="FAIL",
            knowledge_dir=str(config.knowledge_dir),
            runs_root=str(config.runs_root),
            scanned_run_count=0,
            reuse_evidence_count=0,
            promoted_count=0,
            verified_reuse_pattern_count=0,
            errors=errors,
        )
        _write_report(config.knowledge_dir, report)
        return report

    patterns = [item for item in data["patterns"] if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in patterns if item.get("id")}
    by_reuse_key = {
        _pattern_reuse_key(item): item
        for item in patterns
        if _pattern_reuse_key(item)
    }
    run_dirs = _discover_run_dirs(config.runs_root)
    reuse_evidence = _collect_reuse_evidence(run_dirs)
    promoted_count = 0

    for evidence in reuse_evidence:
        pattern = _pattern_for_evidence(evidence, by_reuse_key=by_reuse_key, by_id=by_id)
        if pattern is None:
            continue
        if not _reuse_evidence_can_promote_pattern(pattern, evidence):
            continue
        existing_evidence = pattern.setdefault("reuse_evidence", [])
        if not isinstance(existing_evidence, list):
            existing_evidence = []
            pattern["reuse_evidence"] = existing_evidence
        if not any(item.get("run_id") == evidence["run_id"] for item in existing_evidence if isinstance(item, dict)):
            existing_evidence.append(
                {
                    "run_id": evidence["run_id"],
                    "case_id": evidence["case_id"],
                    "run_dir": evidence["run_dir"],
                    "promoted_to": "verified",
                }
            )

        current = _current_maturity(pattern)
        if current == "draft":
            pattern["maturity"] = "verified"
            maturities = set(_maturities(pattern))
            maturities.add("verified")
            pattern["maturities"] = _sort_maturities(maturities)
            promoted_count += 1

    data["patterns"] = patterns
    data["pattern_count"] = len(patterns)
    verified_reuse_pattern_count = _verified_reuse_pattern_count(patterns)
    if config.min_promotions and verified_reuse_pattern_count < config.min_promotions:
        errors.append(
            f"verified_reuse_pattern_count={verified_reuse_pattern_count} is below required minimum {config.min_promotions}"
        )
    status = "PASS" if not errors else "FAIL"
    patterns_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = KnowledgePromotionReport(
        status=status,
        knowledge_dir=str(config.knowledge_dir),
        runs_root=str(config.runs_root),
        scanned_run_count=len(run_dirs),
        reuse_evidence_count=len(reuse_evidence),
        promoted_count=promoted_count,
        verified_reuse_pattern_count=verified_reuse_pattern_count,
        errors=errors,
    )
    _write_report(config.knowledge_dir, report)
    return report


def _discover_run_dirs(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    return sorted(path.parent for path in runs_root.rglob("artifacts-manifest.json"))


def _collect_reuse_evidence(run_dirs: list[Path]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for run_dir in run_dirs:
        if not _run_passed(run_dir):
            continue
        manifest = _read_json(run_dir / "artifacts-manifest.json")
        if not isinstance(manifest, dict):
            continue
        injected = manifest.get("injected_knowledge_patterns")
        if not isinstance(injected, list):
            continue
        run_id = str(manifest.get("run_id") or "")
        case_id = str(manifest.get("case_id") or run_dir.name)
        final_decision = _final_decision_for_run(run_dir, manifest)
        for item in injected:
            if not isinstance(item, dict):
                continue
            pattern_id = str(item.get("id") or "")
            if not pattern_id:
                continue
            evidence.append(
                {
                    "pattern_id": pattern_id,
                    "reuse_key": _evidence_reuse_key(item),
                    "statement": str(item.get("statement") or ""),
                    "scope": str(item.get("scope") or "workflow"),
                    "pattern_type": str(item.get("type") or ""),
                    "stage_matches": ",".join(stage for stage in item.get("stage_matches", []) if isinstance(stage, str))
                    if isinstance(item.get("stage_matches"), list)
                    else "",
                    "run_id": run_id,
                    "case_id": case_id,
                    "run_dir": str(run_dir),
                    "final_decision": final_decision,
                }
            )
    return evidence


def _pattern_for_evidence(
    evidence: dict[str, str],
    *,
    by_reuse_key: dict[str, dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    reuse_key = evidence.get("reuse_key", "")
    if reuse_key:
        return by_reuse_key.get(reuse_key)
    pattern = by_id.get(evidence["pattern_id"])
    if pattern is None:
        return None
    if not _evidence_matches_pattern(pattern, evidence):
        return None
    return pattern


def _evidence_matches_pattern(pattern: dict[str, Any], evidence: dict[str, str]) -> bool:
    statement = str(evidence.get("statement") or "")
    pattern_statement = str(pattern.get("statement") or "")
    pattern_type = str(pattern.get("type") or "")
    evidence_type = str(evidence.get("pattern_type") or "")
    if statement and pattern_statement and _normalize_statement(statement) != _normalize_statement(pattern_statement):
        return False
    if evidence_type and pattern_type and evidence_type != pattern_type:
        return False
    return True


def _run_passed(run_dir: Path) -> bool:
    run_log = run_dir / "run-log.md"
    if not run_log.exists():
        return False
    return bool(re.search(r"^Status:\s*PASS\s*$", run_log.read_text(encoding="utf-8"), re.M))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _final_decision_for_run(run_dir: Path, manifest: dict[str, Any]) -> str:
    outputs_dir = manifest.get("outputs_dir")
    candidates: list[Path] = []
    if isinstance(outputs_dir, str) and outputs_dir:
        candidates.append(Path(outputs_dir) / "launch-state.json")
    candidates.append(run_dir / "launch-state.json")
    for path in candidates:
        payload = _read_json(path)
        if isinstance(payload, dict):
            decision = _normalize_decision(str(payload.get("decision") or ""))
            if decision:
                return decision
    return ""


def _pattern_reuse_key(pattern: dict[str, Any]) -> str:
    explicit = str(pattern.get("reuse_key") or "").strip()
    if explicit:
        return explicit
    return _reuse_key(
        pattern_type=str(pattern.get("type") or ""),
        scope=str(pattern.get("scope") or "workflow"),
        statement=str(pattern.get("statement") or ""),
    )


def _evidence_reuse_key(item: dict[str, Any]) -> str:
    return _reuse_key(
        pattern_type=str(item.get("type") or ""),
        scope=str(item.get("scope") or "workflow"),
        statement=str(item.get("statement") or ""),
    )


def _reuse_key(*, pattern_type: str, scope: str, statement: str) -> str:
    normalized_statement = _normalize_statement(statement)
    if not pattern_type or not normalized_statement:
        return ""
    return f"{pattern_type}|{scope or 'workflow'}|{normalized_statement}"


def _normalize_statement(statement: str) -> str:
    return re.sub(r"\s+", " ", statement.lower()).strip()


def _reuse_evidence_can_promote_pattern(pattern: dict[str, Any], evidence: dict[str, str]) -> bool:
    pattern_type = str(pattern.get("type") or evidence.get("pattern_type") or "")
    if pattern_type != "decision":
        return True
    run_stage = _infer_stage_from_case_id(evidence.get("case_id", ""))
    if not run_stage:
        return False
    stage_matches = _stage_matches(pattern, evidence)
    if stage_matches and run_stage not in stage_matches:
        return False
    pattern_decision = _decision_from_statement(str(pattern.get("statement") or ""))
    final_decision = _normalize_decision(evidence.get("final_decision", ""))
    return bool(pattern_decision and final_decision and pattern_decision == final_decision)


def _decision_from_statement(statement: str) -> str:
    match = re.search(r"\b(?:state|decision)\s+is\s+(go|pivot|hold|kill|scale)\b", statement, re.I)
    if match:
        return _normalize_decision(match.group(1))
    return ""


def _normalize_decision(decision: str) -> str:
    normalized = decision.strip().lower()
    aliases = {
        "go": "go",
        "pivot": "pivot",
        "hold": "hold",
        "kill": "kill",
        "scale": "scale",
    }
    return aliases.get(normalized, "")


def _stage_matches(pattern: dict[str, Any], evidence: dict[str, str]) -> set[str]:
    values: set[str] = set()
    for value in str(evidence.get("stage_matches") or "").split(","):
        if value:
            values.add(value)
    for key in ["stage", "stage_match", "stage_matches", "applicable_stages"]:
        raw = pattern.get(key)
        if isinstance(raw, str):
            values.add(raw)
        elif isinstance(raw, list):
            values.update(item for item in raw if isinstance(item, str))
    statement = str(pattern.get("statement") or "").lower()
    values.update(stage for stage in STAGES if stage in statement)
    return {value for value in values if value in STAGES}


STAGES = {
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
}


def _infer_stage_from_case_id(case_id: str) -> str:
    lower = case_id.lower()
    aliases = {
        "idea": "idea_only",
        "supplier": "supplier_sample",
        "prelaunch": "pre_launch_test",
        "pre_launch": "pre_launch_test",
        "softlaunch": "soft_launch",
        "soft_launch": "soft_launch",
        "scale": "scale_iterate",
    }
    for alias, stage in aliases.items():
        if alias in lower:
            return stage
    return ""


def _maturities(pattern: dict[str, Any]) -> list[str]:
    maturities = pattern.get("maturities")
    values: list[str] = []
    if isinstance(pattern.get("maturity"), str):
        values.append(pattern["maturity"])
    if isinstance(maturities, list):
        values.extend(item for item in maturities if isinstance(item, str))
    return [item for item in values if item in MATURITY_RANK] or ["draft"]


def _current_maturity(pattern: dict[str, Any]) -> str:
    return max(_maturities(pattern), key=lambda item: MATURITY_RANK[item])


def _sort_maturities(maturities: set[str]) -> list[str]:
    return sorted((item for item in maturities if item in MATURITY_RANK), key=lambda item: MATURITY_RANK[item])


def _verified_reuse_pattern_count(patterns: list[dict[str, Any]]) -> int:
    count = 0
    for pattern in patterns:
        reuse_evidence = pattern.get("reuse_evidence")
        if not isinstance(reuse_evidence, list) or not reuse_evidence:
            continue
        if MATURITY_RANK.get(_current_maturity(pattern), 0) >= MATURITY_RANK["verified"]:
            count += 1
    return count


def _write_report(knowledge_dir: Path, report: KnowledgePromotionReport) -> None:
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "promotion-report.json").write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--min-promotions", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = promote_knowledge_maturity(
        KnowledgePromotionConfig(
            knowledge_dir=args.knowledge,
            runs_root=args.runs,
            min_promotions=args.min_promotions,
        )
    )
    print(f"knowledge_dir={report.knowledge_dir}")
    print(f"status={report.status}")
    print(f"scanned_run_count={report.scanned_run_count}")
    print(f"reuse_evidence_count={report.reuse_evidence_count}")
    print(f"promoted_count={report.promoted_count}")
    print(f"verified_reuse_pattern_count={report.verified_reuse_pattern_count}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
