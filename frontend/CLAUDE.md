# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeerFlow Frontend is a Next.js 16 web interface for an AI agent system. It communicates with a LangGraph-based backend to provide thread-based AI conversations with streaming responses, artifacts, and a skills/tools system.

This fork is building a **Chat-first Commerce Workspace**. The default product entry reuses DeerFlow Thread, Message, Composer, Artifact and Subtask interaction: users upload real ecommerce data and ask a natural question; Parent directly answers, calls deterministic Commerce tools or dynamically delegates 0–N Subagents. Case, Evidence, Hypothesis, Action, Approval and Follow-up remain authoritative persisted business objects for complex/long-running work, but users do not need to create a Case before chatting. The old fixed War Room is not a default page; an optional collaboration scene may visualize real Durable Task Events.

The Commerce entry is fail-closed behind `NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED=false`; the backend flag must also be enabled. Existing Case-first APIs still use `NEXT_PUBLIC_COMMERCE_WORKSPACE_ID` for explicit Workspace scope. The Chat main interface and optional collaboration scene now use the approved generated direction. Runtime scene, actor and station assets are recorded in `../docs/design/commerce-collaboration-imagegen-assets-v1.md`; images consume structured ViewModel state and never decide Task state. Mocked-backend UI tests cannot serve as Commerce Agent acceptance evidence; Agent E2E must use the real backend and an identity-verified DeepSeek V4 request.

The previously approved Chinese Master Shell, Case Detail v2, Data Inbox, Capability Report, Case Queue, Evidence Explorer, Action Center, Agent Run, and Skills & Evals remain implemented at `/commerce`, but they are now advanced-detail assets rather than the default product shell. Pure contracts and projections live under `src/core/commerce/`. New Chat state must consume Durable `SubagentTask` snapshots and append-only Task Events through a pure reducer; Chat compact cards and the optional collaboration scene share the same `CommerceTaskVisualState`. Unknown and out-of-order events remain explicit, and the UI never infers activity from assistant text, CSS timers or random animation. The frozen mapping is documented in `../docs/design/commerce-chat-task-visual-state-contract.md`; generated visual directions are documented in `../docs/design/commerce-chat-visual-directions.md`.

Current frontend validation includes 62 Vitest files / 334 tests, repository-wide Prettier, ESLint and TypeScript, plus 6 passing Chromium mechanical interactions for the Commerce Chat/collaboration route and a real persistent DeepSeek V4 browser Gate. The Chat contract adds strict authenticated Durable Task/Event API parsing, append-only cursors, a pure Task/Event visual reducer, a shared Run activity ViewModel, and an abortable incremental polling Hook for Chat compact status and the optional collaboration scene. Each Task resumes from its own `next_after_seq`; cursors are monotonic and repeated sequence numbers never replay. The collaboration scene uses one generated actor and workstation per unique Durable Task, an empty generated room with no actors when no Task exists, deterministic collision-free 2×2/3×2 placement, explicit terminal states and reduced-motion support. The previously missing approved `CommerceWarRoomView` remains a read-only advanced event-lane view; it is not the default navigation. The persistent Gate used a real local account/CSRF flow, six frozen Olist CSV files and a fresh `deepseek-v4-flash` Parent–Subagent Run with 170,394 Tokens, 13 de-duplicated Provider Request IDs and retry 0. Explore/Analyst ran in parallel, fresh Verifier followed, and the same Run drove Chat, task activity and desktop/390px/reduced-motion collaboration screenshots. A read-only existing-run audit can revisit this Run without submitting another prompt or spending model tokens. Evidence is under `../docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/`.

**Stack**: Next.js 16, React 19, TypeScript 5.8, Tailwind CSS 4, pnpm 10.26.2

## Commands

| Command          | Purpose                                           |
| ---------------- | ------------------------------------------------- |
| `pnpm dev`       | Dev server with Turbopack (http://localhost:3000) |
| `pnpm build`     | Production build                                  |
| `pnpm check`     | Lint + type check (run before committing)         |
| `pnpm lint`      | ESLint only                                       |
| `pnpm lint:fix`  | ESLint with auto-fix                              |
| `pnpm test`      | Run unit tests with Vitest                        |
| `pnpm test:e2e`  | Run E2E tests with Playwright (Chromium)          |
| `pnpm typecheck` | TypeScript type check (`tsc --noEmit`)            |
| `pnpm start`     | Start production server                           |

Unit tests live under `tests/unit/` and mirror the `src/` layout (e.g., `tests/unit/core/api/stream-mode.test.ts` tests `src/core/api/stream-mode.ts`). Powered by Vitest; import source modules via the `@/` path alias.

E2E tests live under `tests/e2e/` and use Playwright with Chromium. They mock all backend APIs via `page.route()` network interception and test real page interactions (navigation, chat input, streaming responses). Config: `playwright.config.ts`.

## Architecture

```
Frontend (Next.js) ──▶ LangGraph SDK ──▶ LangGraph Backend (lead_agent)
                                              ├── Sub-Agents
                                              └── Tools & Skills
```

The frontend is a stateful chat application. Users create **threads** (conversations), send messages, and receive streamed AI responses. The backend orchestrates agents that can produce **artifacts** (files/code) and **todos**.

### Source Layout (`src/`)

- **`app/`** — Next.js App Router. Routes: `/` (landing), `/workspace/chats/[thread_id]` (chat), `/commerce` (feature-flagged Case-first workspace).
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
  - `commerce/` — Commerce API contracts, strict response parsing and Domain Event-to-view-model projection
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
NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED=false
NEXT_PUBLIC_COMMERCE_WORKSPACE_ID=wsp_<32 lowercase hex chars>
```

Leave these unset for the standard `make dev` / Docker flow, where nginx serves
the public `/api/langgraph/*` prefix and rewrites it to Gateway's native `/api/*`
routes.

Requires Node.js 22+ and pnpm 10.26.2+.
