# Copilot onboarding instructions for OpenSKU

Use the closest `AGENTS.md` as the primary repository guidance. This file gives a short product and validation overview for GitHub Copilot.

## Repository summary

OpenSKU is a full-stack AI launch team for ecommerce product research, evidence-governed decision making, launch-asset production, and uploaded business-data analysis.

- Backend: Python 3.12+, FastAPI, LangGraph, agent tools, skills, memory, and sandbox integrations.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, and a Phaser War Room.
- Product agents: OpenSKU Launch Team, specialist launch agents, and Growth Analyst.
- Local unified endpoint: `make dev` at `http://localhost:2026`.
- Frontend-only endpoint: `cd frontend && pnpm dev` at `http://localhost:3000`.

Some internal import paths, environment variables, and runtime directories retain upstream compatibility identifiers. Do not rename those mechanically. A migration must update imports, tests, stored state, Docker resources, and documentation together.

## Common commands

```bash
# Setup
make setup
make install
make doctor

# Full development stack
make dev

# Backend
cd backend
make lint
make test
make test-blocking-io

# Frontend
cd frontend
pnpm typecheck
pnpm test
pnpm lint
pnpm build
pnpm test:e2e
```

## Contribution rules

- Preserve unrelated user changes in a dirty worktree.
- Use `rg` for search and `apply_patch` for edits.
- Fix root causes and add regression coverage proportional to risk.
- Do not weaken assertions, hide errors, or increase retries to mask failures.
- Never commit secrets, `.env` files, local databases, caches, model files, or private datasets.
- Do not change the internal IDs `ecom-launch` or `data-inspector` without an explicit compatibility migration.
- User-visible product copy should use the OpenSKU brand and the existing English/Chinese translation system.
- Frontend visual changes require browser verification in addition to type, unit, lint, and build checks.
- Required upstream copyright and license text must remain intact; see `THIRD_PARTY_NOTICES.md`.
