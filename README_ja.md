# OpenSKU

[English](./README.md) | [中文](./README_zh.md) | 日本語 | [Français](./README_fr.md) | [Русский](./README_ru.md)

> Evidence-governed AI launch loop for ecommerce SKU decisions.

OpenSKU は、EC 事業者、運営担当者、個人セラーが、商品アイデア、商品リンク、競合ページ、公開シグナル、アップロード資料、初期フィードバックをもとに、SKU の上新判断を行うための AI launch loop です。

判断は **Go / Pivot / Hold / Kill / Scale** の形で返します。

OpenSKU は固定の「7 日間パック生成器」ではありません。7 日はデモ用のデフォルト cadence です。実際の上新計画は、SKU の段階、利用可能なデータ、チャネル反応、在庫や運用制約に合わせて 3、7、14、30 日に調整されます。

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

OpenSKU は LangGraph agent runtime の上に構築され、EcomLaunch agent、skill、artifact contract、War Room UI を追加したプロジェクトです。詳しくはメイン README を参照してください: [README.md](./README.md)。
