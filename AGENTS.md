# OpenSKU Agent Instructions

## Critical Real-Model Test Policy

- Any test path that invokes an LLM or validates Agent behavior must use a fresh request to the real DeepSeek V4 model.
- Mock, fake, stub, replayed, cached, or alternate-model responses cannot be used as passing evidence for Agent, Verification, Skill, Eval, end-to-end, or release-gate tests.
- Pure deterministic tests for data, metrics, state transitions, repositories, events, budgets, and policies remain model-free; they must not use a fake model to stand in for an Agent call.
- The configured local alias is currently `deepseek-reasoner`, but a preflight must verify the actual server-side model identity is DeepSeek V4 before Agent tests run.
- Do not silently fall back to another model or DeepSeek version.
- If DeepSeek V4 is unavailable, its identity cannot be verified, authentication fails, or quota/funds are exhausted, stop Agent testing and report a blocked status instead of skipping or passing the test.
- Record actual model identity, provider request ID, token usage, latency, retry count, and configuration versions for every real-model evaluation run.

## Project Identity

OpenSKU is an open-source AI launch loop for ecommerce SKU decisions. It helps merchants, ecommerce operators, and indie sellers turn rough product ideas, listing URLs, competitor links, public signals, uploaded context, and post-test feedback into an evidence-backed Go/Pivot/Hold/Kill/Scale decision loop.

The runtime is a LangGraph-based agent harness extended with **EcomLaunch Agent** for adaptive SKU launch validation, promotion replanning, knowledge capture, and content calibration. Public positioning should lead with OpenSKU and the ecommerce launch-loop workflow, not the underlying harness.

**Key custom addition**: `agents/ecom-launch/` + `skills/custom/ecom-launch/` + `frontend/src/components/workspace/ecom-launch/`

## Quick Commands

```bash
# Setup (first time)
make setup              # Interactive wizard → generates config.yaml + .env

# Development
make dev                # Start all services (gateway:8001, frontend:3000, nginx:2026)
make install            # Install all dependencies (backend + frontend)

# Backend only
cd backend && make dev  # Gateway API only (port 8001)
cd backend && make test # Run all backend tests
cd backend && make lint # Lint with ruff

# Frontend only
cd frontend && pnpm dev      # Next.js dev server
cd frontend && pnpm test     # Unit tests (vitest)
cd frontend && pnpm test:e2e # E2E tests (playwright)
cd frontend && pnpm typecheck # Type check

# Production
make up                 # Docker production (localhost:2026)
make down               # Stop production containers
```

## Architecture

```
deer-flow/
├── backend/                    # Python backend (FastAPI + LangGraph)
│   ├── packages/harness/       # deerflow-harness (core agent framework)
│   ├── app/gateway/            # FastAPI Gateway API
│   └── tests/                  # Backend tests
├── frontend/                   # Next.js frontend
│   └── src/components/workspace/ecom-launch/  # Launch Crew panel
├── agents/                     # Custom agent definitions
│   └── ecom-launch/            # EcomLaunch Agent (SOUL.md + config.yaml)
├── skills/                     # Agent skills
│   ├── public/                 # Built-in skills (22 total)
│   └── custom/
│       ├── ecom-launch/         # EcomLaunch skill (validate-launch workflow)
│       └── content-calibration/ # Content calibration skill (calibrate-content workflow)
├── config.yaml                 # Main configuration (generate from config.example.yaml)
└── extensions_config.json      # MCP servers + skills config
```

## OpenSKU / EcomLaunch Architecture

Multi-agent system using an **Orchestrator-subagent** pattern:

```
Launch Director (lead agent)
├── market-scout       # Public market signals, competitors, pricing
├── voc-miner          # Customer voice, reviews, pain points
├── offer-architect    # Positioning, validation hypotheses
├── asset-studio       # Listing copy, content hooks, scripts
└── evidence-checker   # Evidence audit, claim validation
```

**Subagent config location**: `config.yaml → subagents.custom_agents`

## Critical Configuration

1. Copy `config.example.yaml` → `config.yaml` in project root
2. Set API keys in `.env` (OPENAI_API_KEY, etc.)
3. Run `make doctor` to verify setup

**Config hot-reload**: Model/skill/tool changes take effect on next request. Infrastructure changes (sandbox, channels) require restart.

## Testing

```bash
# Backend (from backend/)
make test                    # All tests
make test-blocking-io        # Strict blocking IO gate
PYTHONPATH=. uv run pytest tests/test_<feature>.py -v  # Single test

# Frontend (from frontend/)
pnpm test                    # Unit tests
pnpm test:e2e                # E2E tests
```

## Code Style

- **Backend**: Python 3.12+, ruff (line length 240), double quotes
- **Frontend**: TypeScript, ESLint + Prettier, Tailwind CSS

## EcomLaunch Deliverables

Default `validate-launch` workflow outputs:

```
/mnt/user-data/outputs/
├── launch-war-room.html      # Dashboard (self-contained HTML)
├── evidence-ledger.json      # Evidence audit (JSON array)
├── competitor-table.csv      # Competitor analysis
├── positioning-brief.md      # Positioning strategy
├── listing-pack.md           # Product listing copy
├── content-pack.md           # Content hooks & scripts
└── launch-calendar.csv       # adaptive validation sprint
```

The professional deliverable is the evidence-backed launch loop: stage diagnosis, Launch Decision Pack, promotion replan, and next experiment. The War Room is the visual demo layer, not the core value by itself.

## Common Pitfalls

- `config.yaml` must be in project root, not `backend/`
- Custom agents go in `agents/<name>/`, not `backend/packages/`
- Skills go in `skills/custom/`, not `skills/public/`
- Subagent prompts must include evidence labeling rules and forbidden metrics
- Frontend Launch Crew panel reads from `ThreadState.artifacts` and `Subtask` context
