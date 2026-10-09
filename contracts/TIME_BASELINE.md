# 时间基准规范（C1）

> 契约编号：C1　状态：**草案待确认**　冻结后任何模块不得自定义时间格式。
> 依据：PRD 示例 `anchor_arrival.timestamp = 1789728000` 与 `days[0].date = "2026-10-12"` 实测相差 23 天（前者为 2026-09-18 18:40 UTC+8，星期五；后者为星期一），且同一实体并存「Unix 秒级整数 / ISO 日期串 / 裸时刻串」三种类型、全篇无时区定义。Rule-01 的「周一闭馆」判定完全依赖星期换算，**时区偏移一天即导致误判**。

## 1. 三条不可协商的规则

| # | 规则 | 理由 |
| --- | --- | --- |
| T-1 | **所有时刻一律按 `Asia/Shanghai`（北京时间，UTC+8）解释与计算**，与用户手机时区无关 ✅ 已冻结 | 行程语义是「当地几点」，不是「用户家乡几点」；海外用户在伦敦规划上海行程，星期必须按上海算。客户端本地时区只影响它自己的显示格式化，**不得用于任何规则判定** |
| T-2 | **持久化用 UTC 秒级整数**（`*_at` 后缀），**展示与规则计算用上海本地时** | 存储无歧义、可比较；规则需要「星期/小时」这类本地语义 |
| T-3 | **禁止裸时刻参与跨天计算**；`HH:mm` 仅用于同日展示 | PRD 的 `target_arrival_time: "19:30"` 无法表达跨零点 |

## 2. 字段命名约定（据此判断一个字段该怎么存）

| 后缀 / 名称 | 类型 | 语义 | 示例 |
| --- | --- | --- | --- |
| `*_at` | integer（UTC 秒） | 绝对时间点 | `arrival_at: 1789733400` |
| `date` | string `YYYY-MM-DD` | 上海本地日期（无时刻） | `"2026-10-12"` |
| `*_local` | string `HH:mm` | 上海本地同日时刻，**仅限展示/同日比较** | `"19:30"` |
| `*_minutes` | integer | 时长（分钟），非时间点 | `planned_dwell_minutes: 90` |
| `*_seconds` | integer | 时长（秒） | `duration_seconds: 1800` |
| `daily_start_local` | string `HH:mm` | 每日独立出发时刻；抵达日受缓冲结束时间约束 | `"09:00"` |

> 命名即契约：看到 `_at` 就当 UTC 秒处理，看到 `_local` 就当同日时刻处理，不允许混用。

## 3. 派生规则（引擎按此推导，客户端不得自行计算）

```
Day 1     ：activity_start_at = anchor_arrival.at + border_buffer_minutes * 60
             day_start_at = max(activity_start_at, date(Day_1) + daily_start_local)
Day 2..N  ：day_start_at      = date(Day_n) + daily_start_local +08:00
第 i 个停靠点：arrival_at  = 上一停靠点 departure_at + transit_from_previous.duration_seconds
             departure_at = arrival_at + planned_dwell_minutes * 60
当日收尾  ：若存在 departure anchor，则追加 hotel → departure 区段（含枢纽缓冲）
```

- `arrival_at`（引擎推算）与 `user_preferred_arrival`（用户意愿）**必须并存**，字段名不同、语义不同，不得互相覆盖。
- 所有派生字段由服务端写入，客户端只读。

## 4. 三个已确认的边界裁决（本次替产品拍板，标注待确认）

| 场景 | 裁决 | 待确认点 |
| --- | --- | --- |
| 抵达时刻跨零点（如 23:30 抵达 → `T_start` 落到次日 01:00） | Day 1 保留但标记 `day_status = "arrival_only"`；允许 Day 1 为空日程；酒店仍为 Day 1 终点 | 是否允许空日程日保存 |
| 夜景行程结束超过 24:00 | 归属**当日**（`arrival_at` 可跨零点，日期归属按开始时刻所在日） | 是否需要在 UI 上标注「次日凌晨」 |
| 跨季行程（9–10 月） | 亮灯规则按 `light_up_schedule` 的季节生效区间判定（见 `schemas/poi.schema.json` 的 `light_up_schedule[].from/to`），无匹配区间则**不触发** Rule-02 | 季节区间由产品/运营维护 |

## 5. 时区相关测试用例（必须进 `examples/`）

| # | 用例 | 期望 |
| --- | --- | --- |
| TZ-1 | 用户在伦敦（UTC+1）规划 2026-10-12 的行程，问 Rule-01 是否命中周一闭馆 | 命中（按上海时区判定为周一） |
| TZ-2 | `arrival_at` 为 23:30 上海本地 | Day 1 标记 `arrival_only`，Day 2 起点取 `daily_start_local` |
| TZ-3 | 同日 `arrival_at` 跨零点至次日 00:30 | 归当日；`date` 不变 |
| TZ-4 | `target_arrival_time` 型裸时刻出现在跨天区段 | 校验器报错（禁止） |

## 6. 校验器强制项（`scripts/validate.py` 实现）

1. 所有 `*_at` 必须是整数且落在合理区间（2026-01-01 ~ 2030-01-01）。
2. 所有 `date` 必须匹配 `^\d{4}-\d{2}-\d{2}$`。
3. 所有 `*_local` 必须匹配 `^([01]\d|2[0-3]):[0-5]\d$`。
4. **示例数据自洽性**：`anchor_arrival.arrival_at` 换算后的日期必须等于 `days[0].date`（PRD 示例正是在此处矛盾，必须拦住）。
5. Day 2..N 缺失 `daily_start_local` 时报错。


2026-10-04 每日配置扩展：days[].daily_start_local 可在每日安排中独立修改。Day 1 起点=max(date + daily_start_local, anchor_arrival.activity_start_at)，可推迟出发但不可提前越过入境缓冲。Day 2..N 继续使用该日自身时刻。修改初始设定不覆盖每日出发时刻。
