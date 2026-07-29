# openGrowth

> AI 增长实验引擎 — 从公开信号和上传数据到可执行决策

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## 简介

openGrowth 是一个**开源的 AI 增长实验引擎**，基于 DeerFlow 扩展两个彼此独立的顶层 Agent：EcomLaunch 负责上线前研究、定位、实验和内容产出；Growth Analyst 负责分析用户上传的经营和内容表现数据，内部兼容 ID 仍为 `data-inspector`。EcomLaunch 内部采用 Orchestrator-Subagent 架构，按需调用 4 个专业 Subagent。

### 核心特性

- **按需多 Agent 协作** - EcomLaunch 只调用任务需要的 0～4 个专业 Subagent
- **上传数据分析** - 直接分析 CSV/XLSX 商铺、小红书和抖音数据
- **证据驱动** - 基于公开信号，非主观判断
- **轻量实验** - 把关键假设变成低成本验证动作和停止条件
- **真实作战室** - 展示两个顶层 Agent 与 4 个真实 EcomLaunch Subagent 的运行状态
- **快速默认配置** - 默认 Flash 推理，保留按需子智能体能力并关闭额外的计划追踪开销
- **整次任务预算** - 限制重复专家调用、主智能体轮次、Token 与执行时间，达到边界后交付已有结果

## 架构

```
                         DeerFlow 原生对话与文件上传
                                      │
                  ┌──────────────────┴──────────────────┐
                  ▼                                     ▼
       EcomLaunch 顶层 Agent                 Growth Analyst 顶层 Agent
                  │                                     │
       Orchestrator + 4 个专业 Subagent            inspect_data
                  │                                     │
     公开信号、市场、定位、内容                         query_data
                  │                                     │
           增长验证与内容产出                 数据质量、聚合、趋势与关联分析

             两个 Agent 当前独立运行，不自动串联
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

## 两个顶层 Agent

| Agent | 当前职责 | 当前边界 |
|-------|----------|----------|
| **EcomLaunch** | 市场与用户研究、产品定位、上线验证和内容产出 | 使用现有多 Agent 工作流 |
| **Growth Analyst** | 检查并分析上传的商铺、商品、小红书、抖音等结构化数据 | 内部 ID 为 `data-inspector`，当前支持 CSV/XLSX |

Growth Analyst 复用 DeerFlow 原生 Agent 配置、文件上传和对话能力，不依赖 Host Bash。上传文件后可以直接用中文提问，例如：

```text
帮我看这个月哪些商品销售额下降最多，同时检查数据有没有重复或缺失。
按笔记比较小红书收藏率，说明计算口径和异常点。
把订单表和商品表关联，找出销售额贡献最高的品类。
```

它采用“简短通用 SOUL + 按需 Skill + 确定性工具”的配置方式：

- `sql-queries`、`cohort-analysis` 和 `ab-test-analysis` 直接采用 [phuryn/pm-skills](https://github.com/phuryn/pm-skills) 的 `pm-data-analytics` 原版 Skill，并保留 MIT License；
- `inspect_data` 负责读取 CSV/XLSX 的表结构和数据概况，`query_data` 负责在内存表上执行受限只读 SQL；
- `analyze_ab_test` 负责二元转化 A/B 实验的确定性统计计算，避免模型手算 p 值和置信区间；
- PM Skill 提供分析方法，DeerFlow 工具提供上传文件读取和实际计算，两者保持清晰分工。

Growth Analyst 默认关闭跨对话长期记忆，避免把上一份数据的指标带入新数据；同一对话内的追问仍由线程历史正常承接。自由文本样例默认隐藏，只有用户明确要求分析文本内容时才读取，避免从少量样例推断总体投诉占比。

这一阶段只提供 CSV/XLSX 数据分析；连续指标 A/B、多实验组和专属导航/UI 尚未包含。

## 4 个专业 Subagent

| Subagent | 职责 | 默认工具边界 |
|----------|------|--------------|
| **market-voc-researcher** | 市场、竞品、价格带、评论和用户声音 | `web_search`、`web_fetch`、`image_search`、`read_file`，带严格预算 |
| **offer-architect** | 人群、价值主张、价格假设和验证实验 | 只读材料，不重复搜索 |
| **asset-studio** | 商品页、小红书、抖音、短视频和直播资产 | 只读已批准的 Launch Brief，不重新研究 |
| **evidence-checker** | 来源、声明、产品事实和交付质量审核 | `read_file` + 对已有 URL 的定向 `web_fetch` |

这些角色使用固定上游提交 `18468a95b427e70e258b51389796367c6f684e7d` 的原版 [phuryn/pm-skills](https://github.com/phuryn/pm-skills)。Skill 提供分析框架，DeerFlow 工具负责实际读取、搜索和执行。

## 运行策略

- 简短问题由 EcomLaunch 直接回答。
- 市场问题只调用 Market & VOC Researcher。
- 定位和实验任务在证据充分后调用 Offer Architect。
- 内容任务只调用 Asset Studio；完整包或高风险声明最后调用 Evidence Checker。
- 完整 Launch Validation Pack 只在用户明确要求时生成。
- 前端默认使用 Flash 推理；EcomLaunch 关闭额外的计划追踪，但保留子智能体能力，并限制最多同时调用 2 个 Subagent。
- 每次请求最多启动 4 个 Subagent，同一专家最多运行一次；默认最多 16 次主智能体模型响应、50 万已观察 Token 和 240 秒执行时间。每个专家另有独立模型调用与 Token 收尾预算，避免撞到递归错误。
- 信息已经包含产品、约束、公开信号来源、决策目标和交付物时直接执行，不再为可合理推断的平台或人群多问一轮。

## 产出物

### validate-launch（上线前验证）

1. **launch-war-room.html** - 增长决策仪表板
2. **evidence-ledger.json** - 证据账本
3. **competitor-table.csv** - 竞品分析
4. **positioning-brief.md** - 增长策略
5. **listing-pack.md** - 产品文案
6. **content-pack.md** - 增长内容
7. **launch-calendar.csv** - 7天验证计划

## 技术栈

| 技术 | 用途 |
|------|------|
| **Next.js 16** | 前端框架 |
| **React 19** | UI库 |
| **Tailwind CSS 4** | 样式系统 |
| **Python 3.12+** | 后端引擎 |
| **LangGraph** | Agent编排 |

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
系统：按依赖顺序调用需要的专业 Subagent
输出：7件套增长验证包
```

### 场景3：电商卖家上新品

```
用户：我想上一款便携咖啡杯，帮我分析一下市场
系统：搜索用户讨论、竞品分析
输出：市场洞察 + 产品文案
```

### 场景4：上传经营或内容数据直接分析

```text
用户：上传订单 CSV 和商品 XLSX，询问“最近 14 天哪些品类拉低了销售额？”
系统：先检查表结构、粒度、缺失和重复，再用只读查询计算等长时间窗口与品类贡献
输出：已确认结论 + 关键数字 + 计算口径 + 数据质量风险 + 下一步建议
```

## 项目结构

```
openGrowth/
├── backend/                    # Python后端
│   ├── packages/harness/       # 核心框架
│   ├── app/gateway/            # API网关
│   ├── app/data_inspector/     # CSV/XLSX 检查与只读查询工具
│   └── tests/                  # 测试
├── frontend/                   # Next.js前端
│   └── src/components/         # React组件
├── agents/                     # Agent定义
│   ├── ecom-launch/           # EcomLaunch 顶层 Agent
│   └── data-inspector/        # Growth Analyst 顶层 Agent 的兼容内部 ID
├── skills/                     # 技能定义
│   └── custom/                 # EcomLaunch 与 Growth Analyst 使用的固定上游 PM Skills
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
