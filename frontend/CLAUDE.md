# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenSKU Frontend is a Next.js 16 web interface for an AI agent system. It communicates with a LangGraph-based backend to provide thread-based AI conversations with streaming responses, artifacts, and a skills/tools system.

**Stack**: Next.js 16, React 19, TypeScript 5.8, Tailwind CSS 4, pnpm 10.26.2

## Commands

| Command                        | Purpose                                           |
| ------------------------------ | ------------------------------------------------- |
| `pnpm dev`                     | Dev server with Turbopack (http://localhost:3000) |
| `pnpm build`                   | Production build                                  |
| `pnpm check`                   | Lint + type check (run before committing)         |
| `pnpm lint`                    | ESLint only                                       |
| `pnpm lint:fix`                | ESLint with auto-fix                              |
| `pnpm test`                    | Run unit tests with Vitest                        |
| `pnpm test:e2e`                | Run isolated mock E2E on port 3101                |
| `pnpm test:e2e:reuse`          | Run mock E2E against an existing port-3000 server |
| `pnpm test:e2e:real-backend`   | Run real Gateway replay E2E on isolated port 3102 |
| `pnpm test:e2e:opensku-replay` | Run full-stack Launch/Growth replay E2E           |
| `pnpm test:e2e:visual`         | Run the focused visual regression suite           |
| `pnpm typecheck`               | TypeScript type check (`tsc --noEmit`)            |
| `pnpm start`                   | Start production server                           |

Unit tests live under `tests/unit/` and mirror the `src/` layout (e.g., `tests/unit/core/api/stream-mode.test.ts` tests `src/core/api/stream-mode.ts`). Powered by Vitest; import source modules via the `@/` path alias.

Mock E2E tests live under `tests/e2e/` and use Playwright with Chromium. They mock backend APIs via `page.route()` and default to a newly built production server on port `3101`; they do not reuse the developer's port-3000 process unless `PLAYWRIGHT_REUSE_SERVER=1` is explicitly set. Use `PLAYWRIGHT_PORT=<port> pnpm test:e2e` to select another isolated port.

`tests/e2e-opensku-replay/` is the product-level full-stack suite. It starts a real production Next.js server and a real Gateway/runtime while replacing only the LLM with the committed hash-keyed replay fixture. The suite covers Launch Ultra's specialist/preflight repair loop and Growth Analyst's CSV upload/join/A/B-analysis path. `tests/e2e/visual-regression.spec.ts` keeps a small macOS pixel baseline and uses DOM/layout assertions plus attached screenshots in Linux CI.

`playwright.real-backend.config.ts` runs the lower-level real-backend contract suite on port `3102` (Gateway `8011`) by default; `playwright.record.config.ts` uses port `3103` for manual real-provider recording. Both are isolated from the developer's port `3000` unless an explicit reuse flag/configuration is supplied.

## Architecture

```
Frontend (Next.js) ──▶ LangGraph SDK ──▶ LangGraph Backend (lead_agent)
                                              ├── Sub-Agents
                                              └── Tools & Skills
```

The frontend is a stateful chat application. Users create **threads** (conversations), send messages, and receive streamed AI responses. The backend orchestrates agents that can produce **artifacts** (files/code) and **todos**.

### Source Layout (`src/`)

- **`app/`** — Next.js App Router. Routes: `/` (landing), `/workspace/chats/[thread_id]` (general chat), and `/workspace/agents/[agent_name]/chats/[thread_id]` (agent-owned chat).
- **`components/`** — React components split into:
  - `ui/` — Shadcn UI primitives (auto-generated, ESLint-ignored)
  - `ai-elements/` — Vercel AI SDK elements (auto-generated, ESLint-ignored)
  - `workspace/` — Chat page components (messages, artifacts, settings)
  - `landing/` — Landing page sections
- **`core/`** — Business logic, the heart of the app:
  - `threads/` — Thread creation, streaming, state management (hooks + types)
  - `api/` — LangGraph client singleton
  - `artifacts/` — Artifact loading and caching
  - `i18n/` — Internationalization (en-US, zh-CN)
  - `settings/` — User preferences in localStorage
  - `memory/` — Persistent user memory system
  - `skills/` — Skills installation and management
  - `messages/` — Message processing and transformation
  - `mcp/` — Model Context Protocol integration
  - `models/` — TypeScript types and data models
- **`hooks/`** — Shared React hooks
- **`lib/`** — Utilities (`cn()` from clsx + tailwind-merge)
- **`server/`** — Server-side code (better-auth, not yet active)
- **`styles/`** — Global CSS with Tailwind v4 `@import` syntax and CSS variables for theming

### Data Flow

1. User input → thread hooks (`core/threads/hooks.ts`) → LangGraph SDK streaming
2. Stream events update thread state (messages, artifacts, todos)
3. TanStack Query manages server state; localStorage stores user settings
4. Components subscribe to thread state and render updates

### Primary Agents

The workspace sidebar provides two primary agent entry points: `OpenSKU Launch Team` and `Growth Analyst`. Growth Analyst keeps the compatibility route and `agent_name` value `data-inspector`. They share the standard chat composer, file upload, and thread APIs; recent-chat lists use the internal value to keep each agent's conversations separate from the other agent and from general chats.

Growth Analyst's route provides its own user-facing name, database icon, and data-analysis quick actions. Keep this route as a chat experience; reusable analysis behavior is configured by the backend agent, tools, and skills.

Primary-agent chats default to Flash reasoning. OpenSKU Launch Team additionally overrides the run context with `is_plan_mode=false`, `subagent_enabled=true`, and `max_concurrent_subagents=2`: specialists stay available while todo-plan creation/update calls remain disabled. Whole-request call, token, duplicate-specialist, and wall-time budgets are enforced by the backend agent config.

### Key Patterns

- **Server Components by default**, `"use client"` only for interactive components
- **Thread hooks** (`useThreadStream`, `useSubmitThread`, `useThreads`) are the primary API interface
- **LangGraph client** is a singleton obtained via `getAPIClient()` in `core/api/`
- **Environment validation** uses `@t3-oss/env-nextjs` with Zod schemas (`src/env.js`). Skip with `SKIP_ENV_VALIDATION=1`

## Code Style

- **Imports**: Enforced ordering (builtin → external → internal → parent → sibling), alphabetized, newlines between groups. Use inline type imports: `import { type Foo }`.
- **Unused variables**: Prefix with `_`.
- **Class names**: Use `cn()` from `@/lib/utils` for conditional Tailwind classes.
- **Path alias**: `@/*` maps to `src/*`.
- **Components**: `ui/` and `ai-elements/` are generated from registries (Shadcn, MagicUI, React Bits, Vercel AI SDK) — don't manually edit these.

## Environment

Backend API URLs are optional; an nginx proxy is used by default:

```
NEXT_PUBLIC_BACKEND_BASE_URL=http://localhost:8001
NEXT_PUBLIC_LANGGRAPH_BASE_URL=http://localhost:8001/api
```

Leave these unset for the standard `make dev` / Docker flow, where nginx serves
the public `/api/langgraph/*` prefix and rewrites it to Gateway's native `/api/*`
routes.

Requires Node.js 22+ and pnpm 10.26.2+.
