# OpenSKU Agent Instructions

## Project Identity

OpenSKU is a LangGraph-based AI launch team with two independent top-level product agents: **OpenSKU Launch Team** for ecommerce research and launch workflows, and **Growth Analyst** for conversational analysis of uploaded CSV/XLSX business and content-performance data. The internal compatibility IDs remain `ecom-launch` and `data-inspector`.

**Key custom additions**:

- OpenSKU Launch Team: `agents/ecom-launch/` + `skills/custom/ecom-launch/` + `frontend/src/components/workspace/ecom-launch/`
- Growth Analyst: `agents/data-inspector/` + `skills/custom/{sql-queries,cohort-analysis,ab-test-analysis}/` + `backend/app/data_inspector/`

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
opensku/
├── backend/                    # Python backend (FastAPI + LangGraph)
│   ├── packages/harness/       # Compatibility agent harness
│   ├── app/gateway/            # FastAPI Gateway API
│   ├── app/data_inspector/     # Deterministic CSV/XLSX analysis tools
│   └── tests/                  # Backend tests
├── frontend/                   # Next.js frontend
│   └── src/components/workspace/ecom-launch/  # Launch Crew panel
├── agents/                     # Repository-defined top-level agents
│   ├── ecom-launch/            # OpenSKU Launch Team compatibility ID
│   └── data-inspector/         # Growth Analyst compatibility ID (SOUL.md + config.yaml)
├── skills/                     # Agent skills
│   ├── public/                 # Built-in skills (22 total)
│   └── custom/
│       ├── ecom-launch/         # OpenSKU launch skill (compatibility path)
│       ├── content-calibration/ # Legacy skill retained in the tree; not loaded by the current top-level agents
│       ├── sql-queries/         # PM Skills SQL analysis workflow
│       ├── cohort-analysis/     # Cohort retention/repeat/adoption method
│       └── ab-test-analysis/    # Binary-conversion experiment method
├── config.yaml                 # Main configuration (generate from config.example.yaml)
└── extensions_config.json      # MCP servers + skills config
```

## OpenSKU Launch Team Architecture

Multi-agent system using **Orchestrator-subagent** pattern:

```
Launch Director (lead agent)
├── market-voc-researcher  # Market signals, competitors, pricing, reviews, VOC
├── offer-architect        # Positioning, pricing hypotheses, validation experiments
└── asset-studio           # Listing copy, content hooks, scripts
```

The `evidence-checker` definition and generic Harness support are retained for
future use, but the OpenSKU Launch Team currently excludes it from its allowlist and complete-Pack
delivery contract.

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

## OpenSKU Launch Team Deliverables

Default `validate-launch` workflow outputs:

```
/mnt/user-data/outputs/
├── launch-war-room.html      # Dashboard (self-contained HTML)
├── evidence-ledger.json      # Evidence audit (JSON array)
├── competitor-table.csv      # Competitor analysis
├── positioning-brief.md      # Positioning strategy
├── listing-pack.md           # Product listing copy
├── content-pack.md           # Content hooks & scripts
└── launch-calendar.csv       # 7-day validation plan
```

## Common Pitfalls

- `config.yaml` must be in project root, not `backend/`
- Custom agents go in `agents/<name>/`, not `backend/packages/`
- Skills go in `skills/custom/`, not `skills/public/`
- Growth Analyst tools stay in `backend/app/data_inspector/` and are registered through `config.yaml`; do not add an app import to the Harness.
- Keep the Growth Analyst SOUL short and use the original `pm-data-analytics` Skills for SQL, cohort, and A/B analysis.
- Keep deterministic file inspection, read-only SQL execution, and A/B statistics in `backend/app/data_inspector/`; retain the upstream MIT attribution and license files.
- Growth Analyst currently analyzes CSV/XLSX only; its application tools remain bounded to uploaded data and read-only queries.
- Subagent prompts must include evidence labeling rules and forbidden metrics
- Frontend Launch Crew panel reads from `ThreadState.artifacts` and `Subtask` context
