# Durable Subagent Task Harness

> 日期：2026-07-24
> 阶段：Chat-first 重定向 Phase 1
> 模型调用：无；本阶段全部为确定性合同与持久化验证

## 完成内容

- 新增版本化 `ContextPacket`、`SubagentTask`、`SubagentTaskEvent` 和 `TaskLease`；
- 新增 queued、running、waiting、waiting_approval、blocked、completed、failed、cancelled、timed_out 状态机；
- 新增 Parent–Child lineage、依赖、attempt、priority、checkpoint、telemetry 和结构化 result/error；
- 新增 `MemorySubagentTaskStore`；
- 新增 SQLAlchemy `SubagentTaskRepository`、`subagent_tasks` 与 `subagent_task_events`；
- 所有任务变更使用乐观版本并追加严格递增事件；
- 事件支持持久化 idempotency key；
- 新增 Lease 获取、续期、释放和递增 fencing token；
- 过期 Lease 的旧 Worker 无法继续写状态；
- Gateway memory/SQLite/PostgreSQL 生命周期注册 Task Store 和 Manager；
- 持久化后端启动时将 Lease 已过期的 orphaned running Task 标记为 blocked，要求显式 resume 或 reassign，不盲目重试；
- 修复既有 `test_subagent_executor.py` 夹具错误替换整个 `deerflow.models` package、导致 `models.lifecycle` 无法导入的问题。

## 关键文件

- `backend/packages/harness/deerflow/subagents/tasks/`
- `backend/packages/harness/deerflow/persistence/subagent_task/`
- `backend/packages/harness/deerflow/persistence/models/__init__.py`
- `backend/app/gateway/deps.py`
- `backend/tests/test_subagent_task_models.py`
- `backend/tests/test_subagent_task_manager.py`
- `backend/tests/test_subagent_task_repository.py`

## RED

```text
uv run pytest -q \
  tests/test_subagent_task_models.py \
  tests/test_subagent_task_manager.py \
  tests/test_subagent_task_repository.py

结果：3 个 collection error
原因：deerflow.subagents.tasks 与 deerflow.persistence.subagent_task 尚不存在
```

## GREEN / REFACTOR / VERIFY

```text
聚焦 Durable Task + Gateway：24 passed
聚焦 Persistence / Run / Event / Executor / Task Tool：227 passed
通用后端非模型集合：4264 passed, 19 skipped
Commerce 非模型集合：433 passed, 23 real-model tests deselected
本次修改文件 Ruff：PASS
git diff --check：PASS
```

完整仓库不能使用一条默认 pytest 命令收集全部测试，因为根测试与 `tests/commerce` 存在同名模块；`--import-mode=importlib` 又与根测试依赖顶层 helper module 的方式冲突。本次分别运行两套集合，没有修改全局 pytest 行为。

全量 Ruff 仍报告 25 个既有 Legacy/OpenSKU 或其他脏工作区文件问题；本阶段没有批量格式化这些无关文件，本次触达文件严格 Ruff 通过。

## 已知边界

- 当前 DeerFlow `task` Tool 尚未使用 Durable Task Manager；
- 当前 `task` Tool 仍在内部启动后台线程后轮询到终态，Parent 仍被单次 Tool Call 阻塞；
- start/wait/follow-up/cancel/resume/reassign 将在 Phase 2 接入；
- 本阶段没有新的 Agent 行为，因此没有运行 DeepSeek V4；历史真实模型证据不能证明新动态生命周期。

## 下一阶段

将 Durable Task Manager 注入 Agent Runtime，扩展原生任务工具为 Parent 可控的异步生命周期，并使用 fresh DeepSeek V4 验证动态 0–N 委派、并行、取消、恢复和失败重规划。
