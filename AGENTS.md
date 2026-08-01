# DeerFlow Agent Instructions

## Project Identity

DeerFlow 2.0 is the LangGraph-based agent runtime used by this repository. The product exposes two independent ecommerce agents:

- **EcomLaunch**: public-evidence-driven validation before a product launch.
- **Store Operator**: conversational analysis after launch; users upload CSV/XLSX files and ask questions in Chinese.

They are separate entry points. Do not add an automatic handoff, shared case lifecycle, or a mandatory cross-agent workflow unless the product decision changes explicitly.

**Key custom additions**: `agents/ecom-launch/`, `agents/store-operator/`, `skills/custom/ecom-launch/`, `skills/custom/store-data-analysis/`, and their matching frontend workspace components.

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
│   ├── app/store_operator/     # Safe CSV/XLSX inspection and read-only SQL tools
│   └── tests/                  # Backend tests
├── frontend/                   # Next.js frontend
│   └── src/components/workspace/
│       ├── ecom-launch/         # EcomLaunch workspace UI
│       └── store-operator/      # Store Operator War Room
├── agents/                     # Custom agent definitions
│   ├── ecom-launch/            # EcomLaunch Agent
│   └── store-operator/         # Store Operator (SOUL.md + config.yaml)
├── skills/                     # Agent skills
│   ├── public/                 # Built-in skills (22 total)
│   └── custom/
│       ├── ecom-launch/         # EcomLaunch skill
│       └── store-data-analysis/ # Store Operator analysis rules
├── config.yaml                 # Main configuration (generate from config.example.yaml)
└── extensions_config.json      # MCP servers + skills config
```

## EcomLaunch Architecture

Multi-agent system using **Orchestrator-subagent** pattern:

```
Launch Director (lead agent)
├── market-scout       # Public market signals, competitors, pricing
├── voc-miner          # Customer voice, reviews, pain points
├── offer-architect    # Positioning, validation hypotheses
├── asset-studio       # Listing copy, content hooks, scripts
└── evidence-checker   # Evidence audit, claim validation
```

**Subagent config location**: `config.yaml → subagents.custom_agents`

## Store Operator Architecture

Store Operator uses DeerFlow's native configuration rather than a business-specific state machine:

```
Store Operator (parent agent)
├── store_inspect_data  # Discover tables, fields, grain, dates, and quality risks
├── store_query_data    # Deterministic read-only DuckDB calculations
└── task (optional)
    ├── explore         # Multi-file/schema exploration
    ├── analyst         # One bounded calculation or decomposition
    └── verifier        # Independent recomputation of a high-impact result
```

- Simple questions must be answered directly with tools; do not force Subagent usage.
- The parent chooses zero or more specialists at runtime. There is no mandatory Explore → Analyst → Verifier sequence.
- Numeric claims must come from `store_query_data`, not sample-row mental math.
- Missing metrics must be reported as unavailable; never invent exposure, clicks, ad spend, stock, profit, or other absent fields.
- The War Room is a secondary view. Character state is derived only from real `task` tool calls and completion messages.

## Critical Configuration

1. Copy `config.example.yaml` → `config.yaml` in project root
2. Set API keys in `.env` (`DEEPSEEK_API_KEY`, etc.); never commit or print them
3. Run `make doctor` to verify setup

**Config hot-reload**: Model/skill/tool changes take effect on next request. Infrastructure changes (sandbox, channels) require restart.

**Real-model gate**: Agent/LLM acceptance tests use a fresh `deepseek-v4-flash` request with `max_retries: 0`. Mock, replay, cached output, or provider/model fallback cannot be counted as passing evidence. Deterministic unit tests may still mock their own local boundaries.

## Implementation Priorities

- Prefer DeerFlow configuration (`config.yaml`, agent `SOUL.md`, Skill, Tool, Subagent profile) over product-specific orchestration code.
- Optimize for the observed user-facing answer and trace quality. Do not add a Harness, Case schema, keyword scope, or fixed workflow without a demonstrated need.
- Use TDD for risky behavior and bug fixes when practical. Configuration, prompts, documentation, and focused UI work may be implemented directly, followed by risk-matched regression tests.
- Keep the primary Store Operator experience as a compact Chinese chat. Do not turn the main page into a dense dashboard.

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
└── launch-calendar.csv       # 7-day validation plan
```

## Common Pitfalls

- `config.yaml` must be in project root, not `backend/`
- Custom agents go in `agents/<name>/`, not `backend/packages/`
- Skills go in `skills/custom/`, not `skills/public/`
- Store uploads are limited to CSV/XLSX and must be queried through the allowlisted read-only tools
- Store Operator must inspect row grain before counting orders or summing order-level amounts
- Subagent prompts must include evidence boundaries and forbidden invented metrics
- Frontend War Room state comes from real `task` tool-call history; never simulate busy agents
