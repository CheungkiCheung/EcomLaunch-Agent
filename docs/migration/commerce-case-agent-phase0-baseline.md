# Commerce Case Agent Phase 0 Baseline

> Audit date: 2026-07-18  
> Branch: `feature/commerce-case-agent`  
> Archive branch: `archive/ecom-launch-pre-commerce-agent-20260718`  
> Archive commit: `9144237`

## 1. Purpose

This document freezes the migration baseline before Commerce domain implementation begins. It records provenance, feature isolation, reusable infrastructure, legacy boundaries, model-test restrictions, and verification evidence.

Phase 0 is intentionally limited. It does not delete OpenSKU/EcomLaunch, redesign the entire DeerFlow repository, or claim that the new Agent works.

## 2. Git and upstream provenance

| Item | Value |
|---|---|
| Current product branch | `feature/commerce-case-agent` |
| Pre-redesign archive branch | `archive/ecom-launch-pre-commerce-agent-20260718` |
| Pre-redesign snapshot | `9144237` |
| Local repository remote | `git@github.com:CheungkiCheung/EcomLaunch-Agent.git` |
| Official DeerFlow upstream | `https://github.com/bytedance/deer-flow` |
| Local squashed import root | `bf981732fdf49268d1bb80505b4096a883ff5921` |
| Official upstream HEAD observed on 2026-07-18 | `a028dfd5fb70bd6e26c7dbf9e89543c7c006f9a2` |

The local import root has no parent commit. Therefore the exact ByteDance DeerFlow SHA used for the original 2026-06-09 import is not recoverable from this Git history. The observed upstream HEAD is an audit reference, not a claim that the local tree is synchronized with that commit.

No `upstream` remote was added and no upstream code was merged during Phase 0.

## 3. Product namespace

New system names:

```text
Commerce Case Agent
backend/app/commerce/
tests/commerce/
frontend/src/.../commerce/
evals/commerce/
docs/commerce/
```

Core objects:

```text
Dataset
DataSource
Entity
Capability
Fact
MetricObservation
Evidence
Case
Hypothesis
Action
Approval
FollowUp
DomainEvent
```

Legacy `OpenSKU`, `EcomLaunch`, `LaunchCrew`, stage-decision, and artifact-pack types must not be imported into these new namespaces.

## 4. Feature isolation

Two fail-closed feature flags isolate the new system:

| Layer | Variable | Default | Responsibility |
|---|---|---:|---|
| Gateway | `COMMERCE_CASE_AGENT_ENABLED` | `false` | Controls future Commerce Router mounting |
| Frontend | `NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED` | `false` | Controls future Commerce Workspace entry |

The frontend flag cannot enable a backend route. Both must be explicitly true for the complete entry to be available.

Phase 0 implements and tests parsing only. Commerce routes and pages do not exist yet.

## 5. Reuse / Extend / Replace / Legacy matrix

| Existing area | Decision | Commerce use |
|---|---|---|
| LangGraph runtime, RunManager, StreamBridge | Reuse | Execute and observe long-running investigation runs |
| Checkpointer and run persistence | Reuse / Extend | Reuse infrastructure; add Commerce checkpoints and metadata |
| Sandbox and built-in tools | Reuse | Controlled file/data operations |
| Upload and artifact transport | Reuse / Extend | Reuse transport; add dataset manifests and typed Commerce outputs |
| Auth and approval primitives | Reuse / Extend | Reuse identity; add action policy and approval records |
| Token usage and tracing | Reuse / Extend | Add model identity, provider request ID and configuration versions |
| Loop detection middleware | Reuse / Extend | Keep generic safety; add Goal Loop stop conditions and budgets |
| Memory and Skills infrastructure | Reuse / Extend | Add layered Commerce memory and candidate-only evolution |
| Generic Thread / Message UI shell | Reuse / Extend | Keep transport and composer; introduce Case-first workspace |
| Fixed EcomLaunch five-role crew | Replace | Capability-driven 0–3 Path Agents |
| Go/Pivot/Hold/Kill/Scale stage workflow | Replace | Case lifecycle and action/follow-up outcomes |
| Artifact-first launch pack | Replace | Evidence, Hypothesis, Action and Follow-up records |
| Message-derived War Room state | Replace | Domain Event-driven views |
| OpenSKU benchmark and RC reports | Legacy | Historical evidence only; not a Commerce gate |
| OpenSKU knowledge promotion | Legacy reference | Inform candidate governance; do not migrate as Active Skill |
| Existing War Room art assets | Optional reuse | Visual inspiration only; roles and event semantics are replaced |

## 6. Legacy inventory

Read-only legacy areas:

```text
agents/ecom-launch/
skills/custom/ecom-launch/
evals/opensku/
scripts/opensku/
scripts/opensku_data/
data/opensku/
docs/ecom-launch/
docs/knowledge/opensku/
docs/demo/opensku-*.md
frontend/src/components/workspace/ecom-launch/
frontend/tests/unit/components/workspace/ecom-launch/
```

Rules:

- do not delete during the new system build;
- do not import legacy domain contracts into `app.commerce`;
- do not report old benchmark PASS values as Commerce Agent evidence;
- do not use old Replay, fake-model tests, or generated traces for a new release gate;
- preserve the archive branch as the authoritative recovery point.

## 7. Data baseline

The primary public dataset is Olist. The full downloaded dataset remains outside Git at:

```text
/tmp/olist-kaggle
```

The repository may contain only:

- dataset license and provenance documentation;
- schemas and data maps;
- deterministic fixture builders;
- minimal, reviewed Gold Case fixtures;
- expected facts, metrics and forbidden claims.

Full raw tables, generated databases and runtime outputs are excluded.

## 8. Real-model test baseline

The current configured alias is `deepseek-reasoner`, using DeepSeek's API endpoint. An alias is not proof of a server-side DeepSeek V4 identity.

Before any Commerce Agent behavior test, implement `real_model_preflight` that:

1. checks credentials without logging secrets;
2. sends a fresh minimal request;
3. captures actual model identity and provider request ID;
4. requires verifiable DeepSeek V4 identity;
5. records token usage, latency, retry and stop reason;
6. blocks on unavailable service, unverified identity, auth failure or exhausted quota;
7. never falls back to another model or response replay.

Until then, only deterministic Commerce tests may run.

Existing DeerFlow tests that use fake LLMs or recorded responses are not valid Commerce Agent acceptance evidence.

## 9. Phase 0 verification record

### Feature flag RED

```text
PYTHONPATH=. uv run pytest tests/test_commerce_feature_flag.py -v
```

Observed result before implementation:

```text
3 failed
reason: GatewayConfig had no commerce_case_agent_enabled field
```

Frontend RED:

```text
./node_modules/.bin/vitest run tests/unit/core/config/feature-flags.test.ts
```

Observed result before implementation:

```text
1 suite failed during import
reason: @/core/config/feature-flags did not exist
```

### Feature flag GREEN

Backend:

```text
3 passed, 1 unrelated LangChain pending-deprecation warning
```

Frontend:

```text
1 file passed
3 tests passed
```

These are deterministic configuration tests. No LLM, Agent, fake model, replay or model fee was involved.

### Static and compatibility baseline

Backend deterministic configuration and import-boundary tests:

```text
PYTHONPATH=. uv run pytest \
  tests/test_commerce_feature_flag.py \
  tests/test_gateway_docs_toggle.py \
  tests/test_harness_boundary.py -v

14 passed, 1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Backend changed-file lint:

```text
PYTHONPATH=. uv run ruff check \
  app/gateway/config.py \
  tests/test_commerce_feature_flag.py

All checks passed
exit code: 0
```

Frontend:

```text
targeted feature-flag tests: 3 passed
TypeScript typecheck: passed
changed-file ESLint: passed
```

Full frontend ESLint was also run to record the inherited baseline. It failed with five errors and two warnings, all under the Legacy EcomLaunch UI:

```text
frontend/src/components/workspace/ecom-launch/launch-crew-activity-model.ts
frontend/src/components/workspace/ecom-launch/war-room-canvas-stage.tsx
frontend/src/components/workspace/ecom-launch/war-room-page.tsx
```

These files were not modified because the new Commerce UI will use a new event-driven namespace. The failure is retained as a truthful legacy baseline rather than hidden or weakened.

Docker Compose parsing:

```text
docker/docker-compose-dev.yaml: valid; warned that local DEER_FLOW_ROOT is unset
docker/docker-compose.yaml: valid when required deployment paths are supplied with non-secret placeholders
```

Git whitespace validation:

```text
git diff --check
exit code: 0
```

### Suites intentionally not run

- Backend full suite: contains Fake LLM, Mock Agent and Replay-based tests. Those remain upstream/legacy infrastructure tests and cannot be counted under the real-model Commerce policy.
- Frontend full unit/E2E suites: contain mocked LangGraph/backend Agent flows. They may later be used for generic UI mechanics, but not as Commerce Agent acceptance evidence.
- Commerce Agent tests: not yet present, and `real_model_preflight` has not been implemented. No model request was attempted during Phase 0.
- Historical OpenSKU evaluators: frozen Legacy evidence only.

## 10. Phase 0 exit checklist

- [x] Archive branch and snapshot exist.
- [x] Commerce branch exists.
- [x] Official upstream and local import provenance are recorded.
- [x] Exact missing upstream-base SHA is disclosed instead of guessed.
- [x] Backend and frontend feature flags default to disabled.
- [x] Feature-flag parsing has deterministic RED/GREEN evidence.
- [x] Root, backend and frontend Agent instructions describe the Commerce system.
- [x] Legacy assets are preserved and excluded from Commerce release claims.
- [x] Static/type/lint baseline is recorded, including the inherited Legacy lint failure.
- [x] Working tree is committed at the Phase 0 boundary: `c561ca7`.

## 11. Next implementation point

Phase 1 begins with a failing package-boundary test:

```text
app.commerce can be imported
deerflow.* never imports app.commerce
```

Then create the minimal `app.commerce` package skeleton and proceed to typed IDs, enums, facts, metrics, evidence and frozen Gold Case contracts.
