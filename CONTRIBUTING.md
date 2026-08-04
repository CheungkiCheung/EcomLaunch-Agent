# Contributing to OpenSKU

Thank you for helping improve OpenSKU. Contributions are welcome across ecommerce workflows, agent behavior, evidence quality, data analysis, the bilingual product experience, documentation, and developer tooling.

## Before you start

- Search [existing issues](https://github.com/CheungkiCheung/opensku/issues) before opening a duplicate.
- Use [GitHub Discussions](https://github.com/CheungkiCheung/opensku/discussions) for product ideas, architecture questions, and early proposals.
- Open an issue first for changes that significantly alter product scope, persistent data, public APIs, security boundaries, or deployment architecture.
- Do not commit API keys, `.env` files, generated databases, caches, model files, or private datasets.

## Development options

### Local development

Prerequisites:

- Python 3.12+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/)
- pnpm 10+
- nginx

```bash
git clone https://github.com/CheungkiCheung/opensku.git
cd opensku
make setup
make install
make dev
```

Open [http://localhost:2026](http://localhost:2026). The unified endpoint proxies the Next.js frontend and FastAPI gateway while preserving streaming responses.

For focused frontend work:

```bash
cd frontend
pnpm dev
```

The frontend is then available at [http://localhost:3000](http://localhost:3000).

### Docker development

Prerequisites:

- Docker Desktop or Docker Engine
- pnpm for host-side cache reuse

```bash
make docker-init
make docker-start
```

Useful commands:

```bash
make docker-logs
make docker-logs-frontend
make docker-logs-gateway
make docker-stop
```

The provisioner service is started only when the selected sandbox configuration requires it.

### Recommended resources

| Scenario | Starting point | Recommended |
| --- | --- | --- |
| Local development | 4 vCPU, 8 GB RAM | 8 vCPU, 16 GB RAM |
| Docker review environment | 4 vCPU, 8 GB RAM | 8 vCPU, 16 GB RAM |
| Shared development server | 8 vCPU, 16 GB RAM | 16 vCPU, 32 GB RAM |

## Project layout

```text
opensku/
├── agents/              # Repository-defined top-level agents
├── backend/             # FastAPI gateway, agent runtime, and analysis tools
├── frontend/            # Next.js product interface and Phaser War Room
├── skills/              # Public and custom agent skills
├── docker/              # Development and production containers
├── docs/                # Architecture and product documentation
├── config.example.yaml  # Main configuration template
└── Makefile             # Common setup, development, and test commands
```

Some internal package paths and environment variables retain compatibility names inherited from the upstream runtime. Do not rename them mechanically: imports, persisted state, Docker resources, and deployment contracts must be migrated and tested together. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development workflow

1. Create a focused branch.
2. Keep unrelated user or workspace changes intact.
3. Add tests proportional to the behavior being changed.
4. Run the relevant checks locally.
5. Update documentation when the behavior, configuration, or public contract changes.
6. Open a pull request using the repository template.

Example:

```bash
git switch -c feature/clear-description
# make changes
git add path/to/changed-files
git commit -m "feat: add clear description"
git push origin feature/clear-description
```

## Test and quality gates

### Backend

```bash
cd backend
make test
make lint
make test-blocking-io
```

### Frontend

```bash
cd frontend
pnpm typecheck
pnpm test
pnpm lint
pnpm build
pnpm test:e2e
```

For frontend visual changes, verify the result in a real browser at both desktop and compact viewport sizes. For language changes, test both English and Chinese and confirm that canvas-rendered text changes with the React interface.

### Formatting

```bash
# Backend
cd backend
make format

# Frontend
cd frontend
pnpm format:write
```

## Pull request expectations

A good pull request explains:

- the user problem and intended outcome;
- the implementation and important tradeoffs;
- validation commands and results;
- screenshots or recordings for visual changes;
- compatibility, migration, or rollback considerations;
- whether AI assistance was used and how the author reviewed the result.

AI-assisted contributions are welcome, but the human contributor remains responsible for understanding, testing, and maintaining the change.

## Reporting security issues

Do not disclose vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md) and use the repository's private security-reporting flow.

## License

By contributing to OpenSKU, you agree that your contribution will be licensed under the [MIT License](LICENSE) and that required third-party notices will be preserved.
