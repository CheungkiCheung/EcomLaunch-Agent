# Commerce Chat Task/Event 前端合同

> 日期：2026-07-26  
> 阶段：Phase 4A，React Chat 布局实现前  
> 模型：本阶段为纯 API / ViewModel / UI 机械合同，不调用 LLM

## Outcome

完成 Chat 紧凑 Subagent 状态和未来游戏化协作空间共用的数据合同：

```text
Gateway Durable Task API
→ strict Zod parsing
→ Task/Event cursor snapshot
→ pure visual-state reducer
→ shared run activity ViewModel
→ Chat compact card / collaboration scene
```

这一步不实现 Chat 页面视觉布局，视觉母版仍等待用户选择。

## Gateway API Client

新增：

```text
loadCommerceRunSubagentTasks
loadCommerceSubagentTaskEvents
loadCommerceRunTaskActivity
loadCommerceRunTaskActivityPage
```

对应真实 Gateway：

```text
GET /api/runs/{run_id}/subagent-tasks
GET /api/subagent-tasks/{task_id}/events?after_seq=...&limit=...
```

合同：

- 使用 authenticated Gateway fetch；
- Task、ContextPacket、Tool Policy、Budget、Telemetry、Lease 和时间字段严格 Zod 校验；
- Event 使用 append-only `seq` 和显式 cursor；
- `has_more` 不被前端猜测；
- 404、非法 JSON 和 Schema 漂移 fail closed；
- 不读取 reasoning_content、原始 Tool 参数或 Secret。

## Incremental Activity Hook

新增：

```text
mergeCommerceRunTaskActivityPages
useCommerceRunTaskActivity
```

行为：

- 每个 Task 独立保存 `next_after_seq`；
- 下一次请求只读取该 Task 游标之后的事件；
- 游标只前进、不回退；
- 重复 `seq` 保留第一次观察到的事件，不重放动画或状态迁移；
- 轮询串行执行，前一次请求未结束时不会重叠启动下一轮；
- Run 切换、手动刷新或组件卸载会 Abort 旧请求；
- API 失败保留最后一次可信活动快照并显式暴露 error；
- Chat 和协作空间只消费同一 `CommerceRunTaskActivityViewModel`。

## Visual State Reducer

新增：

```text
reduceCommerceTaskVisualState(snapshot, events)
```

输出：

```text
status:
queued | working | waiting | approval | blocked | completed | failed | cancelled | timed_out

activity:
idle | dispatching | tool | message | waiting | blocked | completed | failed | cancelled | timed_out
```

规则：

- Event 按 `seq` 排序；
- 重复 `seq` 只处理一次；
- 未知 Event 显式保留，不改变状态；
- 空 Event 使用持久化 Task 快照；
- `task.tool_result` 只显示后端脱敏 Tool 名称；
- `task.message` 只显示后端脱敏 Preview；
- `waiting_approval` 和 `blocked` 不显示为忙碌；
- `failed`、`cancelled` 和 `timed_out` 保持三个可区分的终态；
- `task.lease_released` 不会把失败、取消、超时、阻塞或等待状态错误改回 idle；
- 延迟到达的 Tool / Message / Lease Event 仍可补充脱敏审计摘要，但不能让 approval、waiting、blocked 或终态 Actor 重新显示为忙碌；
- 没有新事件时不播放假活动。

权威设计合同：

```text
docs/design/commerce-chat-task-visual-state-contract.md
```

## Shared Run Activity ViewModel

新增：

```text
buildCommerceRunTaskActivityViewModel
```

它为 Chat 和协作空间提供同一份：

- Task 列表；
- Profile 中文标签；
- 状态和当前活动；
- 最后 Tool；
- Skill、Tool、Budget；
- active / waiting / blocked / completed / failed / cancelled / timed_out 汇总；
- 乱序、未知事件和未完整分页诊断。

页面不得绕过 ViewModel 自己从消息文案推断状态。

## Collaboration Scene Projection

新增 renderer-neutral：

```text
buildCommerceCollaborationSceneViewModel
```

它不实现 Canvas 或人物美术，只冻结真实事件到场景的纯投影：

- 一个唯一 `task_id` 最多对应一个 Actor；
- `explore / analyst / verifier / operator` 只决定工作区标签，不决定状态；
- `task.tool_result` 才能产生 Tool 道具；
- waiting approval、blocked、completed、failed、cancelled、timed_out 均保持独立场景语义；
- 没有 Task 时返回空场景，不生成固定 Crew 或假角色；
- 事件页不完整、乱序、未知 Event 和重复 Task 投影显式形成 warning；
- Canvas、Pixi 和 reduced-motion 列表后续必须消费同一 Scene ViewModel。

## Legacy War Room 基线恢复

全量 TypeScript 最初被以下缺口阻塞：

```text
tests/unit/components/commerce/war-room.test.tsx
→ @/components/commerce/war-room 不存在
```

仓库已有 2026-07-23 批准的 `war-room-visual-v1` 和完整 Event-backed ViewModel，因此补回只读 `CommerceWarRoomView`：

- 事件泳道；
- Evidence 构成；
- Checkpoint；
- 领域事件流；
- Quiet state；
- Case / Run 高级入口；
- 无模型、Token、Retry、Chat Composer 或假动画。

该组件用于保留旧高级详情和恢复基础门禁，不进入新 Chat 默认导航，也不替代未来 Task Event 驱动的游戏化协作空间。

## Lint Hardening

顺带清理了阻塞仓库级 `pnpm check` 的机械问题：

- `RegExp#exec`；
- Pixi `Texture` type import；
- optional chaining；
- async setup 显式 `void`；
- 首次 Pixi 同步改为最新输入 Ref，避免 effect 依赖漂移；
- import order；
- `String#includes`。

不改变 Legacy EcomLaunch 行为。

## Verification

```text
Vitest：55 files / 306 tests passed
ESLint：PASS
TypeScript：PASS
Next.js production build：PASS
Static routes：79 generated
Chromium Playwright mechanical UI：38 passed
git diff --check：PASS
```

生产构建仍有一个原有 Turbopack NFT trace warning，来源：

```text
next.config.js
→ mock artifact route
```

它不影响编译、TypeScript 或页面生成，本阶段未扩大范围修改 mock filesystem route。

## Visual Decision

已通过内置 ImageGen 生成三套 Chat 主界面预览：

```text
A：墨白工作台（推荐）
B：暖灰协作
C：深色专注
```

选择记录：

```text
docs/design/commerce-chat-visual-directions.md
```

在用户确认 A / B / C / A+B 之前，不实现新的 Chat 布局和协作空间视觉。
