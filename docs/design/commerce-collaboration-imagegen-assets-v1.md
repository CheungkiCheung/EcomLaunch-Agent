# Commerce 协作空间 ImageGen 运行时资产 v1

> 日期：2026-07-27  
> 生成路径：Codex 内置 ImageGen（built-in）  
> 用例：`stylized-concept`  
> 状态：已选中、已进入运行时、已完成机械浏览器视觉检查  
> 业务状态来源：`CommerceCollaborationSceneViewModel`，图像本身不决定 Task 状态

## 1. 结论

协作空间已经从 CSS 拼接角色和工位升级为原创生成资产，但没有改变 Task/Event 合同：

```text
SubagentTask snapshot + append-only TaskEvent
→ CommerceTaskVisualState
→ CommerceCollaborationSceneViewModel
→ 生成背景 + 角色 Profile 精灵 + Task 工位精灵
```

- 一个真实 `task_id` 最多显示一个角色和一个工位；
- 没有 Task 时只显示空房间，不创建固定 Crew；
- 角色精灵只表达通用 `explore / analyst / verifier / operator` Profile；
- 工位精灵由结构化 `station` 决定；
- `task.tool_result` 对应的真实 Tool 仍通过“正在使用”标签和详情 Drawer 表达，不从角色手中通用装备反推 Tool；
- `queued / working / waiting / approval / blocked / completed / failed / cancelled / timed_out` 仍由真实 Task/Event 决定；
- 只有 `working` 会启用轻微动画，并受 `prefers-reduced-motion` 降级控制。

## 2. 最终资产

### 场景

- `frontend/public/commerce/collaboration/commerce-room-v1.png`
- SHA-256：`2e2f8969d7e16c7f05c58c0cb9c253500814ae9c5c6a32378275b3e95bdeebae`

### 角色

| Profile | 文件 | SHA-256 |
| --- | --- | --- |
| `explore` | `frontend/public/commerce/collaboration/actors/explore-v1.png` | `a2d29baf32f5fc6201b4a3708d6edda739f1dd6605d857096efd03a9fd1d9502` |
| `analyst` | `frontend/public/commerce/collaboration/actors/analyst-v1.png` | `c85445c19a64c2b1db3a7fed905a8661dc2eec3a8de6cc2ad10370d18a0b9a7e` |
| `verifier` | `frontend/public/commerce/collaboration/actors/verifier-v1.png` | `e69dbf6669f0124c2237c69f2825dea857b227938e10d9737b1f97a1531fa96f` |
| `operator` | `frontend/public/commerce/collaboration/actors/operator-v1.png` | `2d041a5df62ba8cc53d47bae425fe22bcd5915f320eba44b6b340968d0ba0887` |

未知 Profile 使用中性的 `operator` 视觉回退，但用户可见 Profile 标签仍显示真实 `subagent_type`，不会把未知类型伪装成固定业务角色。

### 工位

| Runtime station | 文件 | SHA-256 |
| --- | --- | --- |
| `intake` | `frontend/public/commerce/collaboration/stations/intake-v1.png` | `09312ed57b0fc48a835951446f7819a536dab1145ac8892bc79ea60402aa6e54` |
| `analysis` | `frontend/public/commerce/collaboration/stations/analysis-v1.png` | `669082e7eecf765899e7fe0302d5398d90daf4a1a2ee3dd6106c8b5bee8417b1` |
| `verification` | `frontend/public/commerce/collaboration/stations/verification-v1.png` | `1eed85cfa0df7010f746132270863d9be7935eee4d9c27611fc50e81347cc531` |
| `action / approval / delivery / recovery / general` | `frontend/public/commerce/collaboration/stations/recovery-v1.png` | `9d56a1202dbda2bde41c7ad36e4c571403d873e19d1c571033ce870e97c97d02` |

## 3. 最终 Prompt

### 3.1 角色母版

```text
Use case: stylized-concept
Asset type: production character sprite master sheet for a Chinese ecommerce AI agent collaboration space
Primary request: create four original full-body miniature game characters in one perfectly aligned character lineup, representing generic dynamic subagent profiles: data explorer, metric analyst, independent verifier, and action operator. They are not a fixed crew; each is a reusable visual profile for a real runtime task.
Scene/backdrop: perfectly flat solid #ff00ff chroma-key background for later removal; absolutely uniform, no floor plane, no shadow, no gradient, no texture.
Subject: four distinct adult office-worker game avatars, one per equal-width column, standing front three-quarter view, full body visible, generous separation and padding. Explorer carries a compact data scanner/tablet with muted teal accent. Analyst carries a small chart slate with muted coral-blue accent. Verifier carries a checklist magnifier with muted indigo accent. Operator carries a compact action clipboard/tool case with muted amber accent. Diverse but understated appearances, friendly and professional, gender-balanced, no mascot animals.
Style/medium: premium original 3D miniature diorama game art, soft clay-like materials with crisp readable silhouettes, refined mobile strategy-game character quality, calm rather than cartoon-noisy, compatible with a warm-white Codex-inspired productivity UI.
Composition/framing: wide horizontal lineup, exact equal spacing, same camera, same scale, same eye line and base line, no overlap, characters centered in their columns; show complete shoes and all props.
Lighting/mood: soft neutral studio lighting contained on subjects only, calm, capable, trustworthy.
Color palette: warm white, stone gray, charcoal, muted teal, muted coral-blue, indigo, and amber. Do not use #ff00ff anywhere on characters or props.
Constraints: no text, no labels, no logos, no brand marks, no deer, no animal mascots, no Codex/Claude/DeerFlow/Marvis likeness, no weapons, no exaggerated anime proportions, no cast shadow, no contact shadow, no reflection, no watermark. The background must remain a single uniform #ff00ff color for clean chroma-key extraction.
```

### 3.2 空场景母版

```text
Use case: stylized-concept
Asset type: empty wide background plate for a Task/Event-driven ecommerce AI agent collaboration-space page
Primary request: create an original bright miniature office operations room that can host dynamically placed game characters and workstations. The room must feel like a calm productivity workspace, not a dashboard and not a fixed crew scene.
Scene/backdrop: warm-white micro-diorama office viewed from a high three-quarter isometric angle. A large clean central work floor with four softly suggested zones: data intake at upper-left, metric analysis at upper-right, evidence verification at lower-left, action/recovery at lower-right. The zones are communicated only through subtle floor inlays and wall alcoves, leaving generous empty space for runtime characters and station overlays. Include restrained shelves, a few plants, soft wall lights, cable channels, and a small evidence archive wall. No people and no active screens.
Style/medium: premium original 3D miniature game environment, soft clay and painted-wood materials, refined mobile strategy-game diorama quality, compatible with a warm-white Codex-inspired Chinese productivity interface.
Composition/framing: wide 16:9 composition, symmetrical enough for responsive UI cropping, strong open negative space in the center and each zone, clean readable silhouettes, no objects cut off at edges.
Lighting/mood: soft daylight from upper-left, quiet, capable, welcoming, low visual noise.
Color palette: warm ivory, stone, pale oak, charcoal accents, small muted teal, coral-blue, indigo, and amber details.
Constraints: background environment only; no people, no characters, no animals, no deer, no logos, no brand marks, no readable text, no faux UI labels, no watermark, no dramatic neon, no dark cyberpunk, no busy command-center monitors, no Marvis/Codex/Claude/DeerFlow likeness. Keep the central floor and four placement zones visually uncluttered so real task actors can be composited later.
```

### 3.3 工位母版

```text
Use case: stylized-concept
Asset type: production workstation prop sprite master sheet for a Task/Event-driven ecommerce AI agent collaboration space
Primary request: create four original miniature workstation props in one aligned sheet, corresponding to runtime stations: data intake, metric analysis, evidence verification, and action/recovery. These are reusable visual props, not a fixed business crew.
Scene/backdrop: perfectly flat solid #ff00ff chroma-key background for later removal; one uniform color, no floor plane, no shadow, no gradient, no texture.
Subject: four distinct compact isometric workstation clusters, one per equal-width column with generous separation. Data intake: small ingestion dock with stacked neutral data trays and a scanner, muted teal accent. Metric analysis: compact desk with abstract bar-and-line display shapes, muted coral-blue accent. Evidence verification: inspection table with magnifier lamp, checklist trays, and shield/check motif shapes, muted indigo accent. Action/recovery: compact planning bench with approval stamp, clipboard trays, and tool case, muted amber accent. All screens must use abstract unreadable shapes only.
Style/medium: premium original 3D miniature diorama game props, soft clay and painted-wood materials, same refined warm-white style as a calm productivity workspace, crisp silhouettes suitable for compositing over an isometric office background.
Composition/framing: wide horizontal lineup, exact equal spacing, same isometric camera and scale, each workstation fully visible and centered in its column, no overlap, generous padding.
Lighting/mood: soft neutral studio lighting on props only, calm and professional.
Color palette: warm ivory, pale oak, stone gray, charcoal; muted teal, coral-blue, indigo, amber accents. Do not use #ff00ff anywhere on props.
Constraints: no people, no characters, no animals, no deer, no readable text, no numbers, no logos, no brand marks, no watermark, no cast shadow, no contact shadow, no reflection, no neon, no busy dashboard wall. The background must remain perfectly uniform #ff00ff for clean extraction.
```

## 4. 后处理与质量问题

内置 ImageGen 返回的洋红背景视觉上接近纯色，但自动边缘采样得到的中位数是 `#f803e4` / `#fb03f9`。该颜色会被去底脚本识别为“单红色键”，从而把正常肤色的红色成分错误当作背景 spill。最终处理没有继续使用自动取色，而是严格使用 Prompt 明确指定的 `#ff00ff`：

```text
--key-color #ff00ff
--soft-matte
--transparent-threshold 24
--opaque-threshold 96
--despill
--edge-contract 1
```

随后按四列裁切，并依据 alpha bounding box 去除无效透明边距。最终验证：

- 所有角色和工位均为 RGBA PNG；
- 四角透明；
- 角色肤色与衣物颜色未被错误去色；
- 角色/工位之间没有相邻列残片；
- 工位透明画布已裁紧，运行时显示尺寸不再过小；
- 没有鹿、动物、品牌 Logo、英文标签或水印。

## 5. React 映射

- 场景与资产路径：`frontend/src/components/commerce/collaboration-space-assets.ts`
- 页面渲染：`frontend/src/components/commerce/collaboration-space-view.tsx`
- Task/Event 投影：`frontend/src/core/commerce/collaboration-scene-view-model.ts`

四个 Task 使用确定性 2×2 槽位；五至六个 Task 使用确定性 3×2 槽位。多个失败、取消或超时任务即使都映射到恢复工位，也不会因为“同工位小偏移”而互相遮挡。窄屏使用缩放后的同一任务槽位，不创建第二份状态模型。

## 6. 验证证据

- 机械浏览器截图：`docs/design/commerce/mockups/commerce-collaboration-generated-assets-v1-desktop.png`
- 截图 SHA-256：`80d0386b6377d812a7ea904ebfc87ce2d9e0eeb35912d972b7d03628e8018c8d`
- 截图使用冻结的 Mock Durable Task API，只验证 UI 机械映射和视觉布局，不作为 Agent Release Gate；
- 真实 Agent 验收仍必须使用 fresh `deepseek-v4-flash`、真实 Gateway、真实 Task/Event 和冻结公开数据。

当前机械验证覆盖：

- 空 Run 只有场景，没有角色和工位；
- 一个 Task 对应一个角色精灵和一个工位精灵；
- 四个真实 Task 在桌面 2×2 槽位中不重叠；
- `failed / cancelled / timed_out` 保持不同终态；
- 角色 Drawer 可打开；
- 390px 窄屏无页面横向溢出，四个 Task 仍保持可交互尺寸；
- 所有运行时图像完成加载且 `naturalWidth > 0`。
