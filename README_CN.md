<p align="center">
  <img src=".github/assets/opensku-logo.svg" alt="OpenSKU 标志" width="112" />
</p>

<h1 align="center">OpenSKU</h1>

<p align="center"><strong>面向电商上新的开源 AI 团队。</strong></p>

<p align="center">
  把一个模糊商品想法，变成有证据边界的上新判断、商品方案<br />
  和可以直接编辑的发布素材。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="#体验无密钥中英文演示"><strong>体验 Demo</strong></a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#opensku-能交付什么">交付内容</a> ·
  <a href="docs/war-room.md">War Room</a>
</p>

![OpenSKU 英文 War Room 演示](.github/assets/war-room-demo.gif)

OpenSKU 为独立开发者、产品团队和电商经营者提供一个协作式 AI 上新团队。它会在投入库存、广告预算和正式发布之前，研究公开市场信号，区分事实、估算和假设，设计商品方案，并在一个可追踪的流程中生成完整上新包。

## 体验无密钥中英文演示

录制式 Demo 支持中英文切换，不需要后端、模型供应商或 API Key。它使用确定性的样例数据，明确说明没有实时 Agent 正在运行，并提供一套 60 秒引导演示，覆盖 Launch Validation 与 Growth Analyst 实验两个场景。Launch 路径会明确展示有界 Agent-Environment Loop，包括 Action、结构化 Observation、动态选择的最小修订、重新校验与 Stop Condition；每个场景还包含暖色 War Room 和 4 份随语言切换的可检查交付物。

```bash
cd frontend
pnpm install
pnpm demo
```

打开[英文 Demo](http://localhost:3000/demo?lang=en)或[中文 Demo](http://localhost:3000/demo?lang=zh)。可以先演示面向美国市场的紧凑型旅行咖啡杯验证，再切换到结账页实验，查看只读跨文件分析、双比例检验、SRM、Cohort 样例和受限 Memory 快照。语言和场景都会保存在 URL 中，两个演示路径也都明确与实时市场研究和真实店铺数据区分开。

## OpenSKU 能交付什么

| 你提供 | OpenSKU 调研 | 你获得 |
| --- | --- | --- |
| 粗略商品想法、公开链接或简短 Brief | 市场信号、竞品、价格、用户语言、风险和证据缺口 | 做 / 验证 / 停止建议，以及明确的置信度与下一步 |
| 可选 CSV 或 XLSX 数据 | 变化、异常、分群、留存和实验结果 | 基于上传数据的增长分析 |
| 品牌限制与目标渠道 | 定位、方案假设、商品页结构、内容钩子和脚本 | 可编辑的上新素材，而不是只停留在聊天回答 |

### 一个 Brief 输入 → 一套上新包输出

```text
商品 Brief
  ├─ 市场与用户声音研究
  ├─ 竞品与价格扫描
  ├─ 带证据边界的 Evidence Ledger
  ├─ 定位与商品方案假设
  ├─ 商品页文案与内容钩子
  └─ 7 天轻量验证计划
```

完整流程可生成：

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

## 上新团队

| 运行时角色                       | 职责                                                           |
| -------------------------------- | -------------------------------------------------------------- |
| **启动总监**                     | 拆解 Brief、调度专家并组装最终决策包。                         |
| **市场研究员**                   | 查找竞品、价格信号、市场背景和真实用户语言。                   |
| **方案架构师**                   | 设计定位、商品方案、定价和低成本验证假设。                     |
| **素材工作室**                   | 把策略转成商品页文案、内容方向和发布脚本。                     |
| **增长分析师**                   | 分析上传的 CSV/XLSX，发现变化、异常、分群和实验结果。          |
| **确定性 Preflight（系统门禁）** | 在交付前检查 7 件套、证据 URL、JSON/CSV 结构和不受支持的声明。 |

War Room 不是伪造状态的动画层。它展示每个 Agent 最新的真实线程、运行、任务、产物与失败状态。界面和 Phaser 场景都支持中英文实时切换。

面试 Demo 会把固定专家 Workflow 与自适应交付 Loop 分开：第一次 `present_files` 收到两个结构化 Preflight 违规项，主 Agent 只选择受影响的 2/7 份文件和受限编辑工具；第二次提交通过 7/7，并在使用 2/5 轮预算后满足成功停止条件。

## 三种使用方式

| 模式 | 适合场景 | 行为 |
| --- | --- | --- |
| **Flash** | 快速商品问题与早期类目扫描 | 单 Agent 直接调研和回答。 |
| **Ultra** | 完整上新前验证 | 启动总监调度专家并生成完整上新包。 |
| **Growth Analyst** | 店铺、投放或内容表现数据 | 使用上传的 CSV/XLSX 和确定性分析工具。 |

## 先讲证据，再讲结论

OpenSKU 使用三类证据标签：

- `observed_public`：有公开来源直接支持；
- `estimated`：基于可见证据计算或推断；
- `assumption`：仍需验证的明确假设。

这样可以避免一份看起来很完整的报告，悄悄把缺失数据变成虚构确定性。运行预算还会限制 LLM 调用次数、Token 和执行时间。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/)
- pnpm 10+
- nginx，或用于容器开发的 Docker Desktop

### 安装并启动

```bash
git clone https://github.com/CheungkiCheung/opensku.git
cd opensku
make quickstart
```

`make quickstart` 会打开交互式配置向导、安装前后端依赖并启动开发服务。启动完成后访问 [http://localhost:2026](http://localhost:2026)。

也可以分步执行：

```bash
make setup
make install
make dev
```

配置向导会生成本地配置文件，并提示添加至少一个支持的模型供应商 API Key。密钥、本地数据库和运行时数据都不应提交到 Git。

### Docker 开发

```bash
make docker-init
make docker-start
```

详细的本地开发、Docker、测试和故障排查方法见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 技术结构

```mermaid
flowchart LR
  B["商品 Brief 或上传数据"] --> G["FastAPI + LangGraph 网关"]
  G --> D["启动总监"]
  D --> M["市场研究员"]
  D --> O["方案架构师"]
  D --> A["素材工作室"]
  M --> E["证据台账"]
  O --> E
  A --> P["上新包"]
  E --> P
  G --> X["增长分析师"]
  X --> R["数据增长报告"]
  G --> W["实时 War Room"]
```

## 开发与测试

```bash
# 后端
cd backend
make test
make lint

# 前端
cd frontend
pnpm typecheck
pnpm test
pnpm test:e2e
```

后端单元测试不需要模型供应商密钥；真实模型应用流程仍需要至少配置一个 Provider。

### 可复现的产品级验证

OpenSKU 内置两条确定性全栈 Replay：浏览器连接真实的 Next.js 生产构建和 Gateway/Agent 运行时，只有 LLM 被替换为按输入 Hash 匹配的提交 Fixture。

```bash
# Mock UI E2E，默认使用独立 3101 端口
cd frontend
pnpm test:e2e

# Launch Ultra + Growth Analyst 全栈 Replay
pnpm test:e2e:opensku-replay

# Landing / Demo / War Room 少量视觉回归
pnpm test:e2e:visual

# 仅在 Prompt/工具合同有意变更后重建 Replay Fixture
cd ../backend
PYTHONPATH=. uv run python scripts/build_opensku_replay_fixture.py
```

Launch Replay 会验证三专家依赖链、7 件上新包、确定性 Preflight 失败、最小修订、二次校验以及 War Room checkpoint 同步。Growth Replay 会通过真实 API 上传 3 个 CSV，并验证数据检查、跨文件 Join、双比例显著性/置信区间以及最终 ship/extend/stop 决策。

CI 会在 `.github/workflows/quickstart-smoke.yml` 中验证文档化的本地 Quick Start 和两个生产镜像的构建/启动。`.github/workflows/live-llm-canary.yml` 提供每周定时与手动真实 LLM Canary；配置 `OPENSKU_CANARY_API_KEY`，以及可选的 `OPENSKU_CANARY_BASE_URL`、`OPENSKU_CANARY_MODEL` 后启用。没有密钥时会明确记录 skipped，不会伪装成通过。

### 兼容命名

OpenSKU 是唯一对外产品名。`deerflow.*` Python import、`DeerFlowClient`、`.deer-flow` 运行目录、`ecom-launch` / `data-inspector` Agent ID 以及部分 `DEER_FLOW_*` 变量仅作为兼容接口保留。新部署应优先使用 `OPENSKU_PROJECT_ROOT`、`OPENSKU_HOME`、`OPENSKU_CONFIG_PATH`、`OPENSKU_EXTENSIONS_CONFIG_PATH`、`OPENSKU_SKILLS_PATH` 和 `OPENSKU_HOST_BASE_DIR`。

## Roadmap

- [x] 带证据边界的电商上新流程
- [x] 中英文产品界面
- [x] 实时多 Agent War Room
- [x] CSV/XLSX 增长分析师
- [ ] 可公开分享的上新报告
- [ ] 可复用类目和平台模板
- [ ] 可复现的上新质量评测
- [ ] 一键部署在线 Demo

## 参与贡献

欢迎提交 Issue、案例、设计反馈和 Pull Request。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，产品想法和实现问题可以在 [GitHub Discussions](https://github.com/CheungkiCheung/opensku/discussions) 交流。

## 许可证与第三方声明

OpenSKU 的原创贡献使用 [MIT License](LICENSE)。必须保留的上游版权与许可文本、第三方归属和兼容性说明统一放在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
