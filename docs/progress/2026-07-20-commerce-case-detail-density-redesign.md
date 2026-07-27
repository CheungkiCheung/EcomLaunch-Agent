# Commerce Case Detail 信息密度重设计进度

日期：2026-07-20

## 完成内容

- 对比现有 Commerce Master Shell、用户提供的 Codex Desktop 截图和 DeerFlow 真实布局代码；
- 确认当前问题是默认同时可见层级偏多，而不是配色或基础视觉语言错误；
- 新增全局信息密度与渐进披露约束；
- 将 Case Detail v1 标记为历史密集版本，不进入 React；
- 使用内置 Image Generation 生成 Case Detail v2 三个状态：
  - 桌面默认运营视图；
  - 桌面证据检查面板状态；
  - 移动默认运营视图；
- 三张视觉稿均已人工检查中文、层级、因果限制、行动状态和移动固定区域。

## 关键决定

- 运营默认视图只回答“发生了什么、当前判断、证据边界、下一步”；
- 工程信息进入“运行”或对象级详情；
- 右侧检查面板默认关闭；
- 左侧一级入口收敛为四个；
- Runtime Strip 不再永久显示；
- Composer 空闲时为单行；
- 移动端只有一个固定底部层。

## 产物

```text
docs/design/commerce/information-density-guidelines-v1.md
docs/design/commerce/case-detail-visual-v2.md
docs/design/commerce/mockups/case-detail-visual-v2-default.png
docs/design/commerce/mockups/case-detail-visual-v2-evidence-inspector.png
docs/design/commerce/mockups/case-detail-visual-v2-mobile-default.png
```

## 验证

```text
case-detail-visual-v2-default.png
1586 × 992
SHA-256 d08e5df40beafc01f29abfd24a31cd15d1261444925c9b05986846f57ede993b

case-detail-visual-v2-evidence-inspector.png
1586 × 992
SHA-256 dbfda33690d7a4d6c3bfefc51e8b0f538950b70a6c0e05e7edd7f61ebae60e91

case-detail-visual-v2-mobile-default.png
852 × 1846
SHA-256 2ed532f90c56c24599e0a2db3f8224ac10c5fa8650a335a64e96a2365bf76923
```

本文件记录视觉重设计阶段。后续 React、确定性 API、真实 Olist 数据联调和浏览器 QA 已在 `2026-07-20-commerce-case-detail-react-v2.md` 完成并留证。

## 门禁结果

用户已确认 Case Detail v2；React TDD、真实浏览器交互、桌面/移动截图和真数据合同验收均已通过。下一视觉门禁为 Data Inbox。
