# Commerce Case Agent — Real DeepSeek V4 Preflight

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: implemented and verified with fresh official requests
> Successful provider requests: `3`
> Successful-request tokens: `160` total (`127` input, `33` output)

## Outcome

Commerce model and Agent tests now have a fail-closed real-model gate. The gate does not trust the configured `deepseek-reasoner` alias. It makes a fresh request to the official DeepSeek endpoint and requires the provider response itself to expose an explicit `deepseek-v4...` model identity before any downstream model test may pass.

Implemented:

- `backend/app/commerce/evaluation/real_model_preflight.py`;
- immutable `RealModelPreflightResult` and version contracts;
- explicit `passed` and four required `blocked_*` statuses;
- official endpoint and approved provider-class validation;
- strict DeepSeek V4-family identity matching;
- a unique per-run request nonce plus an exact versioned response marker;
- LangChain response caching and SDK retries explicitly disabled;
- request/response ID, model identity, fingerprint, token, latency, retry, stop-reason and version capture;
- request-nonce and response-content SHA-256 without persisting Prompt or response prose;
- secret redaction and no API-key persistence;
- immutable one-file-per-run local audit records;
- deterministic provider-error classification;
- a `real_model` Pytest marker and live test that fails rather than skips;
- a CLI entry point through `python -m app.commerce.evaluation.real_model_preflight`.

Audit records are written to:

```text
.deer-flow/commerce/evaluation/real-model-preflight/
```

They are runtime evidence and remain outside Git.

## Fail-closed states

```text
blocked_real_model_unavailable
blocked_real_model_identity_unverified
blocked_real_model_quota_exhausted
blocked_real_model_auth_failed
```

The gate never substitutes another model, retries through the SDK, replays a historical response, reads a cached response or treats a skipped test as a pass.

## TDD evidence

The first deterministic test run failed during collection because the target module did not exist:

```text
ModuleNotFoundError: No module named 'app.commerce.evaluation.real_model_preflight'
exit code: 2
```

After the initial implementation, strict telemetry validation exposed a missing response-content hash in the deterministic test fixture. That fixture was corrected without weakening the production validator.

## Deterministic verification

Command:

```text
cd backend
.venv/bin/pytest -q tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py
```

Result:

```text
126 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static verification:

```text
.venv/bin/ruff check \
  app/commerce/evaluation \
  tests/commerce/evaluation \
  tests/commerce/test_package_boundary.py

All checks passed
exit code: 0
```

## Fresh real-model verification

The first sandboxed request could not reach the provider and was persisted as:

```text
blocked_real_model_unavailable
error_code: APIConnectionError
```

It was not converted to a pass. After network permission was granted, two independent initial official requests passed. Both returned:

```text
configured alias: deepseek-reasoner
configured model: deepseek-reasoner
actual model identity: deepseek-v4-flash
provider class: deerflow.models.patched_deepseek:PatchedChatDeepSeek
endpoint: https://api.deepseek.com/v1
input tokens: 33
output tokens: 11
total tokens: 44
request attempts: 1
retries: 0
stop reason: stop
```

Observed initial successful latencies were approximately `881 ms` and `889 ms`. Each request had a distinct provider request/response ID and immutable audit file.

The final hardened version was then tested with a unique request nonce, response caching disabled and SDK retries disabled. It returned:

```text
actual model identity: deepseek-v4-flash
input tokens: 61
output tokens: 11
total tokens: 72
latency: approximately 1066 ms
request attempts: 1
retries: 0
stop reason: stop
response marker: exact match (content stored only as SHA-256)
```

Final live command:

```text
cd backend
.venv/bin/pytest -q -s tests/commerce/evaluation/test_real_model_preflight_live.py
```

Final result:

```text
1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

## Scope boundary

This proves that the project can currently reach and verify the required real DeepSeek V4 model with mandatory telemetry. It does **not** prove Commerce Agent behavior: Semantic LLM candidates, Lead Agent, Path Agents, Verification, Goal Loop, Gold Case Agent E2E and experiments are not implemented yet and therefore have not been tested.

## Next

The next model-backed feature may now be implemented behind this gate. The immediate candidate is the low-confidence Semantic Mapper suggestion layer, where DeepSeek V4 may propose mappings but can never auto-confirm them. Deterministic multi-seller Peer Cohort and persistence work can continue independently without model calls.
