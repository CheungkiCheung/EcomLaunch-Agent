# Commerce Eval, Experiment and Skill Evolution

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: Evaluator, controlled experiments, Holdout and Candidate registry complete; Human promotion pending

> Update: this document preserves the `1.2.0` three-case tuning milestone. The current Candidate is `1.3.0`, based on the later four-case threshold-hardening experiment documented in `2026-07-19-commerce-four-gold-threshold-tuning-skill-v1.3.md`.

## Outcome

Commerce tuning is now an auditable release process rather than manual prompt editing:

```text
frozen Gold Case + frozen versions
→ fresh DeepSeek V4 generation
→ deterministic evaluator
→ fresh Semantic Evaluator
→ repeated Control/Candidate experiment
→ Pareto decision
→ immutable Skill Candidate
→ security scan + offline/holdout
→ Shadow
→ Human Review
→ Promotion / rollback
```

At this milestone, `commerce-semantic-evaluator@1.1.0` rejected unsupported certainty including `dominant driver`, `root cause`, `further confirmed`, `核心原因`, `主因` and `进一步验证/证实`. It has since advanced to `1.2.0` with the deterministic `unsupported-action-threshold` gate. `GC-FULFILLMENT-001` also has the explicit hard-gate reason `no-transit-causal-certainty`. If a failed judge response also emits `all-gates-passed`, the contradictory success code is removed and `inconsistent-success-code-removed` is recorded.

## Real tuning history

The failed or held experiments are intentionally preserved because they explain the tuning decisions.

### Micro experiment — held

```text
Experiment: exp_4d14ee6a77a74c3eb7be5d5c278d6cd8
Control:   2/2 passed
Candidate: 2/2 passed
Decision:  hold
Reason: Candidate total Token cost was about 13.2% higher than Control,
        outside the 10% cost envelope.
```

This run also exposed causal wording and a Semantic Judge blind spot. The acceptance rules were strengthened; the previous output was not grandfathered into PASS.

### Final three-case Holdout — candidate promotion recommendation

```text
Experiment: exp_6b9fe42117b74d30997800495b8eca61
Cases: GC-FULFILLMENT-001, GC-REVIEW-002, GC-CAPABILITY-003
Repetitions: 2 per case and variant

Candidate:
  passed: 6/6
  hard-gate failures: 0
  mean total tokens: 2006.5
  mean latency: 4995.36 ms

Control:
  passed: 3/6
  hard-gate failures: 3
  mean total tokens: 2369.5
  mean latency: 7474.49 ms

Decision: promote_candidate
```

Candidate reduced mean Token use by about `15.3%` and mean Latency by about `33.2%` while improving the hard-gate pass rate. The definition binds:

```text
candidate_skill_version=commerce-diagnostic-synthesis@1.2.0-candidate
candidate_content_sha256=5c788c54cda3717ba859c8ca2f5cea280ef04255bd0ec6185b69bc20fa9fa53b
actual_model_identity_prefix=deepseek-v4
provider_retry=0
```

Reproduction command persisted in the Experiment Definition:

```text
cd backend
PYTHONPATH=. .venv/bin/python -m app.commerce.evaluation.run_experiment \
  --case-key GC-FULFILLMENT-001 \
  --case-key GC-REVIEW-002 \
  --case-key GC-CAPABILITY-003 \
  --repetitions 2
```

The accepted experiment contains 24 unique model Provider Request IDs, covering one generation and one fresh Semantic Evaluation for each of 12 runs:

```text
a5b0baed-4278-430e-bd01-2b981e8ce458
597cd8bd-cde6-4637-8ed8-71921fdbf0f9
a2f849ea-4a00-435f-b697-09e5fd6e5cae
46a2ea7d-65bf-4d05-8c51-4313cd26801a
8f028e4a-ca95-4d92-8fb6-c59c11fba1fe
a7894d4a-1d6f-4fce-9b7d-c01a4ed2f450
0f4e1a91-46d4-448f-9fb6-f6daf3dbddeb
b9069715-618f-492c-9319-95df68fdf3f4
3c17d096-6695-415e-8266-cb29e7c2ae48
ae60621a-85af-424b-9d76-c03b6410261b
d74d17dc-8181-4049-bdff-afe29cd51333
93549025-13f7-42b3-b066-7b9e8c23dad2
e92a00e5-a51d-4b35-a731-50e787a383d3
d586da0a-dbed-448c-86ce-39b9f3d40733
c477d5dc-4d40-4962-8563-76a00da4f20f
f8ed2202-8608-44f2-a889-0022dda06912
b0a8482c-75c6-4e1c-92f3-888da79b1342
d2b31b82-67b7-4204-b7ac-342ffbc87cc4
5e6f3fd6-b9bf-41b8-bdb9-a19050793c95
db04c4d4-7087-4825-8adb-7f761b40b1e7
c0dacbe9-fe23-450d-9e53-a90115e1c0af
692f5748-0767-4b05-a3a9-20a574a11c26
ea9c7513-2660-4364-b5ff-eb1104e555b6
85453324-45b0-494e-a18d-3acc1c8636aa
```

All report evidence records `deepseek-v4-flash`, a fresh request and retry `0`.

## Candidate state

The valid immutable Candidate is:

```text
candidate_id: skillcand_1ba91a22b7c7523e88e452ee58ed4375
skill: commerce-diagnostic-synthesis
base: 1.1.0
candidate: 1.2.0
content SHA-256: 5c788c54cda3717ba859c8ca2f5cea280ef04255bd0ec6185b69bc20fa9fa53b
source/offline experiment: exp_6b9fe42117b74d30997800495b8eca61
security scan: passed
regression: passed
holdout: passed
current status: shadow
```

The API reloads Experiment Definition/Report from the server, verifies the actual Candidate content hash, isolates Workspaces, stores the actor, and rejects client-owned status, hash or Active Pointer fields. Online Agents cannot edit the Active Skill.

## Deterministic verification

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/evaluation/test_real_model_preflight_contract.py \
  tests/commerce/evaluation/test_live_experiment_contracts.py \
  tests/commerce/evaluation/test_runner_experiment_skill.py \
  tests/commerce/evaluation/test_skill_shadow.py

45 passed, 1 unrelated LangGraph warning
exit code: 0
```

The experiment above was not rerun during the current documentation pass; its immutable Definition, per-run audits and Report are the evidence. A separate current fresh Preflight and Action Planner gate confirmed that the configured provider remains available.

## Known limits

- This historical experiment covers three Gold Cases. The later four-case synthesis/semantic gate passes; the unified four-case full Agent E2E remains pending.
- `promote_candidate` is an experiment recommendation, not a production release.
- Human Review has not happened; Active Pointer remains unchanged.
- Production rollback of an Active Skill has not yet been rehearsed.
- Cost values are Token/Latency telemetry, not a currency-spend claim.
