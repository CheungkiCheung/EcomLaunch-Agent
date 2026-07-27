# Commerce Agent 中文 DOCX 简历

> 日期：2026-07-26  
> 状态：完成  
> 输出：`/Users/zhangqixiang/0_3秋招/秋招公司项目/张祺翔_AI_Agent应用开发_简历_Commerce_Agent版_20260726.docx`

## Outcome

在不覆盖原简历的前提下，将原“竞品分析 Agent”项目槽位局部替换为当前 Commerce Agent 动态主线：

- Durable Parent–Subagent Harness；
- Dynamic Commerce Tool / Skill；
- fresh DeepSeek V4 Gold Gate；
- Control / Candidate、Regression、Holdout、Shadow、Human Review、Rollback；
- PostgreSQL 重启恢复、fencing takeover 与可逆内部 Action。

教育、奖项、论文、实习、技能和自我评价保持原内容与结构。

## Template fidelity

参考文件：

```text
/Users/zhangqixiang/0_3秋招/秋招公司项目/张祺翔_AI_Agent应用开发_简历_正式版.docx
```

源文件 SHA-256 在构建前后均为：

```text
771990f0c31d604335fdb97837f090f3d5e962861f73cb3232eadafe4aa25257
```

最终文件 SHA-256：

```text
3f53e6d741dae6835e77b1196b1cfddd6c7b1a79a66d17b2677bf0d9bca10fbc
```

结构验证：

```text
package_parts_preserved=17/17
paragraphs_preserved_outside_slot=31/31
edited_paragraph_properties_preserved=5/5
paragraph_count=36
project_text_ok=true
ZIP integrity=PASS
```

只允许 `word/document.xml` 的 P24–P28 文本发生变化。非正文包部件、项目槽位外段落、项目段落属性、页面尺寸、页边距、样式、编号、Footer 和关系均保持原模板。

## Visual QA

Documents skill 的 LibreOffice headless 路径可以确认单页，但本机 LibreOffice 对独立中文字体探针同样省略 CJK 字形，因此不能作为中文显示的最终权威。

补充使用 macOS Quick Look 原生文档引擎生成 2000 px 单页预览，并与原模板逐页对照。最终结果：

- 一页 A4；
- 中文字形完整；
- 项目标题、日期和三条 Bullet 无裁切、重叠或异常换页；
- 专业技能和自我评价仍完整位于第一页；
- 页面结构和视觉节奏保持原模板风格。

Pages 原生应用核验曾尝试通过 Computer Use 启动，但当时 Mac 处于锁屏状态，未绕过锁屏。Quick Look 已提供无需修改外部状态的本地原生渲染证据。

## Known limitations

- 这份简历只更新了项目经历，没有替用户最终决定所有求职表述；最终投递前仍需结合目标 JD 做一轮人工取舍。
- LibreOffice headless 的 CJK PDF 输出在当前机器上不可作为 Word/Pages 的显示代理；DOCX 本身已由 Quick Look 正确渲染。
- 没有把尚未完成的 Chat-first React 页面、浏览器 Agent Gate、外部商家 Connector 或 Shadow Candidate Promotion 写成已完成能力。
