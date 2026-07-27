# Commerce Agent 20260727 中文简历验收

> 日期：2026-07-27  
> 状态：完成  
> DOCX：`/Users/zhangqixiang/0_3秋招/秋招公司项目/张祺翔_AI_Agent应用开发_简历_Commerce_Agent版_20260727.docx`  
> PDF：`/Users/zhangqixiang/0_3秋招/秋招公司项目/张祺翔_AI_Agent应用开发_简历_Commerce_Agent版_20260727.pdf`

## 1. 更新范围

以 20260726 Commerce Agent 版为保留模板，只更新项目经历 P25–P29：

- 项目标题保持单行日期布局；
- Durable Parent–Subagent Harness；
- 11 个确定性 Commerce Tool 与动态 Profile / Skill；
- 默认中文 Chat 与同源 Task/Event 游戏化协作空间；
- 334 个前端单测和 5 条专项 Chromium E2E；
- fresh DeepSeek V4 四条跨场景 Gate；
- 最新 v7：17 请求、199,598 Token、retry 0、Parent Tool Error 0；
- Candidate → Holdout → Shadow → Human Promotion → Rollback 治理链；
- PostgreSQL 重启恢复和 fencing takeover。

没有写入以下未完成或不成立的结论：

- 真实持久化上传浏览器 Agent Gate 已通过；
- v7 repair-free；
- 当前 Candidate 已 Promotion；
- 外部商家 Connector 已完成；
- 公开数据证明业务 uplift。

## 2. 模板保真

参考文件：

```text
/Users/zhangqixiang/0_3秋招/秋招公司项目/张祺翔_AI_Agent应用开发_简历_Commerce_Agent版_20260726.docx
```

结构 Gate：

```text
source_sha256=3f53e6d741dae6835e77b1196b1cfddd6c7b1a79a66d17b2677bf0d9bca10fbc
final_docx_sha256=082b27ff45ca1fec1d370aef0db64d2b27ed931bf962e2fd88ae0cd6093f49b8
package_parts=18
preserve_only_parts_unchanged=17/17
paragraph_count=36
paragraphs_outside_slot_unchanged=true
edited_paragraph_properties_preserved=true
edited_run_properties_preserved=true
ZIP integrity=PASS
```

只允许 `word/document.xml` 的 P25–P29 文本变化。教育、荣誉、论文、实习、技能、自我评价、页边距、样式、编号、Footer、关系和其他包部件均保持原模板。

## 3. DOCX 视觉 Gate

按 Documents Skill 完成：

1. LibreOffice `render_docx.py` 单页渲染；
2. `render_and_diff.py` 对参考/最终 DOCX 做逐页差异；
3. macOS Quick Look 2000px 原生中文预览；
4. 第一次预览发现标题过长导致“今”换行；
5. 只缩短项目标题后重新构建、渲染和检查。

最终原生预览：

```text
.deer-flow/docx/resume-20260727/quicklook-v2/张祺翔_AI_Agent应用开发_简历_Commerce_Agent版_20260727.docx.png
```

最终结果：

- 一页 A4；
- 中文字形完整；
- 项目标题和日期均为单行；
- 三条 Commerce Bullet 无裁切、重叠或异常换页；
- 专业技能和自我评价完整保留；
- 页面底部仍有安全留白。

LibreOffice 在当前机器上仍会省略部分 CJK 字形，因此只用于分页、结构和差异 Gate；中文最终视觉以 macOS Quick Look 原生渲染为准。

## 4. PDF Gate

为了避免交付 LibreOffice 缺少 CJK 字形的 PDF，使用通过原生视觉验收的 2000px Quick Look 单页预览生成 A4 高保真投递副本，并通过 Poppler 重新渲染检查。

```text
final_pdf_sha256=591fd6c35886daf3622e12df450083572c50d26178cad8c1e6f0d489072dfadc
pages=1
page_size=A4 595.276 × 841.89 pt
encrypted=no
javascript=no
visual_render=PASS
```

该 PDF 是单页栅格高保真投递副本；DOCX 是可编辑权威版本。
