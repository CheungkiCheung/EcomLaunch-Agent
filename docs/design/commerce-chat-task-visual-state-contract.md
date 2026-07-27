# Commerce Chat Task → Visual State 合同

> 状态：Phase 4 实现前合同  
> 日期：2026-07-26  
> 权威来源：`SubagentTask` 快照与 `/api/subagent-tasks/{task_id}/events`

## 1. 目标

Chat 内紧凑 Subagent 状态和按需游戏化协作空间必须从同一份结构化 Task/Event 数据投影，不能各自根据聊天文本或动画计时器猜状态。

```text
SubagentTask snapshot + append-only TaskEvent
→ pure reducer
→ CommerceTaskVisualState
→ Chat compact card / collaboration scene
```

## 2. 输入

Task 快照读取：

- `task_id`、`thread_id`、`run_id`、`parent_task_id`；
- `subagent_type`、`description`；
- `status`；
- `context_packet.available_skills`；
- `context_packet.available_tools`；
- `context_packet.budget`；
- `created_at`、`updated_at`、`completed_at`。

已知 Task Event：

```text
task.created
task.queued
task.running
task.waiting
task.waiting_approval
task.blocked
task.completed
task.failed
task.cancelled
task.timed_out
task.resumed
task.recovery_blocked
task.lease_acquired
task.lease_renewed
task.lease_released
task.tool_result
task.message
```

事件通过 `seq` 排序；同一 `seq` 只接受第一条，重复事件不重复播放或累加。

## 3. 输出

视觉状态：

```text
queued | working | waiting | approval | blocked | completed | failed | cancelled | timed_out
```

事件活动：

```text
idle | dispatching | tool | message | waiting | blocked | completed | failed | cancelled | timed_out
```

`working` 不等于“模型此刻正在调用”。它只表示快照或事件明确处于 `running`。没有新事件时，界面保持最后已知状态，不显示假忙碌。

## 4. 映射

| Task/Event                                | Visual status | Activity      | UI 表达                      |
| ----------------------------------------- | ------------- | ------------- | ---------------------------- |
| 快照 `queued` / `task.created`            | `queued`      | `idle`        | 已排队，不播放忙碌动画       |
| `task.running` / `task.resumed`           | `working`     | `dispatching` | 已开始执行                   |
| `task.lease_acquired` / `renewed`         | 保持          | `dispatching` | 任务已被 Worker 接管         |
| `task.tool_result`                        | 保持          | `tool`        | 显示结构化 Tool 名称，可展开 |
| `task.message`                            | 保持          | `message`     | 显示脱敏消息预览，可展开     |
| `task.waiting`                            | `waiting`     | `waiting`     | 等待依赖或外部条件           |
| `task.waiting_approval`                   | `approval`    | `waiting`     | 等待人工审批                 |
| `task.blocked` / `recovery_blocked`       | `blocked`     | `blocked`     | 显示阻塞原因和恢复入口       |
| `task.completed`                          | `completed`   | `completed`   | 完成，可查看结果与 Evidence  |
| `task.failed`                            | `failed`      | `failed`      | 显示失败原因                 |
| `task.cancelled`                         | `cancelled`   | `cancelled`   | 显示用户或策略取消           |
| `task.timed_out`                         | `timed_out`   | `timed_out`   | 显示时间或预算超时           |
| 未知事件                                  | 保持          | 保持          | 记录未知事件，不改变状态     |

## 5. 安全与降级

- 不渲染 reasoning_content、原始 Tool 参数或 Provider Secret；
- 后端只提供脱敏 `content_preview` 和 Tool Event 摘要；
- 乱序 Event 先排序，UI 可显示 `wasReordered` 诊断但不得重复动作；
- 快照作为当前状态基线，已知状态 Event 只按序更新；
- 空 Event 列表不等于运行中，使用快照状态；
- 延迟到达的 Tool、Message 或 Lease Event 可以补充脱敏摘要，但只有 `working` 状态能改变为 tool / message / dispatching 活动；审批、等待、阻塞和终态不得被重新播放为忙碌；
- 未知状态或事件保持最后已知状态，不能推断 `working`；
- reduced-motion 只去掉移动和闪烁，不改变状态语义。

## 6. 协作空间角色映射

协作空间不是固定角色 War Room：

- 每个可见小人或工位对应一个真实 `task_id`；
- `subagent_type` 只决定外观标签，不决定状态；
- `task.tool_result` 决定角色手上的工具或道具；
- `task.waiting_approval` 决定角色停在审批点；
- `task.blocked` 决定角色进入阻塞态；
- `task.completed` 决定角色进入完成态；
- `task.failed`、`task.cancelled` 和 `task.timed_out` 分别决定失败、取消和超时终态；Lease 释放不把终态改回空闲；
- 没有对应 Task/Event 的角色、走动和忙碌不得出现。

## 7. 当前实现边界

当前已完成严格 Task/Event API 解析、纯 TypeScript reducer、共享 Run activity ViewModel、增量事件页合并、可取消的轮询 Hook，以及 renderer-neutral `CommerceCollaborationSceneViewModel`。每个 Task 使用自己的 `next_after_seq`，游标只前进，重复 `seq` 保留第一次观察到的事件；Run 切换和组件卸载会终止旧请求。九个持久化状态均有确定性投影测试，`failed`、`cancelled` 和 `timed_out` 不再被折叠，Lease 释放不会清空终态。协作空间投影保证一个唯一 `task_id` 最多产生一个 Actor，Tool 道具、审批、阻塞和终态全部来自结构化 Event，并显式暴露分页未完成、乱序、未知和重复投影警告。Chat 紧凑状态、可选协作空间和原创 ImageGen 角色/场景/工位资产已经实现；图像只消费该合同，不决定状态。当前剩余验收是使用同一条 fresh DeepSeek V4 真实 Run 完成 Chat、协作空间、Drawer、移动端与 reduced-motion 的最终视觉 Release Gate。
