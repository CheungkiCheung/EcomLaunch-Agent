# openGrowth

> 面向电商经营的双 Agent 工作台：上架前验证方向，上架后用真实店铺数据持续分析。

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

openGrowth 基于 [DeerFlow](https://github.com/bytedance/deer-flow) 构建，保留其 LangGraph Agent Runtime、配置化 Agent、Skill、Tool、Subagent、文件上传和流式 Chat 能力。本仓库新增两个彼此独立的电商入口：

- **EcomLaunch**：上架前，利用公开市场信号、用户声音和竞品证据验证新品方向。
- **商铺运营 Agent（Store Operator）**：上架后，上传 CSV/XLSX，直接用中文追问经营变化、商品贡献、退款、履约或其他数据问题。

两者目前不做自动交接，也不要求用户建立共同 Case。这样可以先把每个入口的真实使用体验做扎实，再用实际需求决定是否需要跨阶段数据合同。

## 商铺运营怎么用

1. 打开“商铺运营 → 数据对话”。
2. 上传订单、商品、营销、退款、库存、履约或利润相关的 CSV/XLSX。
3. 直接提问，例如：

```text
这份数据可以可靠分析什么？
```

```text
请比较最近 14 天和此前 14 天，店铺最明显的变化是什么？
```

```text
哪些商品或类目对成交下降贡献最大？有没有其他解释？
```

用户不需要提供内部 ID、表名、SQL、Subagent 类型或精确字段名。第一次分析时，Agent 会先检查真实表结构、数据粒度、时间范围和质量风险；用户所说的“最近”以数据中的最新日期为锚点，而不是系统当天日期。

## 核心设计

```text
中文 Chat
   │
   ▼
Store Operator Parent
   ├── store_inspect_data ── 表、字段、粒度、时间与质量检查
   ├── store_query_data ───── DuckDB 只读确定性计算
   └── task（按需）
       ├── explore ────────── 多文件、字段和口径探索
       ├── analyst ────────── 单一窗口比较或贡献拆解
       └── verifier ───────── 关键数字独立复算
```

简单问题由 Parent 直接调用数据 Tool 回答。只有问题需要独立探索、并行拆解或高风险数字复核时，才临时委派 0-N 个 Subagent；系统没有固定的 `Explore → Analyst → Verifier` 流程。

这套设计把职责分为三层：

| 层 | 负责什么 | 不负责什么 |
|---|---|---|
| Agent / SOUL | 理解问题、选择行动、组织中文回答 | 心算指标、编造缺失数据 |
| Skill / Subagent Profile | 领域规则和可选专业分工 | 强制所有请求走同一流程 |
| Tool | 解析文件、执行确定性查询、返回事实 | 替用户做因果判断 |

## 数据能力与边界

`store_inspect_data` 支持：

- CSV 与多 Sheet XLSX；
- 表 alias、行列数、空值、重复行、样例和数字摘要；
- 日期范围和常见电商语义字段候选；
- 50 MB 单文件、30 万行/表、120 列/表的保护上限。

`store_query_data` 使用内存 DuckDB，只接受单条 `SELECT` 或 `WITH` 查询，最大返回 200 行。工具关闭外部访问，并拒绝写操作、多语句、SQL 注释、`ATTACH`、`COPY`、`INSTALL`、`LOAD`、`PRAGMA` 和外部文件扫描函数。

分析遵循以下证据边界：

- 所有计数、聚合、趋势和贡献拆解必须来自数据 Tool；
- 先判断一行是订单、商品明细还是事件，避免订单金额重复求和；
- 当前文件没有曝光、点击、加购、广告消耗、库存、利润等字段时，明确说明无法判断；
- 区分数据事实、可能解释、未知项和数据质量风险；
- 相关性不能写成已证实因果。

## 对话与作战室

主界面保持 DeerFlow/Codex 风格的中文 Chat，不增加密集业务面板。作战室是一个辅助观察入口：

- 四个小比例角色代表 Parent、Explore、Analyst 和 Verifier；
- 空闲角色在场景中轻量走动；
- 只有真实 `task` Tool Call 对应的角色才返回工位并进入工作状态；
- Task 完成后角色恢复空闲；
- `prefers-reduced-motion` 环境下停止走动并固定在工位；
- 不模拟假任务，不做复杂碰撞、搬运、汇报动画或跨 Agent 联动。

视觉决策见 [`docs/design/store-operator/war-room-visual-v1.md`](./docs/design/store-operator/war-room-visual-v1.md)。

## EcomLaunch

EcomLaunch 保留原有上架前验证能力：Parent 根据目标委派市场与用户声音研究、定位设计、内容资产和证据核验等 Subagent，使用公开信息输出有来源边界的验证结论。它不依赖 Store Operator，也不会自动读取店铺运营数据。

主要配置位置：

```text
agents/ecom-launch/
skills/custom/ecom-launch/
frontend/src/components/workspace/ecom-launch/
```

## 项目结构

```text
openGrowth/
├── agents/
│   ├── ecom-launch/                 # 上架前 Agent 配置
│   └── store-operator/              # 商铺运营 Agent 配置与 SOUL
├── backend/
│   ├── app/gateway/                 # DeerFlow API Gateway
│   ├── app/store_operator/          # CSV/XLSX 与只读 SQL Tool
│   ├── packages/harness/            # DeerFlow Agent Runtime
│   └── tests/store_operator/        # 数据工具测试
├── frontend/
│   ├── src/components/workspace/ecom-launch/
│   └── src/components/workspace/store-operator/
├── skills/custom/
│   ├── ecom-launch/
│   └── store-data-analysis/
├── config.yaml                      # 本地运行配置
├── config.example.yaml              # 无密钥配置示例
└── docs/design/store-operator/      # 视觉与设计记录
```

## 本地运行

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm
- uv

### 安装

```bash
make install
```

在根目录 `.env` 配置模型密钥。密钥不能写入 `config.yaml`、日志、测试证据或 Git：

```text
DEEPSEEK_API_KEY=...
```

启动完整开发环境：

```bash
make dev
```

也可以分别启动：

```bash
cd backend
uv run uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001
```

```bash
cd frontend
pnpm dev
```

商铺运营对话地址：

```text
http://127.0.0.1:3000/workspace/agents/store-operator/chats/new
```

作战室地址：

```text
http://127.0.0.1:3000/workspace/agents/store-operator/war-room
```

## 模型验收规则

本项目的 Agent/LLM 行为验收使用 fresh 真实 DeepSeek V4 请求：

```text
本地模型 alias：deepseek-reasoner
服务端模型：deepseek-v4-flash
max_retries：0
```

Mock、Replay、缓存输出或模型回退不能作为 Agent Gate 通过证据。确定性数据工具和纯前端状态逻辑仍使用常规单元测试。真实模型门禁还必须记录实际模型身份、重试次数和 provider request ID，避免把错误路由或旧响应当成通过。

## 验证

后端：

```bash
cd backend
uv run pytest -q \
  tests/store_operator \
  tests/test_custom_agent.py \
  tests/test_subagent_skills_config.py \
  tests/test_tool_deduplication.py
uv run ruff check app/store_operator tests/store_operator
```

前端：

```bash
cd frontend
pnpm typecheck
pnpm exec vitest run
pnpm exec eslint \
  'src/components/workspace/store-operator/**/*.{ts,tsx}' \
  'src/app/workspace/agents/store-operator/**/*.tsx'
```

前端功能改动还需要真实浏览器检查上传、流式回答、作战室状态、390px 布局和 reduced-motion 行为。

## 上游与个人新增能力

DeerFlow 提供 Agent Runtime、LangGraph 编排、配置系统、Skill/Tool/Subagent 机制、上传、线程消息和基础前端。本项目新增并负责验证的部分包括：

- 两个电商垂直 Agent 的产品边界与配置；
- Store Operator 中文 SOUL 和数据分析 Skill；
- 安全 CSV/XLSX 检查与只读 DuckDB Tool；
- Explore / Analyst / Verifier 按需 Subagent 策略；
- 中文入口和真实 Task 驱动的轻量作战室；
- DeepSeek V4 零重试真实模型门禁与电商公开数据验收。

## 许可证

MIT License，详见 [LICENSE](./LICENSE)。
