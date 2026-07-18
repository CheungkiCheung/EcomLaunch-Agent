# OpenSKU

[English](./README.md) | [中文](./README_zh.md) | [日本語](./README_ja.md) | [Français](./README_fr.md) | Русский

> Evidence-governed AI launch loop for ecommerce SKU decisions.

OpenSKU помогает продавцам, ecommerce-операторам и indie sellers превращать идеи SKU, ссылки на товары, страницы конкурентов, публичные сигналы, загруженные материалы и ранний feedback в цикл решения по запуску: **Go, Pivot, Hold, Kill или Scale**.

Это не фиксированный генератор one-week artifacts. Семь дней используются только как demo cadence. Реальный план запуска должен меняться в зависимости от стадии SKU, доступных данных, реакции каналов, inventory constraints и операционных рисков.

## Core Workflow

| Step | Output |
|---|---|
| Stage diagnosis | `idea_only`, `supplier_sample`, `pre_launch_test`, `soft_launch`, or `scale_iterate` |
| Evidence-backed decision | Go / Pivot / Hold / Kill / Scale recommendation |
| Launch Decision Pack | Artifact snapshot for the current loop |
| Promotion replan | Updated hook, channel, price signal, claim, creator brief, or test plan |
| Knowledge deltas | Reusable category, channel, claim-risk, and experiment learnings |

## Default Artifacts

```text
/mnt/user-data/outputs/
├── launch-war-room.html
├── evidence-ledger.json
├── competitor-table.csv
├── positioning-brief.md
├── listing-pack.md
├── content-pack.md
└── launch-calendar.csv
```

## Quick Start

```bash
git clone git@github.com:CheungkiCheung/OpenSKU.git
cd OpenSKU

make install
make config
make dev
open http://localhost:2026
```

OpenSKU is built on a LangGraph agent runtime and extends it with the EcomLaunch agent, skill, artifact contract, and War Room UI. See the main README for the full project description: [README.md](./README.md).
