# OpenSKU

[English](./README.md) | 中文 | [日本語](./README_ja.md) | [Français](./README_fr.md) | [Русский](./README_ru.md)

> 面向电商 SKU 决策的证据治理型 AI 上新循环。

OpenSKU 帮助商家、电商运营和独立卖家，把粗糙新品想法、商品链接、竞品页面、公开信号、上传材料和早期反馈，转化为一个可执行的 SKU 上新决策循环：**Go、Pivot、Hold、Kill 或 Scale**。

它不是固定的“7 天上新包生成器”。7 天只是 demo 默认节奏；真实上新计划会根据 SKU 阶段、可用数据、渠道反馈和经营约束调整为 3、7、14 或 30 天。

## 核心能力

| 能力 | 说明 |
|---|---|
| 阶段诊断 | 判断 SKU 处于 idea-only、supplier/sample、pre-launch test、soft launch 或 scale/iterate |
| 决策建议 | 输出 Go / Pivot / Hold / Kill / Scale，并说明证据和缺口 |
| 证据账本 | 区分公开证据、上传真实数据、估算和不可用指标 |
| 宣传重排 | 根据评论、内容、创作者、客服、店铺或样品反馈调整下一轮宣传计划 |
| 知识沉淀 | 将类目、渠道、卖点、风险和实验经验沉淀为 knowledge deltas |

## 默认产出

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

这些文件组成当前循环的 Launch Decision Pack。它是一次决策快照，不是产品的全部边界。

## 快速开始

```bash
git clone git@github.com:CheungkiCheung/OpenSKU.git
cd OpenSKU

make install
make config
make dev
open http://localhost:2026
```

## 底层架构

OpenSKU 构建在 LangGraph agent runtime 之上，并扩展了专属的 EcomLaunch agent、skill、artifact contract 和前端 War Room。底层 runtime 保留了 DeerFlow 的 harness 能力；公开产品定位应以 OpenSKU 和 SKU launch loop 为主。

更多信息请阅读主 README：[README.md](./README.md)。
