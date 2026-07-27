# Commerce PostgreSQL 与 Skill Evolution Release

> 日期：2026-07-26
> 分支：`feature/commerce-case-agent`
> 状态：本轮完成
> 模型：本轮所有评测请求均为 fresh `deepseek-v4-flash`，`max_retries=0`

## 1. PostgreSQL 真实集成

之前文档只接受 SQLAlchemy PostgreSQL DDL 编译，没有真正连接数据库。本轮使用仓库已经声明的 `postgres` extra 和本机 PostgreSQL 16 临时集群，运行：

```bash
cd backend
uv sync --extra postgres
COMMERCE_TEST_POSTGRES_URL=postgresql+asyncpg://...
uv run pytest tests/commerce/persistence/test_postgres_integration.py -q -s
```

结果：

```text
1 passed in 1.22s
```

测试实际完成：

1. 从空库执行 Commerce Alembic `20260718_0001` 到 `20260719_0010` 全部迁移；
2. 写入 Case、Run、Lease 和 Goal Loop Checkpoint；
3. 关闭 SQLAlchemy Engine，模拟进程/连接边界；
4. 重建 Engine 后读取同一 Run、Checkpoint 和 Domain Event；
5. 在 Lease 过期后由新 Worker 接管，fencing token 从 `1` 增加到 `2`；
6. 验证最新 Checkpoint 与接管前完全一致。

这证明了应用级持久化、恢复和 fencing 合同；不把它夸大成生产多节点 PostgreSQL 压测或 HA 证明。

## 2. Skill Evolution 真实门禁

### 2.1 Semantic Evaluator

真实 Semantic Gate：

```text
2 passed in 7.36s
```

覆盖保留 unknown / 不把相关性写成因果，以及拒绝 `root cause` / `dominant driver` 等越界结论。

### 2.2 单 Case Experiment

Control/Candidate、两次 repetition：

```text
1 passed in 36.43s
```

共 4 个 Run、8 个唯一 Provider Request ID，绑定 Prompt / Context / Router / Skill 版本和 Token/Latency Pareto 报告。

### 2.3 四 Case Holdout

首次真实运行发现 Semantic Evaluator 返回了合法 JSON 外壳，但自由文本 `explanation` 超过 1,500 字符，导致版本化 Schema 正确 fail closed。修复过程：

```text
真实 Holdout 失败：explanation > 1500
→ RED：新增超长 explanation 合同测试
→ Prompt：限制 explanation ≤ 300 字符，禁止 revision commentary / chain-of-thought
→ Parser：超长自由文本不进入审计，替换为固定安全说明并追加 explanation-overlong-discarded
→ 保留结构化布尔判定与 reason_codes
→ 重新执行真实 Holdout
```

确定性合同：

```text
13 passed
```

重新执行真实四 Case Holdout：

```text
1 passed in 107.52s
Candidate 8/8
32 unique model requests
retry=0
```

这不是放宽 Schema：只有自由文本说明被丢弃，`useful`、`unknowns_preserved`、`action_guidance_is_bounded`、因果安全布尔值和审计码仍由模型结构化输出决定，并继续接受确定性 Guard。

### 2.4 Shadow

真实 Shadow 继续验证两个隔离 Run：

```text
3 passed in 22.39s
```

包括两个 Semantic Gate 和 Candidate Shadow。Shadow 只读，不修改 Case，Candidate 仍保持 `shadow`，没有用户授权不会变成 Active。

## 3. 当前治理边界

- 内部 Artifact Connector 已通过真实文件写入、SHA-256 读回和可验证归档回滚；
- 外部商家 Connector 仍 fail closed，不伪造平台账号、广告或订单写入；
- Skill Candidate 已经具备 Candidate → Offline Evaluated → Shadow → Human Review → Active / Rollback 状态机；
- 当前真实 Candidate 的最后一步 Human Promotion 仍需要用户明确授权，因此不自动调用 Promotion API；
- PostgreSQL 已有真实本地集成，但生产多节点 CAS、Workspace membership 和浏览器 Agent Release 仍未完成。
