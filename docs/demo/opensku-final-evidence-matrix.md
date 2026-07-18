# OpenSKU Final Evidence Matrix

This matrix maps final acceptance claims to inspectable evidence. It is designed
for external review by a human or another model.

## Release Candidate

| Claim | Evidence | Status |
|---|---|---|
| RC2 scores 10 accepted real live runs | `evals/opensku/release_candidates/2026-06-28-rc2-10run.json` | Complete |
| Two runs per launch stage are included | `evals/opensku/release_candidates/2026-06-28-rc2-10run.json` | Complete |
| Expected-decision gate is enabled | `evals/opensku/release_candidates/2026-06-28-rc2-10run.json` | Complete |
| RC2 passes semantic gate | `evals/opensku/reports/2026-06-28-rc2-10run-decision-gate/summary.md` | `PASS 530/530` |
| Historical semantic failures are preserved | `evals/opensku/reports/2026-06-27-rc-gate-probe/summary.md` | Complete |
| Failure analysis and fix decisions are logged | `docs/progress/2026-06-28-final-completion.md` | Complete |

## Real Reruns

| Case | Real Run Directory | Decision Gate Report | Status |
|---|---|---|---|
| `opensku-idea-002` | `docs/progress/runs/2026-06-28/rc2-rerun-opensku-idea-002` | `evals/opensku/reports/2026-06-28-rc2-rerun-opensku-idea-002-decision-gate/summary.md` | `PASS 70/70` |
| `opensku-supplier-002` | `docs/progress/runs/2026-06-28/rc2-rerun-opensku-supplier-002` | `evals/opensku/reports/2026-06-28-rc2-rerun-opensku-supplier-002-decision-gate/summary.md` | `PASS 70/70` |
| `opensku-softlaunch-002` | `docs/progress/runs/2026-06-28/rc2-rerun-opensku-softlaunch-002` | `evals/opensku/reports/2026-06-28-rc2-rerun-opensku-softlaunch-002-decision-gate/summary.md` | `PASS 70/70` |
| `opensku-prelaunch-001` | `docs/progress/runs/2026-06-28/rc2-rerun-opensku-prelaunch-001` | `evals/opensku/reports/2026-06-28-rc2-rerun-opensku-prelaunch-001-decision-gate-after-case-fix/summary.md` | `PASS 70/70` |

## Benchmark And Artifact Contract

| Claim | Evidence | Status |
|---|---|---|
| 30 cases exist across five launch stages | `evals/opensku/cases/`, `evals/opensku/validate_cases.py` | Complete |
| Cases include expected decisions and rationales | `evals/opensku/cases/` | Complete |
| Query/product/category contradiction was corrected | `evals/opensku/cases/opensku-prelaunch-001.json`, `backend/tests/test_opensku_cases.py` | Complete |
| Artifact writer is tested | `backend/tests/test_opensku_artifact_writer_tool.py` | Complete |
| Artifact validator is tested | `backend/tests/test_opensku_artifact_validator_tool.py`, `backend/tests/test_opensku_artifact_validators.py` | Complete |
| Forbidden private metric leakage is blocked | `backend/tests/test_opensku_benchmark_tool_policy.py`, `evals/opensku/scoring.py` | Complete |
| Agent contract requires stage, decision, next loop, data boundary, and artifact list | `backend/tests/test_ecom_launch_contract.py`, `agents/ecom-launch/SOUL.md`, `skills/custom/ecom-launch/SKILL.md` | Complete |

## Knowledge Sedimentation

| Claim | Evidence | Status |
|---|---|---|
| Knowledge is generated from accepted run artifacts | `docs/knowledge/opensku/knowledge-deltas.jsonl` | Complete |
| Ingest report passes | `docs/knowledge/opensku/ingest-report.json` | `PASS` |
| Current accepted run count is 21 | `docs/knowledge/opensku/ingest-report.json` | Complete |
| Current record count is 63 | `docs/knowledge/opensku/ingest-report.json` | Complete |
| Current pattern count is 13 | `docs/knowledge/opensku/ingest-report.json` | Complete |
| Reuse evidence exists | `docs/knowledge/opensku/promotion-report.json` | `reuse_evidence_count=31` |
| Four patterns are promoted after reuse | `docs/knowledge/opensku/promotion-report.json` | `promoted_count=4` |
| Quality gate passes | `evals/opensku/scorers/knowledge_delta_quality.py` run logged in `docs/progress/2026-06-28-final-completion.md` | `PASS 60/60` |

## UI And Frontend

| Claim | Evidence | Status |
|---|---|---|
| War Room renders stage, decision, artifact, and data-boundary cards | `docs/progress/screenshots/2026-06-28-opensku-war-room.png` | Complete |
| War Room central scene is visible in screenshot | `docs/progress/screenshots/2026-06-28-opensku-war-room.png` | Complete |
| Static fallback protects screenshot visibility under Pixi canvas | `frontend/src/components/workspace/ecom-launch/war-room-canvas-stage.tsx` | Complete |
| Ecom-launch UI unit tests pass | `docs/progress/2026-06-28-final-completion.md` | `27` files, `225` tests |
| Real-backend replay E2E passes | `frontend/tests/e2e-real-backend/`, `frontend/tests/e2e-real-backend/real-backend-render.spec.ts-snapshots/real-backend-render-chromium-darwin.png` | `2 passed` |

## Documentation

| Claim | Evidence | Status |
|---|---|---|
| Root README explains final OpenSKU scope | `README.md` | Complete |
| Eval README explains RC2 gate | `evals/opensku/README.md` | Complete |
| Knowledge README explains execution memory boundary | `docs/knowledge/opensku/README.md` | Complete |
| Final completion log records decisions and evidence | `docs/progress/2026-06-28-final-completion.md` | Complete |
| Reviewer guide exists | `docs/demo/opensku-reviewer-guide.md` | Complete |

## Known Limitations

| Limitation | Why It Matters | Boundary |
|---|---|---|
| No private merchant telemetry | Prevents false GMV/CTR/CVR/ROI claims | Metrics remain `unavailable` unless uploaded |
| No production ecommerce connectors | This is a portfolio-grade agent system, not a deployed seller backend | Public fixtures and uploaded files are the current data path |
| Replay-backed frontend E2E is not fresh live model behavior | Avoids overclaiming UI tests as agent-quality proof | RC2 live-run gate is the agent behavior source of truth |
| War Room is a visualization layer | UI should not be confused with eval harness | Artifact contracts and RC gates carry acceptance |
| Public benchmark fixtures are not private company data | Keeps project legally and epistemically honest | Dataset docs describe what each fixture can and cannot prove |
