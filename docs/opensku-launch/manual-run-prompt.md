# OpenSKU Launch Team Complete-Pack Test Prompt

请为下面的产品生成一个完整的 Launch Validation Pack。先读取并遵循
`ecom-launch` Skill；根据需要调用最少数量的专业子智能体，不要为了展示
多智能体而重复研究。最多同时运行两个互相独立的子任务。

可用专业角色：

- `market-voc-researcher`：公开竞品、价格、评论和用户声音
- `offer-architect`：人群切口、价值主张、价格假设和验证实验
- `asset-studio`：商品页、短视频、小红书/抖音和直播资产

## 产品信息

- 产品：面向办公室通勤和轻户外场景的便携防漏咖啡杯
- 品类：coffee tumbler / travel mug / portable insulated cup
- 平台：淘宝、小红书、抖音
- 人群：通勤携带咖啡的上班族，以及在意防漏、清洁、异味、保温和便携性的轻户外用户
- 价格：人民币 99～199 元
- 已确认限制：不带电子元件；其他材质、容量、保温时长、检测、认证和售后政策均待确认
- 私有数据：没有商家后台数据

## 证据要求

仅使用可公开访问的网页和明确提供的材料，不绕过登录墙、验证码、反爬机制或私有后台。

区分并标注：

- `observed_public`
- `uploaded_real`
- `estimated`
- `assumption`
- `unavailable`

不得虚构 GMV、CTR、CVR、ROI、广告消耗、销量、退款率、复购率、市场份额、产品规格、检测结果、认证、用户证言或售后政策。缺失内容使用待确认占位，并给出低成本验证方式。

## 输出

将有价值的最终文件写入 `/mnt/user-data/outputs` 并调用 `present_files`：

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

`evidence-ledger.json` 必须是可解析的 JSON 数组；CSV 必须能被标准 CSV 解析器读取。最终回复先给出上市方向、主要风险和下一步，再展示文件，不要把所有文件内容重复粘贴到聊天中。最终回复必须明确说明“未经过独立 Evidence Checker 审计”，不得声称链接内容已经被独立核验。
