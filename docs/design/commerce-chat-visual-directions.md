# Commerce Chat 主界面视觉方向

> 日期：2026-07-26  
> 工具：内置 ImageGen，`ui-mockup` 预览模式  
> 状态：历史三套预览仍保留；用户已确认 Chat-first + 按需协作空间，React 与原创 ImageGen 运行时资产 v1 已实现

> 最新决策记录见：`docs/design/commerce-chat-war-room-visual-v2.md`

## 页面目标

默认入口是中文持续 Chat，不是 Dashboard、Case 工作台或固定 War Room。

共同信息架构：

```text
左侧：新建任务 + 历史任务
中央：上传数据、自然提问、中文回答
回答下方：一条紧凑可折叠 Subagent 活动摘要
按需入口：查看协作空间
底部：文件上传 + 持续追问 Composer
```

共同状态：

- 文件：`订单数据.zip`；
- 用户问题：`最近履约变差了，帮我定位问题`；
- 回答结构：`现象 / 阶段定位 / 反证与限制 / 下一步`；
- Subagent：`检查数据能力 / 分析履约变化 / 独立核验`；
- 活动状态只来自 `CommerceTaskVisualState`；
- 无常驻右侧 Inspector；
- 无默认 Dashboard、KPI 墙或大图表；
- 无鹿、无 Marvis 品牌、无 Codex/Claude Logo；
- 默认 Chat 不出现游戏小人，协作空间按需打开。

## 方向 A：墨白工作台

最接近用户提出的 Codex 风格：

- 冷静的灰白画布和深灰文字；
- 极细边框与大量留白；
- 少量靛蓝只用于 active / verified；
- Subagent 是一条紧凑状态行，不形成三张大卡；
- 整体最克制，最适合求职演示中突出 Agent 行为而不是 UI 装饰。

推荐度：**首选**。

## 方向 B：暖灰协作

在 Chat-first 基础上增加轻微电商运营亲和感：

- 暖象牙白、石灰色分隔；
- 鼠尾草绿和低饱和琥珀表示 verified / waiting；
- 圆角更柔和，但不使用重卡片；
- 比 A 更像面向业务人员的产品，比 A 稍弱“Agent 工程工具”气质。

推荐度：适合作为 A 的配色备选。

## 方向 C：深色专注

深色专业工作台：

- 墨黑/石墨背景；
- 暖白文字、低饱和蓝绿状态色；
- 更强调运行过程和专业工具感；
- 适合开发者与深度使用场景，但电商运营用户长时间阅读可能不如浅色自然。

推荐度：适合后续深色主题，不建议作为唯一默认母版。

## 推荐决策

建议选择 **A：墨白工作台** 作为默认浅色母版，同时吸收 B 的轻微暖色状态语义；C 保留为后续深色主题，不在首轮并行实现。

## 选择后实施范围

选择母版后才开始：

1. 复用 DeerFlow Workspace / Thread / Message / Composer；
2. 左侧导航收敛为新建任务和历史任务；
3. 新增 Commerce 数据上传提示与自然回答排版；
4. 将 Durable Task/Event 投影接入紧凑 Subagent 状态；
5. Evidence / Artifact / Approval 按需展开；
6. 旧 `/commerce` Master Shell 降级为高级详情入口；
7. 单元测试、TypeScript、Lint、构建和真实浏览器视觉 QA；
8. Agent 浏览器 E2E 连接真实后端和 fresh DeepSeek V4。

## 实现差异记录

React 页面已经实现。默认 Chat 继续使用 DeerFlow Design Token、真实中文字体和结构化 Task/Event 数据；协作空间使用原创生成的空场景、四个通用 Profile 角色和四类工位资产。完整 Prompt、透明去底过程、SHA-256、Task 映射和机械浏览器截图见 `docs/design/commerce-collaboration-imagegen-assets-v1.md`。生成图不包含运行时文字，也不决定 Task 状态。
