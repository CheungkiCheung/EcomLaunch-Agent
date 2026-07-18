# 2026-06-27 - Phase 3 Artifact Validators

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: `c85a39b`
- Goal: execute Phase 3 from `docs/plans/opensku-complete-execution-plan.md`.
- Scope: artifact contracts, validators, golden/broken fixtures, backend test, and validator CLI commands.

## Thinking

Phase 3 matters because OpenSKU's agent outputs need to be inspectable artifacts, not persuasive prose. The project should be able to say exactly why an output is invalid: missing evidence ids, private metric hallucination, empty decision rules, unsupported claim readiness, or invalid knowledge deltas.

The design choice was to validate complete artifact bundles instead of isolated files. A future live agent run writes an output directory, so the validator should already understand an output directory with required artifacts and cross-file evidence references.

Alternatives rejected:

- Do not only test happy-path golden files.
- Do not accept Markdown artifacts that make unsupported product/spec/policy claims.
- Do not allow launch-calendar signals to default to private backend metrics when the evidence ledger has no uploaded-real data.
- Do not validate evidence-ledger parseability without also checking evidence ids and private metric boundaries.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Read Phase 3 requirements | `sed -n '470,610p' docs/plans/opensku-complete-execution-plan.md` | Confirmed required validators, checks, fixtures, and validation commands. |
| 2026-06-27 | Added TDD test | `backend/tests/test_opensku_artifact_validators.py` | First run failed because `evals.opensku.validators` did not exist. |
| 2026-06-27 | Added artifact contract docs | `evals/opensku/schemas/artifact_contracts.json`; `evals/opensku/schemas/README.md` | Documents required columns/fields/sections. |
| 2026-06-27 | Implemented validator core | `evals/opensku/validators/core.py` | Validates artifact bundles, evidence ledger, CSVs, Markdown packs, launch state, promotion replan, knowledge deltas, and cross-file evidence refs. |
| 2026-06-27 | Implemented validator CLI | `evals/opensku/validators/run_all.py` | Supports normal pass mode and `--expect-fail` mode for broken fixtures. |
| 2026-06-27 | Implemented fixture generator | `evals/opensku/fixtures/build_artifact_fixtures.py` | Generates 10 golden bundles and 10 broken bundles. |
| 2026-06-27 | Generated artifact fixtures | `uv run python evals/opensku/fixtures/build_artifact_fixtures.py` | Passed: `golden_bundles=10`, `broken_bundles=10`. |
| 2026-06-27 | Ran backend validator test | `cd backend && uv run pytest tests/test_opensku_artifact_validators.py -q` | Passed: `3 passed, 1 warning in 0.12s`. |
| 2026-06-27 | Ran golden validator CLI | `uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/golden` | Passed: 10/10 bundles passed. |
| 2026-06-27 | Ran broken validator CLI | `uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/broken --expect-fail` | Passed: 10/10 bundles failed as expected. |
| 2026-06-27 | Parsed contract JSON | `uv run python - <<'PY' ... json.loads(...) ... PY` | Passed: `artifact-contracts-json-ok`. |

## Evidence

### Deliverables

```text
evals/opensku/schemas/artifact_contracts.json
evals/opensku/schemas/README.md
evals/opensku/validators/__init__.py
evals/opensku/validators/core.py
evals/opensku/validators/run_all.py
evals/opensku/fixtures/build_artifact_fixtures.py
evals/opensku/fixtures/golden/
evals/opensku/fixtures/broken/
backend/tests/test_opensku_artifact_validators.py
```

### Fixture Generation

Command:

```bash
uv run python evals/opensku/fixtures/build_artifact_fixtures.py
```

Output:

```text
golden_bundles=10
broken_bundles=10
```

Fixture file counts:

```text
golden: 100 files
broken: 100 files
```

Each bundle contains:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
launch-state.json
promotion-replan.md
knowledge-deltas.json
```

### Backend Test Output

Command:

```bash
cd backend && uv run pytest tests/test_opensku_artifact_validators.py -q
```

Output:

```text
...                                                                      [100%]
3 passed, 1 warning in 0.12s
```

### Golden Validator Output

Command:

```bash
uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/golden
```

Output:

```text
fixtures=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/evals/opensku/fixtures/golden
bundle_count=10
passed_count=10
failed_count=0
PASS golden-001 artifacts=10
PASS golden-002 artifacts=10
PASS golden-003 artifacts=10
PASS golden-004 artifacts=10
PASS golden-005 artifacts=10
PASS golden-006 artifacts=10
PASS golden-007 artifacts=10
PASS golden-008 artifacts=10
PASS golden-009 artifacts=10
PASS golden-010 artifacts=10
VALIDATION PASSED
```

### Broken Validator Output

Command:

```bash
uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/broken --expect-fail
```

Output summary:

```text
bundle_count=10
passed_count=0
failed_count=10
EXPECTED_FAILURES_CAUGHT
```

Broken fixture coverage:

```text
broken-001: invalid evidence-ledger JSON
broken-002: evidence item missing id
broken-003: public fixture incorrectly treats GMV as observed_public
broken-004: launch-calendar.csv missing decision_rule column
broken-005: launch-calendar.csv empty decision_rule
broken-006: launch-calendar.csv uses CTR/CVR/GMV/ROI without uploaded_real evidence
broken-007: listing-pack.md contains unsupported FDA approved / 100% safe claims
broken-008: content-pack.md missing Claim readiness label
broken-009: promotion-replan.md missing stop/continue rule
broken-010: knowledge-deltas.json invalid type/maturity and missing source id
```

## Validation

Phase 3 acceptance criteria:

| Requirement | Evidence | Status |
|---|---|---|
| validators catch at least 10 deliberately broken fixture artifacts | `broken` fixture run caught 10/10 broken bundles | Passed |
| validators pass at least 10 golden fixture artifacts | `golden` fixture run passed 10/10 bundles | Passed |
| validators are used by eval runner | `evals/opensku/validators/run_all.py` calls shared validator core | Passed |
| validators are used by at least one backend test | `backend/tests/test_opensku_artifact_validators.py` imports `validate_artifact_bundle` and `validate_fixture_collection` | Passed |
| required backend validation command passes | `cd backend && uv run pytest tests/test_opensku_artifact_validators.py -q` | Passed |
| required golden validation command passes | `uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/golden` | Passed |
| required broken validation command passes with expected failures | `uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/broken --expect-fail` | Passed |

Validator checks now cover:

- parseable JSON evidence ledger.
- evidence item ids.
- allowed evidence types.
- source type presence.
- confidence presence.
- private metrics unavailable unless uploaded or explicitly unavailable.
- parseable launch calendar CSV.
- launch calendar required columns.
- non-empty decision rules.
- no private metric validation signals for no-backend cases.
- claim readiness labels in listing/content packs.
- unsupported product/spec/policy claim traps.
- promotion replan required sections.
- knowledge delta type, maturity, and source id.
- cross-file evidence id references.

What was not tested:

- These validators have not yet been run against a live agent output directory.
- The eval harness has not yet scored model outputs; this is Phase 5.
- Agent prompt/skill files have not yet been hardened to guarantee these artifacts; this is Phase 4.

## Decision

Phase 3 is complete.

Proceed to Phase 4: Agent Contract Hardening.

## Next

1. Update the EcomLaunch skill and SOUL contract so live runs produce the validated artifacts.
2. Update contract tests for stage diagnosis, decision output, artifact list, no private metric invention, and no unsupported exact claims.
3. Run the Phase 4 backend test command.
4. Execute one real live agent validation run and validate its artifact directory.

