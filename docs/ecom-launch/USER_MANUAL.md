# OpenSKU 用户使用手册

> OpenSKU 是一个面向电商 SKU 上新的 AI 决策循环。它把粗糙新品想法、商品链接、竞品页面、公开信号、上传材料和早期反馈，整理成可执行的 Go / Pivot / Hold / Kill / Scale 判断。

---

## 目录

1. [产品简介](#产品简介)
2. [适用场景](#适用场景)
3. [核心概念](#核心概念)
4. [快速开始](#快速开始)
5. [推荐输入](#推荐输入)
6. [产出物说明](#产出物说明)
7. [数据边界](#数据边界)
8. [常见问题](#常见问题)

---

## 产品简介

OpenSKU 不是通用竞品分析工具，也不是固定的“7 天上新包生成器”。它的核心是一个自适应上新循环：

```text
阶段诊断 -> 证据判断 -> 宣传/测试调整 -> 下一轮实验 -> 知识沉淀
```

每次运行都会生成当前循环的 Launch Decision Pack。这个 pack 是一次决策快照，不是产品的全部边界。真实公司在发商品时，验证周期会随阶段、数据质量、渠道反馈、库存压力和经营约束调整，可能是 3 天、7 天、14 天或 30 天。

### OpenSKU 解决的问题

| 问题 | 传统做法 | OpenSKU 做法 |
|---|---|---|
| 没有后台数据，不知道新品能不能做 | 凭经验判断，或者只看竞品销量截图 | 标记私域指标不可用，用公开信号和可采集验证信号做阶段判断 |
| AI 容易编造 GMV、CVR、ROI 等指标 | 报告看起来完整，但决策风险很高 | 所有证据标为 observed_public、uploaded_real、estimated 或 unavailable |
| 上新计划变成一次性文档 | 做完报告后很少根据反馈调整 | 根据评论、样品反馈、内容表现、店铺数据或创作者反馈重排下一轮宣传计划 |
| 类目经验难以复用 | 每次都重新问、重新分析 | 输出 knowledge-deltas，沉淀类目、渠道、卖点、风险和实验经验 |

---

## 适用场景

OpenSKU 适合这些场景：

- 只有一个 SKU 想法，还没有样品或后台数据
- 已经有供应商、样品、商品规格或竞品链接，需要判断切入点
- 准备做短视频、直播、达人寄样、小红书/抖音种草等预热测试
- 已经软启动，拿到少量评论、客服问题、内容数据或店铺导出，需要调整宣传计划
- 想把每次上新的判断沉淀成可复用知识，而不是一次性报告

OpenSKU 不适合作为：

- 真实 GMV、CVR、ROI、复购率预测系统，除非用户上传真实数据
- 法务/质检/认证结论生成器
- 自动替代商家经营判断的全托管投放系统

---

## 核心概念

### Launch Stage

OpenSKU 会先判断当前 SKU 所处阶段：

| 阶段 | 含义 | 常见下一步 |
|---|---|---|
| `idea_only` | 只有想法或模糊方向 | 验证需求、受众、痛点和核心卖点 |
| `supplier_sample` | 有供应商、样品、规格或报价 | 验证规格可信度、样品反馈、价格接受度 |
| `pre_launch_test` | 准备上线前的小规模内容/页面/预约测试 | 验证 hook、页面 claim、创作者 brief、预购意向 |
| `soft_launch` | 已经小流量上线，有少量真实反馈 | 解释反馈，调整宣传计划和下一轮实验 |
| `scale_iterate` | 已经有可用信号，准备扩大或优化 | 优化渠道、库存、内容节奏、页面证据和预算规则 |

### Decision

每次运行都会给出一个方向：

| 决策 | 什么时候用 |
|---|---|
| `Go` | 证据足够支持进入下一轮验证或小规模上线 |
| `Pivot` | 方向可做，但受众、卖点、价格、渠道或页面证据需要调整 |
| `Hold` | 数据缺口太关键，先补规格、政策、样品或真实反馈 |
| `Kill` | 核心假设风险过高，不建议继续投入 |
| `Scale` | 已有足够早期信号，可以扩大测试或进入优化阶段 |

### Launch Decision Pack

Launch Decision Pack 是当前循环的文件产出集合。它保留当前代码和 UI 依赖的文件名，但语义已经从“固定周期产物”改为“当前循环快照”。

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm
- uv

### 本地启动

```bash
git clone git@github.com:CheungkiCheung/OpenSKU.git
cd OpenSKU

make install
make config
make dev
open http://localhost:2026
```

如果仓库远程仍是旧名称，使用实际仓库地址 clone 即可，本地命令保持一致。

### 推荐提问

无后台数据：

```text
我想做一个 99-199 元的通勤咖啡杯，但没有任何店铺后台数据。
请用公开信号判断当前上新阶段、是否值得测试，并输出 Launch Decision Pack 和下一轮实验方案。
```

有竞品链接：

```text
这是一个公开竞品/商品链接。请不要假设我有销量或转化数据。
只基于可见公开信号和页面信息，判断是否值得小规模上新验证，并指出下一轮该调整什么宣传重点。
```

有早期反馈：

```text
我已经发了 5 条短视频和 2 个达人 brief，下面是评论、收藏、询单和样品反馈。
请判断这个 SKU 是 Go、Pivot、Hold、Kill 还是 Scale，并重排下一轮内容和宣传计划。
```

---

## 推荐输入

OpenSKU 可以接受：

- 商品想法、目标价格、目标平台、目标人群
- 竞品链接、商品页截图、评论截图、短视频脚本、直播话术
- 供应商报价、样品规格、检测报告、售后政策、包装信息
- 内容表现、客服问题、评论反馈、退货原因、询单记录
- CSV、Markdown、图片、PDF、表格等上传材料

输入越接近真实经营约束，输出越像可执行计划。没有私域数据也可以运行，但系统必须把缺失指标标为 unavailable。

---

## 产出物说明

默认 `validate-launch` 会生成并展示这些文件：

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

### 1. `launch-war-room.html`

当前循环的可视化决策面板。应包含：

- SKU 简介
- Launch Stage 诊断
- Go / Pivot / Hold / Kill / Scale 建议
- 核心受众和卖点
- 关键证据与不确定性
- Listing / content / promotion 的下一步
- 当前循环限制

### 2. `evidence-ledger.json`

证据账本。每条证据都应记录来源、类型、置信度和适用范围。

```json
[
  {
    "id": "ev_001",
    "claim": "目标用户在通勤场景中反复提到防漏和单手开合问题",
    "evidence_type": "observed_public",
    "source_type": "public_review",
    "confidence": "medium"
  }
]
```

### 3. `competitor-table.csv`

竞品和公开页面对比。重点不是“谁销量最高”，而是可观察的价格带、卖点、页面证据、评论痛点和可切入空位。

### 4. `positioning-brief.md`

SKU 定位和上新判断。应包含：

- 目标用户
- Job to be done
- 核心承诺
- 差异化点
- 风险假设
- Kill 条件
- 下一轮实验方向

### 5. `listing-pack.md`

商品页文案草案。应把 claim 分为：

- 可直接使用
- 草稿可用但需补证据
- 需要规格/检测/政策确认
- 暂时不要使用

### 6. `content-pack.md`

内容和宣传素材草案。可包含短视频 hook、脚本、达人 brief、评论回复、直播话术和社媒帖子。

### 7. `launch-calendar.csv`

下一轮自适应验证 sprint。它不一定是 7 天，应根据阶段选择 3、7、14 或 30 天。

```csv
day,objective,experiment,asset,channel,validation_signal_to_collect,decision_rule,owner,expected_output
```

推荐节奏：

| 阶段 | 常见周期 |
|---|---|
| `idea_only` | 3-7 天 |
| `supplier_sample` | 7-14 天 |
| `pre_launch_test` | 7-14 天 |
| `soft_launch` | 7-30 天 |
| `scale_iterate` | 14-30 天 |

### 可选循环文件

当用户上传真实反馈，或系统发现可复用经验时，可以额外输出：

```text
launch-state.json
promotion-replan.md
knowledge-deltas.json
```

- `launch-state.json`: 当前 SKU 阶段、可用数据、缺失数据、决策状态
- `promotion-replan.md`: 观察信号、解释、宣传调整、下一轮测试和停止/继续规则
- `knowledge-deltas.json`: 可复用类目、渠道、卖点、风险和实验经验

---

## 数据边界

OpenSKU 可以使用：

- 公开搜索结果、公开商品页、公开评论、公开文章、问答和 SEO 页面
- 用户上传的规格、截图、CSV、店铺导出、检测报告、政策文件
- 明确标注的估算和假设

OpenSKU 不能凭空生成：

- GMV、CTR、CVR、ROI、广告花费、销量、退款率、复购率、真实市场份额
- 检测结论、安全认证、质保/退货政策、真实用户证言
- 小红书、抖音、淘宝、京东、拼多多、Amazon、Shopify、TikTok Shop 的私域后台数据

如果数据不可用，正确做法是写 `unavailable`，然后给出如何采集该信号。

---

## 常见问题

### Q1：OpenSKU 真的只做 7 天计划吗？

不是。7 天只是 demo 默认节奏。真实上新要看阶段和数据质量：idea 阶段可以 3-7 天，样品和预热阶段通常 7-14 天，软启动和放量阶段可能需要 7-30 天。

### Q2：没有店铺后台数据还能用吗？

可以。OpenSKU 会用公开信号、竞品页面、评论、内容反馈、询单、样品反馈等轻量信号做判断。但它必须把 GMV、CVR、ROI 这类私域指标标为 unavailable。

### Q3：如果我上传真实店铺数据会怎样？

OpenSKU 会把上传数据标为 `uploaded_real`，解释它如何改变判断，并调整下一轮宣传或实验计划。

### Q4：它和普通竞品分析有什么区别？

普通竞品分析通常停在“别人怎么卖”。OpenSKU 要回答“我现在处在哪个上新阶段、该 Go/Pivot/Hold/Kill/Scale、下一轮测试和宣传具体怎么改、哪些知识要沉淀”。

### Q5：结果能直接上线使用吗？

部分文案可以作为草稿，但涉及功效、规格、认证、质保、检测、用户证言的 claim 必须先用真实材料确认。OpenSKU 会把这些写进 claim readiness 矩阵。

---

## 技术支持

- 核心项目入口：`README.md`
- EcomLaunch MVP 文档：`docs/ecom-launch/README.md`
- 手动运行提示词：`docs/ecom-launch/manual-run-prompt.md`
- Agent 规格文档：`docs/plans/ecom-launch-agent-spec.md`

---

**OpenSKU**: 把电商上新从“一次性报告”变成可评测、可调整、可沉淀的决策循环。
