# 样例实验分析——结账页社会证明

> OpenSKU 确定性 Demo 样例。本录制分析不使用模型、真实店铺账户、外部文件或网络数据源。

## 业务问题

根据购买转化率，结账页社会证明实验版本是否应该上线？

## 已注册的样例输入

| 样例文件                     | Join Key     | 用途                     |
| ---------------------------- | ------------ | ------------------------ |
| `visitors.csv`               | `visitor_id` | 合格访客总体和曝光时间   |
| `experiment_assignments.csv` | `visitor_id` | 对照组/实验组分配        |
| `orders.csv`                 | `visitor_id` | 分析窗口内的二元购买结果 |

真实 Growth Analyst 会把用户上传的 CSV/XLSX 注册为受限 DuckDB 表。应用工具只允许执行只读 `SELECT` / `WITH`，并拒绝外部文件访问、多语句、网络访问和写操作。

## Join 合同

```sql
WITH purchaser AS (
  SELECT DISTINCT visitor_id
  FROM orders
  WHERE order_status = 'completed'
)
SELECT
  a.variant,
  COUNT(*) AS assigned_visitors,
  COUNT(p.visitor_id) AS purchasers
FROM experiment_assignments AS a
JOIN visitors AS v USING (visitor_id)
LEFT JOIN purchaser AS p USING (visitor_id)
GROUP BY a.variant;
```

录制样例聚合结果：

| 版本   | 已分组访客 | 购买人数 |   转化率 |
| ------ | ---------: | -------: | -------: |
| 对照组 |      1,200 |       96 | 0.080000 |
| 实验组 |      1,180 |      124 | 0.105085 |

## 双比例 z-test

样例对二元购买结果执行双侧、合并方差的双比例 z-test。

```text
绝对提升           = 0.105085 - 0.080000 = 0.025085
相对提升           = 0.025085 / 0.080000 = 31.36%
z 统计量           = 2.1125
双侧 p-value       = 0.0346
绝对提升 95% CI    = [0.001809, 0.048361]
                   = [+0.18, +4.84] 个百分点
```

## 样本比例失配（SRM）

预设分流为 50/50，实际观察到 1,200 名对照组访客和 1,180 名实验组访客。

```text
卡方统计量    = 0.1681
SRM p-value   = 0.6818
结果          = 通过
```

通过这项检查并不能证明实验完全无偏；它只能说明总体分流没有出现统计上异常的偏离。

## 决策合同

- **SHIP：**主指标通过，置信区间在期望方向上排除零，SRM 通过，并且保护指标可接受。
- **EXTEND：**方向可能有利，但不确定性、统计功效或数据质量仍不足。
- **STOP：**效果有害、明确未通过决策阈值，或实验数据无效。

样例结果：**上线并持续监控**。
