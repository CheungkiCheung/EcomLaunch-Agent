# OpenSKU Complete Execution Plan

Date: 2026-06-27

Status: execution source of truth with RC2 completion progress

Owner: project maintainer with Codex execution support

## Current Progress Snapshot

Last updated: 2026-06-28

Completed evidence:

- 30 OpenSKU benchmark cases exist across five launch stages.
- 10-run live acceptance set passed aggregate execution scoring: `PASS 420/420`.
- 10-run semantic release-candidate gate passes: `evals/opensku/reports/2026-06-28-rc2-10run-decision-gate/`, `PASS 530/530`.
- RC2 uses `evals/opensku/release_candidates/2026-06-28-rc2-10run.json`, with two accepted real live runs per launch stage.
- Four historical semantic mismatches were resolved through real reruns and one benchmark correction:
  - `opensku-idea-002`: real rerun, expected `Pivot`, actual `Pivot`.
  - `opensku-supplier-002`: real rerun, expected `Pivot`, actual `Pivot`.
  - `opensku-softlaunch-002`: real rerun, expected `Pivot`, actual `Pivot`.
  - `opensku-prelaunch-001`: WANDS query/product/category mismatch corrected from `Go` to `Pivot`, then passed decision gate.
- Knowledge sedimentation is active: `accepted_run_count=21`, `record_count=63`, `pattern_count=13`.
- Strict knowledge promotion is active: `reuse_evidence_count=31`, `promoted_count=4`, `verified_reuse_pattern_count=4`.
- Knowledge quality gate passes: `PASS 60/60`.
- Expected-decision gate exists and correctly caught a semantic mismatch: `opensku-prelaunch-002` expected `Pivot`, earlier live run chose `Kill`.
- The taxonomy fix was verified through a real live rerun: `live-decision-taxonomy-prelaunch-002` passed `--decision-gate` with `expected=Pivot`, `actual=Pivot`, `score=70/70`.
- A named multi-stage release-candidate gate exists: `evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json`.
- The first five-stage RC gate passes: `evals/opensku/reports/2026-06-27-rc1-five-stage-decision-gate/`, `PASS 280/280`.
- The historical 10-run RC decision-gate probe remains logged as a useful failure: `evals/opensku/reports/2026-06-27-rc-gate-probe/`, `FAIL 500/520`.
- Frontend OpenSKU component verification passes: `pnpm typecheck`; `27` unit test files and `225` tests passed.
- UI evidence exists at `docs/progress/screenshots/2026-06-28-opensku-war-room.png`.
- Real-backend replay E2E passes: `cd frontend && pnpm exec playwright test --config=playwright.real-backend.config.ts`, `2 passed`.

Still pending for the full portfolio phase:

- Final backend/eval regression sweep after documentation and War Room fallback edits.
- Final frontend regression sweep after screenshot fallback.
- Demo package and reviewer-facing reproduction guide.
- Final `git diff --check`.

## 0. Intent

OpenSKU should become a credible, complete agent-system portfolio project, not a small demo that only generates a fixed validation pack.

The target product is:

```text
OpenSKU: evidence-governed adaptive SKU launch loop.
```

The target engineering story is:

```text
Real ecommerce datasets + real agent execution + artifact contracts + eval harness + knowledge sedimentation + inspectable UI.
```

This plan is intentionally complete. It is not a minimum viable validation path. Every milestone has real acceptance criteria, real command gates, and a required execution log. If a milestone cannot be verified with real data or a real agent call, the milestone is not done.

## 1. Non-Negotiables

1. No fake private metrics.
   - GMV, CTR, CVR, ROI, ad spend, sales volume, refund rate, repeat purchase rate, and verified uplift are unavailable unless uploaded or present in a public dataset.

2. No mock-only acceptance.
   - Unit tests and replay tests are useful regression gates.
   - They do not count as final acceptance for agent behavior.
   - Each product milestone needs at least one real run through the OpenSKU agent path.

3. Real agent validation means the real runtime path.
   - Frontend or API submits a user prompt.
   - Runtime context uses `agent_name=ecom-launch` and `mode=ultra`.
   - The backend builds the lead agent.
   - The `ecom-launch` skill is loaded.
   - Subagent execution is enabled.
   - Tool calls happen through the real tool layer.
   - Artifacts are written to the thread output directory.
   - `present_files` exposes the artifacts.

4. Logs are mandatory at key nodes.
   - Each milestone starts with an execution log.
   - Each validation run writes a run log.
   - Each failed run writes a failure analysis.
   - Logs must include what was attempted, why, commands run, evidence collected, results, and next decisions.

5. Dataset usage must be honest.
   - Public datasets can simulate uploaded real context, but the docs must say they are public benchmark fixtures.
   - Olist/RetailRocket/Taobao behavior data can support soft-launch and scale-like cases.
   - Amazon Reviews/WANDS/ESCI/MAVE can support public signal, search fit, VOC, and claim readiness.
   - None of these equals a live merchant backend integration.

6. Product scope remains narrow.
   - OpenSKU is about SKU launch decisions.
   - It is not a generic growth automation platform.
   - It is not a crawler for private ecommerce dashboards.
   - It is not an ad bidding or attribution product.

## 2. Source Of Truth

Current source files:

```text
README.md
AGENTS.md
agents/ecom-launch/SOUL.md
skills/custom/ecom-launch/SKILL.md
docs/ecom-launch/README.md
docs/ecom-launch/USER_MANUAL.md
docs/ecom-launch/manual-run-prompt.md
docs/plans/ecom-launch-agent-spec.md
```

This execution plan supersedes older growth-engine planning documents for future work. Historical documents can remain, but they must be marked archived if their terminology conflicts with OpenSKU.

## 3. Completion Definition

OpenSKU is complete for this portfolio phase when all of the following are true:

1. It can run at least 30 curated benchmark cases across five launch stages:
   - `idea_only`
   - `supplier_sample`
   - `pre_launch_test`
   - `soft_launch`
   - `scale_iterate`

2. It can perform at least 10 live agent validation runs through the real runtime path:
   - 2 idea-only cases
   - 2 supplier/sample cases
   - 2 pre-launch test cases
   - 2 soft-launch cases
   - 2 scale/iterate cases

3. Every live run produces required artifacts:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

4. Runs with feedback or benchmark context also produce:

```text
launch-state.json
promotion-replan.md
knowledge-deltas.json
```

5. Artifact validators pass:
   - JSON parseability.
   - CSV parseability.
   - required fields.
   - evidence IDs referenced consistently.
   - no forbidden private metric inventions.
   - no unsupported exact product/spec/policy claims.
   - launch-calendar decision rules are explicit.

6. Eval harness produces a report:

```text
evals/opensku/reports/<timestamp>/summary.md
evals/opensku/reports/<timestamp>/scores.json
evals/opensku/reports/<timestamp>/failures.md
```

7. UI shows the launch loop clearly:
   - stage diagnosis.
   - decision status.
   - launch crew activity.
   - required artifacts.
   - optional replan and knowledge artifacts.
   - evidence limitations.

8. Documentation is coherent:
   - README explains OpenSKU in 30 seconds.
   - user manual explains real data limitations.
   - data map explains datasets and license/use boundaries.
   - eval docs explain scorers and benchmark cases.
   - demo guide reproduces at least one real live run.

9. Final validation includes:
   - backend focused tests.
   - frontend unit tests.
   - frontend typecheck.
   - real backend replay e2e.
   - real live agent run.
   - screenshot/video evidence for the UI.

## 4. Validation Philosophy

Use three validation layers, but do not confuse them.

| Layer | Purpose | Can use fake/replay? | Counts as milestone acceptance? |
|---|---|---:|---:|
| L1 Unit and contract tests | Fast regression checks | Yes | No, by itself |
| L2 Replay and real-backend tests | Protocol and UI stability | Yes, replay model allowed | No, by itself |
| L3 Live agent validation | Product truth | No fake model, no mocked agent path | Yes |

### L3 Live Agent Validation Requirements

A live run must record:

```text
run_id
thread_id
date
model
mode
agent_name
input case id
uploaded files
tools used
subagents invoked
artifact paths
validator result
screenshots if UI involved
final decision
known limitations
```

Live run evidence should be stored under:

```text
docs/progress/runs/<YYYY-MM-DD>/<case_id>/
├── run-log.md
├── final-response.md
├── validator-output.txt
├── artifacts-manifest.json
├── screenshots/
└── notes.md
```

## 5. Logging Protocol

Every key node must create or update a log under `docs/progress/`.

### Required Key Nodes

1. plan start
2. data source decision
3. dataset ingestion complete
4. benchmark case schema finalized
5. first artifact validator passing
6. first offline eval report passing
7. first live agent run passing
8. first live run with uploaded benchmark data passing
9. first UI run passing
10. knowledge-deltas loop passing
11. full benchmark suite passing
12. final release candidate review

### Log Template

```markdown
# <YYYY-MM-DD> - <Milestone Or Run Name>

## Context

- Branch:
- Commit:
- Goal:
- Scope:

## Thinking

Why this milestone matters.
What tradeoff was chosen.
What alternatives were rejected and why.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|

## Evidence

Links to files, run ids, screenshots, reports, command outputs.

## Validation

What was tested.
What passed.
What failed.
What was not tested and why.

## Decision

Proceed / retry / block / change scope.

## Next

Exact next steps.
```

### Log Quality Bar

Bad log:

```text
Updated evals. Tests pass.
```

Acceptable log:

```text
Implemented deterministic metric-honesty scorer because forbidden private metric leakage is the highest trust risk.
Ran it against 12 benchmark artifacts. 10 passed, 2 failed because the agent wrote "expected CVR".
Decision: tighten skill forbidden-claims section and add a regression case.
```

## 6. Project Phases

## Phase 0: Baseline Audit And Freeze

Goal: establish current truth before building.

### Work

1. Record current git status.
2. Identify unrelated dirty files.
3. Record current docs/product positioning.
4. Run existing focused tests.
5. Create progress log.

### Deliverables

```text
docs/progress/<date>-baseline-audit.md
docs/progress/current-known-dirty-files.md
```

### Validation

Commands:

```bash
git status --short
cd backend && uv run pytest tests/test_ecom_launch_contract.py -q
cd frontend && pnpm typecheck
```

Acceptance:

- command outputs are copied or summarized in the log.
- unrelated dirty files are explicitly listed.
- OpenSKU source-of-truth docs are identified.

## Phase 1: Data Strategy And Dataset Map

Goal: turn "I have no real data" into a credible open-data strategy.

### Data Sources

Use the following data sources as first-class benchmark inputs:

| Dataset | Use In OpenSKU | Stage Coverage |
|---|---|---|
| Olist Brazilian E-Commerce Public Dataset | order, review, delivery, product, payment, seller context | `soft_launch`, `scale_iterate` |
| RetailRocket Ecommerce Dataset | behavior events: view, add-to-cart, transaction | `pre_launch_test`, `soft_launch` |
| Amazon Reviews 2023 | reviews, ratings, product metadata, prices, descriptions | `idea_only`, `supplier_sample`, `pre_launch_test` |
| Amazon ESCI Shopping Queries | query-product relevance and search fit | `pre_launch_test` |
| Wayfair WANDS | product search relevance in home/furniture domain | `pre_launch_test` |
| MAVE | product attribute-value extraction and claim/spec validation | `supplier_sample`, claim readiness |
| Taobao User Behavior / TAOBAO-MM | China ecommerce behavior benchmark, optional large-scale path | `soft_launch`, `scale_iterate` |
| ShoppingMMLU / ChineseEcomQA / ShoppingComp / ShoppingBench / ECom-Bench | domain knowledge and shopping-agent evaluation reference | supplemental eval |

### Deliverables

```text
docs/data/open-data-map.md
docs/data/dataset-licenses.md
docs/data/data-usage-boundary.md
docs/progress/<date>-data-source-decision.md
```

### Acceptance

- Each dataset has:
  - source URL.
  - license or usage note.
  - fields used.
  - what it can prove.
  - what it cannot prove.
  - which OpenSKU stage it supports.
- The docs explicitly state that these are public benchmark fixtures, not live merchant integrations.
- At least 5 dataset sources are verified from primary pages.

### Real Validation

Not enough to list links. Must actually load a sample.

Commands to add and run:

```bash
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset olist --limit 5
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset amazon_reviews --limit 5
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset wands --limit 5
```

Acceptance:

- sample rows saved under `data/opensku/samples/`.
- schemas saved under `data/opensku/schemas/`.
- log includes sample row counts and fields.

## Phase 2: OpenSKU-Bench Case Schema

Goal: create a benchmark format that maps real public datasets into launch-loop tasks.

### Work

Create:

```text
evals/opensku/case_schema.json
evals/opensku/README.md
evals/opensku/cases/
evals/opensku/fixtures/
```

Case schema must include:

```json
{
  "case_id": "string",
  "stage": "idea_only | supplier_sample | pre_launch_test | soft_launch | scale_iterate",
  "category": "string",
  "brief": "string",
  "public_context": [],
  "uploaded_real": [],
  "expected_decision": "Go | Pivot | Hold | Kill | Scale",
  "required_artifacts": [],
  "required_claims": [],
  "forbidden_claims": [],
  "scoring_notes": {},
  "source_dataset": []
}
```

### Benchmark Case Targets

Create at least 30 cases:

| Stage | Count | Example Sources |
|---|---:|---|
| `idea_only` | 6 | Amazon Reviews, WANDS, ESCI |
| `supplier_sample` | 6 | MAVE, Amazon metadata |
| `pre_launch_test` | 6 | ESCI, WANDS, RetailRocket |
| `soft_launch` | 8 | Olist, RetailRocket |
| `scale_iterate` | 4 | Olist, RetailRocket, Taobao optional |

### Acceptance

- `evals/opensku/case_schema.json` validates all cases.
- every case has a source dataset and a stage.
- every case has an expected decision with rationale.
- no case relies on invented live backend data.
- at least 10 cases include uploaded-data simulation.
- at least 10 cases include public-signal context.
- at least 5 cases are designed to catch forbidden metric hallucination.
- at least 5 cases are designed to catch unsupported product/spec/policy claims.

### Validation Commands

```bash
uv run python evals/opensku/validate_cases.py
uv run python evals/opensku/print_case_matrix.py
```

## Phase 3: Artifact Schemas And Validators

Goal: make the output contract machine-checkable.

### Work

Create validators for:

```text
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

Create:

```text
evals/opensku/schemas/
evals/opensku/validators/
backend/tests/test_opensku_artifact_validators.py
```

### Required Checks

#### Evidence Ledger

- parseable JSON.
- every evidence item has an id.
- evidence_type is one of:
  - `observed_public`
  - `uploaded_real`
  - `estimated`
  - `unavailable`
  - `assumption`
- source_type is present.
- confidence is present.
- private metrics are unavailable unless uploaded.

#### Launch Calendar

- parseable CSV.
- required columns:

```text
day,objective,experiment,asset,channel,validation_signal_to_collect,decision_rule,owner,expected_output
```

- decision rule is not empty.
- validation signals do not default to private backend metrics for no-backend cases.

#### Listing And Content Packs

- include claim readiness labels.
- exact specs use placeholders unless supported.
- forbidden claims are absent.

#### Promotion Replan

- includes observed signal.
- includes interpretation.
- includes plan change.
- includes next test.
- includes stop/continue rule.

#### Knowledge Deltas

- includes type:
  - `decision`
  - `guideline`
  - `pitfall`
  - `process`
  - `model`
- includes maturity:
  - `draft`
  - `verified`
  - `proven`
- includes source case or run id.

### Acceptance

- validators catch at least 10 deliberately broken fixture artifacts.
- validators pass at least 10 golden fixture artifacts.
- validators are used by the eval runner and by at least one backend test.

### Validation Commands

```bash
cd backend && uv run pytest tests/test_opensku_artifact_validators.py -q
uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/golden
uv run python evals/opensku/validators/run_all.py --fixtures evals/opensku/fixtures/broken --expect-fail
```

## Phase 4: Agent Contract Hardening

Goal: make the agent produce adaptive launch-loop artifacts reliably.

### Work

Update:

```text
agents/ecom-launch/SOUL.md
skills/custom/ecom-launch/SKILL.md
docs/ecom-launch/manual-run-prompt.md
```

Required behavior:

- classify launch stage before recommendation.
- choose Go/Pivot/Hold/Kill/Scale.
- use all five roles for full runs.
- create required artifacts.
- create optional loop artifacts when uploaded data exists.
- never silently downgrade to smoke test.
- never invent private metrics.
- never invent exact specs, certification, refund policy, warranty, or testimonials.
- produce knowledge deltas when reusable learning exists.

### Acceptance

- contract tests assert the new behavior.
- skill text includes all required artifacts.
- SOUL final response rules mention:
  - launch stage.
  - decision.
  - next-loop test.
  - promotion adjustment.
  - data limitations.
  - artifact list.

### Validation Commands

```bash
cd backend && uv run pytest tests/test_ecom_launch_contract.py tests/test_lead_agent_skills.py tests/test_subagent_prompt_security.py -q
```

### Real Agent Validation

Run at least one live case after this phase:

```text
case: idea_only.amazon_reviews.coffee_tumbler
mode: ultra
agent_name: ecom-launch
expected decision: Go or Pivot with rationale
```

Acceptance:

- actual run invokes `ecom-launch`.
- final answer states launch stage.
- final answer states decision.
- required artifacts exist.
- artifact validators pass.

## Phase 5: Offline Eval Harness

Goal: score benchmark outputs repeatably.

### Work

Create:

```text
evals/opensku/run_eval.py
evals/opensku/scorers/
evals/opensku/reports/
```

Scorers:

| Scorer | Type | What It Checks |
|---|---|---|
| artifact completeness | deterministic | required files exist |
| parseability | deterministic | JSON/CSV parse |
| evidence type validity | deterministic | evidence labels valid |
| metric honesty | deterministic | no invented private metrics |
| unsupported claim detection | deterministic | no exact unsupported spec/policy claims |
| stage diagnosis quality | rubric judge | stage matches case data |
| decision quality | rubric judge | Go/Pivot/Hold/Kill/Scale rationale |
| promotion replan grounding | rubric judge | changes are tied to observed data |
| knowledge delta quality | rubric judge | reusable, typed, sourced |

### Acceptance

- deterministic scorers run without model access.
- rubric scorers can run with configured judge model.
- eval report includes per-case failures, not only aggregate score.
- score threshold for release candidate:
  - deterministic pass rate >= 95%.
  - no forbidden metric leakage.
  - no required artifact missing.
  - rubric average >= 4.0 / 5.0.

### Validation Commands

```bash
uv run python evals/opensku/run_eval.py --cases evals/opensku/cases --mode deterministic
uv run python evals/opensku/run_eval.py --cases evals/opensku/cases --mode judge
```

## Phase 6: Real Live Agent Runner

Goal: make live agent validation reproducible and logged.

### Work

Create a runner that can call the real backend with real runtime context:

```text
scripts/opensku/run_live_agent_case.py
scripts/opensku/collect_live_run_artifacts.py
scripts/opensku/validate_live_run.py
```

The runner should:

1. create or reuse a thread.
2. upload case fixture files.
3. submit the case prompt with:

```json
{
  "agent_name": "ecom-launch",
  "mode": "ultra",
  "thinking_enabled": true,
  "is_plan_mode": true,
  "subagent_enabled": true,
  "reasoning_effort": "high"
}
```

4. stream until completion.
5. save raw stream events.
6. collect output artifacts.
7. run artifact validators.
8. write run log.

### Acceptance

- runner can execute one case end-to-end against a local backend.
- runner stores all evidence under `docs/progress/runs/`.
- runner fails non-zero when:
  - no artifacts are produced.
  - validators fail.
  - agent does not use `ecom-launch`.
  - required stage/decision missing.

### Required Live Runs

Before final completion:

| Stage | Required Live Runs |
|---|---:|
| `idea_only` | 2 |
| `supplier_sample` | 2 |
| `pre_launch_test` | 2 |
| `soft_launch` | 2 |
| `scale_iterate` | 2 |

### Validation Commands

```bash
make dev-daemon
uv run python scripts/opensku/run_live_agent_case.py --case evals/opensku/cases/idea_only.amazon_reviews.coffee_tumbler.json
uv run python scripts/opensku/validate_live_run.py --run docs/progress/runs/<date>/<case_id>
make stop
```

If a real API key/model is unavailable, this phase is blocked. It must not be marked passed with replay.

## Phase 7: Real Backend Replay Regression

Goal: keep deterministic regression coverage while live runs remain expensive.

### Work

Add replay fixture for one canonical OpenSKU case:

```text
backend/tests/fixtures/replay/opensku_launch_loop.ultra.json
backend/tests/fixtures/replay/opensku_launch_loop.ultra.events.json
backend/tests/test_opensku_replay_golden.py
frontend/tests/e2e-real-backend/opensku-real-backend-render.spec.ts
```

### Acceptance

- replay fixture was recorded from a real model run.
- replay test fails on stale prompt/tool graph hash miss.
- event golden catches SSE protocol drift.
- frontend real-backend test renders model-generated content from the replay.

### Validation Commands

```bash
cd backend && uv run pytest tests/test_opensku_replay_golden.py -q
cd frontend && pnpm test:e2e -- tests/e2e-real-backend/opensku-real-backend-render.spec.ts
```

## Phase 8: UI Productization

Goal: make the UI communicate the loop, not only show a decorative War Room.

### Work

Update `frontend/src/components/workspace/ecom-launch/` to show:

- launch stage.
- decision.
- evidence confidence.
- artifact status.
- promotion replan status.
- knowledge deltas status.
- unavailable metrics warning.
- launch crew agent activity.

### Required UI States

1. empty state.
2. running state.
3. subagent active state.
4. artifact generated state.
5. validation failure state.
6. completed state.

### Acceptance

- UI renders without overlap on desktop and mobile.
- stage and decision are first-viewport visible.
- optional artifacts have dedicated cards.
- user can open every generated artifact.
- UI does not claim real private metrics.
- screenshot evidence stored in progress run folder.

### Validation Commands

```bash
cd frontend && pnpm typecheck
cd frontend && pnpm test -- tests/unit/components/workspace/ecom-launch
cd frontend && pnpm test:e2e -- tests/e2e/agent-chat.spec.ts tests/e2e/artifact-preview.spec.ts
```

Real UI validation:

```bash
make dev-daemon
uv run python scripts/opensku/run_live_agent_case.py --case evals/opensku/cases/soft_launch.olist.home_decor_pivot.json --open-ui
cd frontend && pnpm test:e2e -- tests/e2e-real-backend/opensku-live-ui.spec.ts
make stop
```

## Phase 9: Knowledge Sedimentation

Goal: make knowledge the moat, not the harness.

### Work

Implement knowledge deltas:

```text
knowledge-deltas.json
docs/knowledge/opensku/
scripts/opensku/ingest_knowledge_deltas.py
evals/opensku/scorers/knowledge_delta_quality.py
```

Phase 9 has two maturity levels:

1. Knowledge archive: accepted runs generate source-linked knowledge deltas and reusable patterns.
2. Knowledge reuse: later live runs consume selected patterns, record the injected pattern IDs, and promote maturity only after successful reuse.

Knowledge delta schema:

```json
{
  "id": "kd_001",
  "type": "decision | guideline | pitfall | process | model",
  "maturity": "draft | verified | proven",
  "scope": "category | channel | claim | experiment | workflow",
  "statement": "string",
  "source_case_id": "string",
  "source_run_id": "string",
  "evidence_ids": [],
  "decay_check": "string"
}
```

Knowledge injection schema:

```json
{
  "injected_knowledge_patterns": [
    {
      "id": "kp_001",
      "type": "pitfall | process | decision | guideline | model",
      "maturity": "draft | verified | proven",
      "stage_match": "idea_only | supplier_sample | pre_launch_test | soft_launch | scale_iterate | all",
      "occurrence_count": 1,
      "statement": "string",
      "source_pattern_file": "docs/knowledge/opensku/patterns.json"
    }
  ]
}
```

Knowledge selection rules:

- Select 3 to 5 patterns per run.
- Prefer stage match, then risk tag match, then higher occurrence count, then higher maturity.
- Never inject the whole knowledge base into the prompt.
- Record selected pattern IDs in run evidence.
- Keep final artifact lists filenames-only; do not add guessed counts or pattern commentary to final prose.

Maturity promotion rules:

```text
draft -> verified:
  pattern was injected into a later live run and that run passed validators/scoring.

verified -> proven:
  pattern was reused successfully across at least two stages or three accepted live runs.

any -> deprecated:
  pattern conflicts with a newer accepted run, stale data boundary, or current project contract.
```

### Acceptance

- at least 20 knowledge deltas generated from benchmark/live runs.
- each delta has source case/run.
- no delta claims unsupported private metrics.
- at least 5 patterns are available for reuse.
- at least 1 real live run injects selected knowledge patterns.
- the live run evidence records `injected_knowledge_patterns`.
- injected knowledge does not cause artifact validator or final-response contract failures.
- at least 1 injected pattern can be promoted from `draft` to `verified` by a later successful live run.
- docs explain knowledge maturity and decay.

### Validation Commands

```bash
uv run python scripts/opensku/ingest_knowledge_deltas.py --runs docs/progress/runs
uv run python evals/opensku/scorers/knowledge_delta_quality.py --knowledge docs/knowledge/opensku
uv run --project backend python evals/opensku/run_live_agent_validation.py --case evals/opensku/cases/<case>.json --knowledge-dir docs/knowledge/opensku
```

### Design References

```text
docs/research/opensku-agent-loop-research-notes.md
docs/research/opensku-terminology.md
docs/adr/0002-knowledge-is-execution-memory-not-wiki.md
docs/adr/0003-live-eval-contracts-are-release-gates.md
```

## Phase 10: Documentation And Demo Package

Goal: make the project inspectable by recruiters/interviewers and runnable by future maintainers.

### Work

Update:

```text
README.md
docs/ecom-launch/USER_MANUAL.md
docs/data/open-data-map.md
docs/evals/opensku-eval-harness.md
docs/demo/opensku-demo-script.md
docs/demo/opensku-real-run-report.md
```

### Demo Assets

At least one complete demo case should include:

```text
prompt
uploaded fixtures
final answer
artifact bundle
eval report
UI screenshots
run log
known limitations
```

### Acceptance

- README has quick start and honest status.
- demo script can be followed by a reviewer.
- docs distinguish built, demo, lab, planned.
- no resume-only language in public README.
- no unsupported production claims.

## Phase 11: Full Verification Gate

Goal: prove the entire project works.

### Required Commands

Backend:

```bash
cd backend
uv run pytest tests/test_ecom_launch_contract.py \
  tests/test_lead_agent_skills.py \
  tests/test_subagent_skills_config.py \
  tests/test_subagent_prompt_security.py \
  tests/test_opensku_artifact_validators.py \
  tests/test_opensku_replay_golden.py -q
```

Frontend:

```bash
cd frontend
pnpm typecheck
pnpm test -- tests/unit/components/workspace/ecom-launch
pnpm test:e2e -- tests/e2e/agent-chat.spec.ts tests/e2e/artifact-preview.spec.ts tests/e2e-real-backend/opensku-real-backend-render.spec.ts
```

Eval:

```bash
uv run python evals/opensku/validate_cases.py
uv run python evals/opensku/run_eval.py --cases evals/opensku/cases --mode deterministic
uv run python evals/opensku/run_eval.py --cases evals/opensku/cases --mode judge
uv run --project backend python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --live-run docs/progress/runs/<YYYY-MM-DD>/<accepted-live-run> \
  --decision-gate \
  --report-name <release-candidate-decision-gate>
```

Live:

```bash
uv run python scripts/opensku/run_live_suite.py --cases evals/opensku/cases/live-required.txt
```

### Final Acceptance

Final completion requires:

- all required commands pass.
- live suite has 10 completed runs.
- every live run has a progress log.
- deterministic eval pass rate >= 95%.
- expected-decision gate passes for the release-candidate live run set, or every mismatch is explicitly triaged with a benchmark-case correction or agent taxonomy fix.
- no forbidden metric leakage.
- no missing required artifacts.
- UI screenshots exist for at least 3 successful cases.
- final docs updated.
- known limitations documented.

## 7. Implementation Order

Recommended execution order:

1. Phase 0: baseline audit.
2. Phase 1: data map.
3. Phase 2: case schema.
4. Phase 3: artifact validators.
5. Phase 4: agent contract hardening.
6. Phase 5: offline eval harness.
7. Phase 6: live agent runner.
8. Phase 7: replay regression.
9. Phase 8: UI productization.
10. Phase 9: knowledge sedimentation.
11. Phase 10: docs and demo package.
12. Phase 11: full verification gate.

Do not start UI polish before artifact schemas and validators exist. Otherwise the UI will decorate unstable outputs.

Do not start full live suite before benchmark cases validate. Otherwise failures will be noisy and hard to interpret.

Do not mark eval complete before at least one real live run has produced artifacts and passed validators. Otherwise evals are disconnected from product reality.

## 8. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Dataset download is too large | slow local work | use small sampled fixtures first, document full-data path |
| Kaggle access requires manual token | blocks automation | support URL/manual placement and document setup |
| Live model costs too much | incomplete validation | cap case count per milestone, but final live suite still required |
| Agent run is nondeterministic | flaky eval | deterministic validators plus multiple live runs |
| Public pages block fetch | weak public signal | use benchmark fixtures and mark fetch limitation |
| Agent fabricates private metrics | trust failure | deterministic forbidden metric scorer blocks release |
| UI over-focuses on War Room | product looks decorative | first-viewport stage/decision/evidence panels |
| Knowledge deltas become generic | no moat | require source case/run/evidence and maturity |

## 9. Commands Cheat Sheet

Existing commands:

```bash
cd backend && uv run pytest tests/test_ecom_launch_contract.py -q
cd frontend && pnpm typecheck
cd frontend && pnpm test
cd frontend && pnpm test:e2e
make dev-daemon
make stop
```

Commands to add:

```bash
uv run python evals/opensku/validate_cases.py
uv run python evals/opensku/run_eval.py --cases evals/opensku/cases --mode deterministic
uv run python scripts/opensku/run_live_agent_case.py --case <case.json>
uv run python scripts/opensku/run_live_suite.py --cases evals/opensku/cases/live-required.txt
```

## 10. Final Review Checklist

Before calling the project complete:

- [x] Git status reviewed and unrelated dirty files identified.
- [x] Dataset docs completed.
- [x] 30 benchmark cases validate.
- [x] Artifact validators pass golden and broken fixtures.
- [x] Live runner executes the real agent path.
- [x] 10 live runs completed for RC2, two per launch stage.
- [x] Live run logs and artifacts exist under `docs/progress/runs/`.
- [x] Semantic release-candidate eval report generated: `PASS 530/530`.
- [x] UI screenshot captured: `docs/progress/screenshots/2026-06-28-opensku-war-room.png`.
- [x] Known limitations documented in reviewer docs and progress logs.
- [x] No fake private metrics or unsupported claims are allowed by contract, validators, and decision gates.
- [ ] README, eval docs, knowledge docs, and demo guide pass final consistency review.
- [ ] Final backend/eval regression sweep passes after the last docs/UI edits.
- [ ] Final frontend regression sweep passes after the last UI edit.
- [ ] `git diff --check` passes.
