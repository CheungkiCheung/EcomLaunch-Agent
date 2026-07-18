# OpenSKU

[English](./README.md) | [中文](./README_zh.md) | [日本語](./README_ja.md) | Français | [Русский](./README_ru.md)

> Evidence-governed AI launch loop for ecommerce SKU decisions.

OpenSKU helps merchants, ecommerce operators, and indie sellers turn product ideas, listing links, competitor pages, public signals, uploaded context, and early feedback into a SKU launch decision loop: **Go, Pivot, Hold, Kill, or Scale**.

This project is not a fixed one-week artifact generator. Seven days is only the default demo cadence. Real SKU launches should adapt to launch stage, available data, channel feedback, inventory constraints, and operating risk.

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
