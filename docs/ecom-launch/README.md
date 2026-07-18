# OpenSKU / EcomLaunch Manual Demo Materials

This folder contains manual demo materials for OpenSKU's EcomLaunch agent workflow.
For final reviewer-facing evidence, start with:

```text
docs/demo/opensku-reviewer-guide.md
docs/demo/opensku-final-evidence-matrix.md
evals/opensku/reports/2026-06-28-rc2-10run-decision-gate/summary.md
```

The goal is to prove the core SKU launch-loop workflow before building a dedicated conversational OpenSKU entry:

```text
existing agent chat
-> Ultra mode
-> ecom-launch skill
-> ask_clarification when the launch brief is too incomplete
-> ecommerce custom subagents
-> public web search/fetch
-> uploaded feedback or stage context when available
-> files under /mnt/user-data/outputs
-> present_files artifacts
```

## Files

- `demo-brief.portable-coffee-tumbler.json`: recommended demo input.
- `demo-run-2026-06-09.md`: first local smoke-run record and validation notes.
- `manual-run-prompt.md`: prompt to paste into an Ultra-mode DeerFlow chat.
- `subagents.ecom-launch.yaml`: copyable `subagents:` config block for local `config.yaml`.

## Local Setup

1. Copy `config.example.yaml` to `config.yaml` if you have not already.
2. Copy the contents of `subagents.ecom-launch.yaml` into `config.yaml`.
3. Ensure `skills/custom/ecom-launch/SKILL.md` exists.
4. Install the local browser runtime once if you use the default local `web_fetch`: `cd backend && uv run playwright install chromium`.
5. Restart the backend if it is already running.
6. Start a new chat in Ultra mode so `subagent_enabled=true`.
7. Paste `manual-run-prompt.md`.

The default `web_fetch` provider is local and free: it uses fast `httpx` fetching first, then falls back to local Playwright/Chromium rendering for public JavaScript pages. It does not use paid crawler APIs and must not be used to bypass login walls, CAPTCHA, anti-bot systems, or private ecommerce dashboards.

## Expected Artifacts

The run should create and present a Launch Decision Pack as the current loop snapshot:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

Optional but useful:

```text
review-insights.json
risk-notes.md
source-list.md
launch-state.json
promotion-replan.md
knowledge-deltas.json
```

`launch-calendar.csv` is the default next-sprint artifact. It may describe a 3, 7, 14, or 30-day loop depending on whether the user has only an idea, a supplier/sample, pre-launch content feedback, soft-launch data, or scale-stage data. Seven days is only the demo default.

## Manual Demo Acceptance Criteria

The artifact-first manual path is successful when:

- the agent reads or follows the `ecom-launch` skill
- Ultra mode exposes the ecommerce subagents through the `task` tool
- the final deliverables are saved under `/mnt/user-data/outputs`
- `present_files` is called
- the final recommendation is framed as Go, Pivot, Hold, Kill, or Scale when appropriate
- the agent diagnoses the SKU launch stage before recommending the next loop
- `evidence-ledger.json` distinguishes observed public evidence from estimates
- no private merchant metrics are invented
- `evidence-ledger.json` is parseable JSON
- CSV artifacts are parseable and every row has the declared column count
- validation plans use lightweight no-backend signals by default, not private platform metrics
- uploaded feedback or early-launch data triggers promotion replanning instead of a static report

## Notes

Use public data only. Do not bypass login walls, CAPTCHA, anti-bot systems, or private ecommerce dashboards.

If a source cannot provide a private metric such as GMV, CTR, CVR, ROI, ad spend, refund rate, or repeat purchase rate, mark the metric as unavailable. For users without backend data, default to validation signals such as sample feedback, comment/save/share intent, inquiry count, preorder interest, creator response quality, repeated objections, and manual price-acceptance checks. If the user uploads real backend or test data, use it as `uploaded_real`, explain what changed, and adjust the next promotion or experiment loop.
