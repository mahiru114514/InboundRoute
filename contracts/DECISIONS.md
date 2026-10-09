# 契约冻结决策记录（C1–C6）

> 用法：本文档是 C1–C6 的**唯一决策台账**。每冻结一张表，把「状态」改为「已冻结」，并在 `CHANGELOG.md` 记一条。
> **重要**：标 ⚠️ 的条目是**我替你做的默认决策**——为了让契约可用，必须先选一个值。请逐条确认或推翻；推翻要改的是文件，不是这份说明。

---

## C1 时间基准

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 时区 | 一律 `Asia/Shanghai`（北京时间，UTC+8），与用户手机时区无关 | ✅ **已冻结（2026-09-25 确认）** |
| 持久化格式 | `*_at` 后缀 = UTC 秒级整数；`date` = 上海本地 `YYYY-MM-DD`；`*_local` = 同日 `HH:mm` | ✅ **已冻结（2026-09-25 确认）** |
| `timestamp` 更名 | `anchor_arrival.timestamp` → `arrival_at` | ✅ 已冻结 |
| 每日起点 | `days[].daily_start_local` 按天独立配置，默认 `09:00`；首日不早于抵达缓冲结束 | ✅ 已冻结 |
| 跨零点 | Day 1 保留并标 `arrival_only`；允许空日程日；酒店仍为 Day 1 终点 | ✅ 已冻结 |
| 夜景跨零点 | 归属开始时刻所在日 | ✅ 已冻结 |

> 冻结含义：**引擎与规则一律按北京时间计算**（星期、营业时段、亮灯窗口全部用 UTC+8）。
> 客户端本地时区只影响它自己的显示格式化，**不得用于任何规则判定**。
> 已由 `scripts/validate.py` 强制：`timezone` 必须等于常量 `Asia/Shanghai`（`const`，写错即校验失败）。
> 时区相关回归用例见 `TIME_BASELINE.md` §5（TZ-1~TZ-4）。

文件：`TIME_BASELINE.md`

---

## C2 实体字段表

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 新增实体 | `User`（字段级）、`TripVersion`（`version`+`revision_history`）、`RouteSegment`、`HolidayCalendar`（并入 `closure_rules`）、`CuratedStation`、`POICategory`（并入 `category` + `mappings.category_taxonomy`） | ⚠️ 待确认 |
| 星期编号 | **ISO 8601：1=周一 … 7=周日**（PRD 未定义 `0` 的含义，必须定死） | ✅ **已冻结（2026-09-25 确认）** |
| `closure_days` | 改为 `closure_rules[]`，支持周闭 / 特定期 / 修缮 / 节假日例外；新增 `closure_data_status` 三态 | ⚠️ 待确认 |
| 营业时间 | 字符串 → 结构化时段数组（支持午休、按星期、旺季） | ⚠️ 待确认 |
| 停留时长 | 单值 → 支持 `point` / `range` 两种 | ⚠️ 待确认 |
| `light_up` | 增加 `T_light_rule` 与带生效日期的 `windows[]`（解决跨季） | ⚠️ 待确认 |
| 预约制 | 新增 `reservation_required` + `advance_booking_days` | ⚠️ 待确认 |
| 多语言 | `names{zh-Hans,zh-Hant,en,ja,ko}` + `romanization{pinyin,pinyin_plain,ja_romaji,ko_rr}` | ⚠️ 待确认 |
| 坐标 | 每个点带 `crs`，内部主数据统一 `WGS84`，Adapter 单向转换 | ⚠️ 待确认 |
| 距离字段 | `transit_from_previous` 增加 `distance_meters` / `walking_distance_meters` / `estimated_steps` | 必须加，无争议 |
| 审计字段 | 全实体加 `created_at` / `updated_at` / `version` / `provenance` | 必须加，无争议 |

文件：`schemas/poi.schema.json`、`schemas/trip.schema.json`、`schemas/route.schema.json`、`schemas/station.schema.json`

---

## C3 规则执行规范

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 规则编号 | 以正文为准：Rule-01 闭馆 / 02 亮灯 / 03 跨度 / 04 同质化（**PRD 的流程图作废**，它只有 3 个框且编号错位） | ⚠️ 待确认 |
| 执行顺序 | ① 时序推演 → ② 硬规则（Rule-01）→ ③ 软规则并行求值 → ④ 汇总渲染 | ✅ 已冻结 |
| 软规则是否改排序 | **否（方案 A）** —— 软规则只出提示，改单只能由用户显式操作（Move to Evening） | ✅ **已冻结（2026-09-25 决策：方案 A）** |
| 迭代上限 | `max_iterations: 1`。方案 A 下引擎不自触发，无需迭代收敛；顺序变化只来自用户操作 | ✅ 已冻结 |
| 移动后仍不满足 | 移动生效 + 保留提示，文案换 `rule.lightup.still_early` + 不再提供 Move to Evening（避免无效点击） | ✅ 已冻结 |
| 「末位」定义 | 当日最后一个**未锁定**位置；末尾连续 `locked` 的点不动，新位置插在它们之前 | ✅ 已冻结 |
| Rule-01 数据缺失 | `closure_data_status=unknown` 时**软提示，禁止静默放行** | ⚠️ 默认 |
| Rule-01 确认有效期 | 改期后确认失效（`expires_on_reorder`） | ⚠️ 待确认 |
| Rule-02 判定基准 | 用**抵达时间**；并补「到得太晚」对称分支 | ⚠️ 待确认 |
| Rule-03 判定 | 双条件：直线 >25 km **且** 耗时 >60 min，且必须 `is_core_urban`；阈值按城市参数化 | ⚠️ 待确认 |
| Rule-04 分类 | 用 `category.level2`，取值受 `mappings.category_taxonomy` 约束；文案插值 | ⚠️ 待确认 |
| 提示承载 | `modal_confirm` / `toast` / `inline_bubble` / `list_banner` / `card_badge` / `pin_badge`，并给容量上限 | ⚠️ 默认 |

文件：`rules.json`

---

## C4 API 契约

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 风格 | REST + `/api/v1`；游标分页 | ⚠️ 待确认（若后端选 GraphQL 需重写本节） |
| 鉴权 | 全接口 Bearer JWT；`trip.user_id == token.sub` 否则 403 | 必须，无争议 |
| 三方 key | **客户端零 key，全部服务端代理** | 必须，上线门禁 |
| 幂等 | `Idempotency-Key` 头，24h 窗口，重放返回首次结果 | 必须，无争议 |
| 版本兼容 | `X-Contract-Version`；新增可选字段=次版本，其余=主版本；客户端必须忽略未知字段 | ⚠️ 默认 |
| 错误码 | 13 个码固定（见 `errors.json`） | ⚠️ 默认 |
| 限流 | 单用户 ≤60 次/小时，并发会话 ≤8 | ⚠️ 待确认 |
| 埋点 | 5 类事件必需；降级率 5min >10% 告警 | ⚠️ 默认 |

文件：`schemas/api.schema.json`、`errors.json`

---

## C5 Route Adapter 归一化

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 三模态结构 | 统一放 `variants[]`，客户端不为每种模式各写一套 | ⚠️ 默认 |
| 费用 | 单值 → `{min, max, currency}` 区间 + `display_currency` | ⚠️ 待确认 |
| 拥堵 | 新增 `congestion_level` 枚举 | ⚠️ 待确认（依赖三方能否提供） |
| 换乘 30% 上浮 | 只存 `transfer_overhead{applies_to, factor, counts_in_timeline}`，**不改写值**（保证幂等）；`counts_in_timeline=true` 时按 `applies_to` 计入时间轴：`walking_segment` → `duration_seconds + walking_duration_seconds*(factor-1)`，`whole_transit` → `duration_seconds*factor`，`none` → 原值 | ✅ **已冻结（C 拍板）** |
| 落客点 | 单值 → 数组 + `source` + `priority`；人工优先于三方 | ⚠️ 待确认 |
| 数据来源标注 | 每个进出站口/换乘段带 `source`（`curated` vs `api`），缺失时前端隐藏该行而非显示占位 | ⚠️ 默认 |
| 降级表达 | `data_source=degraded` + `degraded_reason` + `degraded_notice_key` + `partial` | 必须，无争议 |

文件：`schemas/route.schema.json`、`mappings.json#/crs_conversion`

---

## C6 三方能力实测

| 项 | 决策 | 状态 |
| --- | --- | --- |
| 站台库必供字段 | 进出站口编号、站台方向、线路颜色、站内换乘步行距离与扶梯提示 —— 全部标记为 `must_come_from_curated` | ⚠️ 待实测确认 |
| 三方字段映射 | 已按高德/腾讯/百度列出已知可得与未知项（`mappings.provider_field_map`） | ☐ 待实测 |
| 实测结论回填 | 实测后回来改 `provider_field_map`，并把不可得项从 3.5 承诺里删除或降级 | ☐ 未开始 |

文件：`mappings.json#/provider_field_map`、`../InboundRoute_PRD_三方能力核实清单.md`

---

## 遗留待决策项（不阻塞开工）

| # | 事项 | 现状 | 影响谁 | 建议决策时机 |
| --- | --- | --- | --- | --- |
| D-1 | `prefer_taxi`（Family/Senior）是否允许自动切换对比卡默认 Tab | 契约已加 `variants[].is_default_tab` + 排序，但**是否自动**未定 | 模块四前端 | 模块四开始前 |
| D-2 | Pacing 上限的未决语义：超上限是拦截还是警告 | 契约冻结为软警告 + 可绕过（`errors.json#PACING_EXCEEDED`） | 模块一 | 模块一联调前 |
| D-3 | 跨零点行程是否在 UI 标注「次日凌晨」 | 契约未涉及展示层 | 模块一/五前端 | UI 定稿前 |
| D-4 | 离线包是否包含 POI 详情字段（现在列为 optional） | `mappings.json#/offline_package.optional` | 模块五 | 模块五开始前 |
| D-5 | 站台库覆盖范围（一期覆盖哪些站点） | 依赖 C6 实测 | 模块四 | C6 实测后 |

---

## 冻结顺序建议（一个人的节奏）

1. **先 C1 + C2**（3 天）：它们是其它四张的地基。C1 一天，C2 两天。
2. **再 C3**（1 天）：规则表可以照着 `rules.json` 逐条对产品过。
3. **再 C4 + C5**（2 天）：接口与 Adapter 结构可以并行写，两者互相引用字段。
4. **C6 最后**（2–3 天，可与其他并行）：实测结果只影响 `mappings.json` 局部。

**每冻结一张，立刻跑一次 `python scripts/validate.py`**，把「示例数据自洽」当成冻结的前提——PRD 的示例数据本身就是矛盾的，不拦住它，契约就白做。
