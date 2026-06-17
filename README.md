# openGrowth

> AI增长实验引擎 — 从公开信号到校准决策，建立你自己的判断公式

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## 简介

openGrowth 是一个**开源的AI增长实验引擎**，采用 Orchestrator-Subagent 架构，5个专业Agent并行协作，覆盖从上线前验证到内容校准的完整增长实验链路。

### 核心特性

- **多Agent协作** - 5个专业Agent并行工作
- **证据驱动** - 基于公开信号，非主观判断
- **实验校准** - Score → Predict → Retro → Evolve 闭环
- **游戏化界面** - 像素艺术办公室
- **渐进式模式** - Flash/Thinking/Pro/Ultra 4种模式
- **两大工作流** - validate-launch + calibrate-content

## 架构

```
┌─────────────────────────────────────────────────────┐
│              openGrowth 架构                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐    ┌─────────────┐                │
│  │  用户输入   │───▶│  模式选择   │                │
│  └─────────────┘    └─────────────┘                │
│                           │                         │
│                           ▼                         │
│  ┌─────────────────────────────────────┐           │
│  │         Orchestrator Agent          │           │
│  │    (任务分解 + 子Agent调度)         │           │
│  └─────────────────────────────────────┘           │
│                           │                         │
│         ┌─────────────────┼─────────────────┐       │
│         ▼                 ▼                 ▼       │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐ │
│  │ Market   │      │ Offer    │      │ Growth   │ │
│  │ Researcher│     │ Architect│      │ Analyst  │ │
│  └──────────┘      └──────────┘      └──────────┘ │
│         │                 │                 │       │
│         ▼                 ▼                 ▼       │
│  ┌─────────────────────────────────────┐           │
│  │         工具层 (last30days等)       │           │
│  └─────────────────────────────────────┘           │
│                           │                         │
│                           ▼                         │
│  ┌─────────────────────────────────────┐           │
│  │         产出物生成器                 │           │
│  │    (7件套增长验证包)                │           │
│  └─────────────────────────────────────┘           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- yt-dlp（YouTube搜索）
- ffmpeg（YouTube转录）

### 安装

```bash
# 克隆仓库
git clone git@github.com:CheungkiCheung/openGrowth.git
cd openGrowth

# 安装依赖
make install

# 启动服务
make dev

# 访问前端
open http://localhost:2026
```

## 5个专业Agent

| Agent | 职责 | 工具 |
|-------|------|------|
| **market-voc-researcher** | 市场研究 + 用户声音 | last30days + web_search |
| **offer-architect** | 增长策略 + 假设验证 | web_search + PM Skills |
| **growth-analyst** | 数据分析 + 指标设计 | market-sizing + north-star |
| **asset-studio** | 内容创作 + 素材制作 | web_search |
| **evidence-checker** | 证据审计 + 质量控制 | ab-test + cohort-analysis |

## 4种模式

| 模式 | 用途 | Agent | 产出物 |
|------|------|-------|--------|
| **Flash** | 快速查询 | 单Agent | 基础回答 |
| **Thinking** | 深度分析 | 单Agent | 市场洞察 |
| **Pro** | 详细报告 | 单Agent | 竞品分析 |
| **Ultra** | 完整验证 | 5个Agent | 7件套验证包 |

## 产出物

### validate-launch（上线前验证）

1. **launch-war-room.html** - 增长决策仪表板
2. **evidence-ledger.json** - 证据账本
3. **competitor-table.csv** - 竞品分析
4. **positioning-brief.md** - 增长策略
5. **listing-pack.md** - 产品文案
6. **content-pack.md** - 增长内容
7. **launch-calendar.csv** - 7天验证计划

### calibrate-content（内容校准）

1. **calibration-ledger.json** - 校准账本
2. **rubric.md** - 评分公式
3. **content-scorecard.md** - 内容评分卡

## 技术栈

| 技术 | 用途 |
|------|------|
| **Next.js 19** | 前端框架 |
| **React 19** | UI库 |
| **Tailwind CSS 4** | 样式系统 |
| **Python 3.12+** | 后端引擎 |
| **LangGraph** | Agent编排 |
| **last30days** | 多平台数据聚合 |

## 使用场景

### 场景1：创业者验证idea

```
用户：我想做一个AI写作助手，帮我看看这个idea怎么样
系统：自动搜索竞品、用户痛点、市场机会
输出：初步市场洞察
```

### 场景2：产品经理验证新方向

```
用户：帮我做一个完整的增长验证包
系统：5个Agent并行执行
输出：7件套增长验证包
```

### 场景3：电商卖家上新品

```
用户：我想上一款便携咖啡杯，帮我分析一下市场
系统：搜索用户讨论、竞品分析
输出：市场洞察 + 产品文案
```

### 场景4：卖家校准内容表现

```
用户：帮我回顾上周发的5条短视频脚本，哪些预测准、哪些翻车了
系统：对比 blind prediction vs 实际数据，输出校准账本
输出：calibration-ledger.json + 更新后的评分公式
```

## 项目结构

```
openGrowth/
├── backend/                    # Python后端
│   ├── packages/harness/       # 核心框架
│   ├── app/gateway/            # API网关
│   └── tests/                  # 测试
├── frontend/                   # Next.js前端
│   └── src/components/         # React组件
├── agents/                     # Agent定义
├── skills/                     # 技能定义
├── config.yaml                 # 配置文件
└── docs/                       # 文档
```

## 核心能力

### 1. 多平台数据聚合

| 平台 | 数据类型 | 费用 |
|------|----------|------|
| Reddit | 用户讨论、痛点 | 免费 |
| YouTube | 视频评测、转录 | 免费 |
| Hacker News | 技术讨论 | 免费 |
| Polymarket | 预测市场赔率 | 免费 |

### 2. 证据驱动决策

- 所有私有指标标记为unavailable
- 基于公开信号验证
- 每个决策都有证据支持

### 3. 游戏化界面

- 像素艺术办公室
- 6个像素角色
- 实时状态同步
- 白板任务进度

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 联系方式

- **GitHub**: github.com/CheungkiCheung/openGrowth
- **Issues**: GitHub Issues

---

**openGrowth** - 让增长验证更简单、更客观、更高效。
