# Rule 决策表测试用例集（B 的开发与测试依据）

> 对应契约：`rules.json`（C3）。本文把 `rules.json#/ac_matrix` 的骨架扩成**可执行的 GWT 用例**。
> 执行模型已冻结为**方案 A**：软规则只出提示，改单必须由用户显式操作；`max_iterations: 1`。
> 时区一律 `Asia/Shanghai`（北京时间）；星期编号 ISO（1=周一 … 7=周日）。
>
> **用法**：B 写引擎时，每条用例都要能落成一个测试；测试命名直接用 `TC-xx` 编号，方便和产品/测试对齐。
> 标注 `[需 mock]` 的用例需要桩数据（三方 API 或规则库字段），其余可在纯函数层验证。

---

## 0. 覆盖率检查表

| 规则 | 用例数 | 覆盖类型 |
| --- | --- | --- |
| Rule-01 闭馆 | 9 | 命中/不命中、节假日例外、临时闭馆、数据缺失三态、确认与改期失效、开放式街区 |
| Rule-02 亮灯 | 8 | 到太早/到太晚、跨季无窗口、移动后仍不满足、locked 点、改期失效、软规则不改单 |
| Rule-03 跨度 | 6 | 双条件四种组合、核心城区缺失、城市参数化 |
| Rule-04 同质化 | 5 | 阈值边界、多档计数、空分类、跨页签 |
| 跨规则与执行模型 | 7 | 顺序、并集渲染、硬阻断短路、幂等、性能预算、离线态 |

共 **35 条**。每条格式：`前置（Given）→ 触发（When）→ 期望（Then）`。

---

## 1. Rule-01 闭馆日强冲突（硬约束）

规则要点：命中 `closure_rules` 且 `is_enclosed_attraction = true` → 弹二次确认；确认后打红标并落库。
例外优先级：`holiday_exception_open` > `holiday_exception_closed` > `special_period` / `maintenance` > `weekly`。

| ID | 前置 | 触发 | 期望 |
| --- | --- | --- | --- |
| TC-01-01 | POI 有 `weekly=1`（周一）且 `is_enclosed_attraction=true`，`closure_data_status=verified` | 加入 2026-10-12（周一） | 返回 `modal_confirm`，`message_key=rule.closure.confirm`，`outcome=pending`；**不落库**，等用户决策 |
| TC-01-02 | 同 TC-01-01 | 用户选 `proceed_anyway` | `notice.outcome=confirmed_proceed`、`confirmed_at` 写入；`pin_state=added_conflict_warned`；卡片红标；`revision_history` 增加 `confirm_conflict` |
| TC-01-03 | 同 TC-01-01 | 用户选取消 | 该点不入行程；`ordered_stops` 与操作前完全一致 |
| TC-01-04 | `weekly=1` + `holiday_exception_open` 含 `2026-10-05`，且当日为周一 | 加入 2026-10-05 | **不触发**（节假日照常开放优先） |
| TC-01-05 | `special_period` 覆盖 `2026-02-15~2026-02-21`（春节） | 加入 2026-02-18 | 触发；原因文案使用 `reason_zh/reason_en`，而非硬编码 Monday |
| TC-01-06 | `maintenance` 覆盖 `2026-11-01~2026-11-03` | 加入 2026-11-02 | 触发（修缮闭馆同样阻断） |
| TC-01-07 | `closure_data_status=unknown`，`closure_rules=[]` | 加入任意日期 | **不弹硬确认，但必须出软提示** `rule.closure.data_unknown`（`must_notify`，禁止静默放行） |
| TC-01-08 | `closure_data_status=unverified` | 加入任意日期 | 出软提示 `rule.closure.data_unverified`，措辞弱于 unknown，不阻断 |
| TC-01-09 | `weekly=1` 命中，但 `is_enclosed_attraction=false`（开放式街区） | 加入周一 | **不触发硬确认**（无检票边界）；如产品后续要求提示，另立软规则 |
| TC-01-10 | 已确认 `proceed_anyway` 的点（`outcome=confirmed_proceed`） | 用户把该点拖到周二 | 原确认按 `expires_on_reorder=true` **失效**；对周二重跑全部规则；若周二不在闭馆日则红标清除 |
| TC-01-11 | POI 未采集 `is_enclosed_attraction`（字段缺失） | 加入周一 | 落到「数据缺失」分支：出软提示，不阻断（避免因缺字段误拦） |

> 注：TC-01-11 的语义与 TC-01-07 一致——**宁可不拦，不可静默放行**。

---

## 2. Rule-02 亮灯时序（软约束）

规则要点：`light_up.required=true` 且抵达时间早于 `T_light` → 提示 + `[Move to Evening]`。
`T_light` 由 `light_up.T_light_rule` 计算（默认 `window_start_minus_30`）；窗口按 `windows[].date_from/to` 匹配，**无匹配窗口则不触发**。

| ID | 前置 | 触发 | 期望 |
| --- | --- | --- | --- |
| TC-02-01 | 夏季窗口 `19:00-23:00`（`T_light=18:30`），预计 17:40 抵达 | 求值 | 出 `rule.lightup.too_early`，`message_args.T_light=18:30`，actions 含 `move_to_evening` |
| TC-02-02 | 同上，预计 18:30 抵达 | 求值 | **不触发**（边界：`arrival >= T_light`） |
| TC-02-03 | 同上，预计 23:30 抵达（已过 `close=23:00`） | 求值 | 出 `rule.lightup.too_late`（PRD 缺失的对称分支），actions 含 `change_day` |
| TC-02-04 | 行程日期 2026-10-12，`windows` 只有 `05-01~09-30` | 求值 | **不触发**（无匹配窗口，不得取就近季节兜底） |
| TC-02-05 | `light_up.required=true` 但 `windows=[]` | 求值 | **不触发**（数据缺失即跳过，不猜） |
| TC-02-06 | 当日 4 个点，外滩预计 17:40 抵达，`T_light=18:30` | **仅执行求值，用户不点任何按钮** | `ordered_stops` 顺序与求值前**逐项相等**；仅新增 notice（方案 A 的核心断言） |
| TC-02-07 | 当日末位连续 2 个点 `locked=true`，外滩未锁定 | 用户点 `move_to_evening` | 外滩插到末尾连续 locked 点**之前**；两个 locked 点相对顺序不变；`revision_history` 增加 `move_to_evening` |
| TC-02-08 | 当日仅 2 个点；移到最晚位置后抵达 17:45，仍 < `T_light=18:30` | 用户点 `move_to_evening` | 移动生效；提示保留但文案换 `rule.lightup.still_early`（含 `arrival_local`）；**不再提供** `move_to_evening`（避免无效点击） |
| TC-02-09 | 外滩已有 `outcome=pending` 的 too_early 提示 | 用户把外滩拖到另一天 | 原提示按 `expires_on_reorder` 失效；对新日期重跑全部规则 |
| TC-02-10 | `T_light_rule=sunset` | 求值 | `T_light` 取当日日落时刻（需日落数据源；缺失时按 skip 处理，不得用默认值蒙） |

---

## 3. Rule-03 地理跨度（软约束）

规则要点（**双条件**，PRD 只有直线距离单条件）：相邻两点直线距离 > `city_config.spread_straight_km` **且** 预估耗时 > `spread_duration_minutes` **且** 两点属核心城区。
上海默认阈值：直线 25 km、耗时 60 min。

| ID | 前置 | 触发 | 期望 |
| --- | --- | --- | --- |
| TC-03-01 | 外滩 → 迪士尼：直线 28.5 km，轨道 70 min，两端 `is_core_urban=true` | 加入当日 | 出 `rule.spread.long_transit`，`message_args={distance_km:28.5, duration_minutes:70}`，挂在该边上 |
| TC-03-02 | 两点直线 30 km，但高速直达 25 min | 求值 | **不触发**（避免误报——这正是双条件的意义） |
| TC-03-03 | 黄浦江两岸两点：直线 1.0 km，但因绕行/换乘耗时 35 min | 求值 | **不触发**（直线近、耗时也不超阈值） |
| TC-03-04 | 直线 30 km、耗时 70 min，但一端 `is_core_urban=false`（郊区） | 求值 | **不触发**（PRD 的「高密度主城区」条件） |
| TC-03-05 | 任一 POI 缺 `city.is_core_urban` | 求值 | **跳过**（缺数据不猜，`skipped_rules` 中记录 `missing_data`） |
| TC-03-06 | 城市为上海，阈值取 25/60 | 求值 | 阈值从 `city_config.shanghai` 读取；换成其他城市时阈值随之变化（禁止硬编码 25） |

---

## 4. Rule-04 同质化审美疲劳（软约束）

规则要点：单日内相同 `category.level2` 计数 ≥ 3 → 底部 Banner，文案插值。

| ID | 前置 | 触发 | 期望 |
| --- | --- | --- | --- |
| TC-04-01 | 当日已有 2 个 `classical_garden` | 加入第 3 个同类 | 出 `rule.homogeneous.banner`，`message_args.count=3` |
| TC-04-02 | 前一条已触发 | 再加入第 4、5 个同类 | 仍只显示 **1 条** Banner，`count` 更新为 4、5（**不得写死 3**） |
| TC-04-03 | 当日 3 个点分属 3 个不同 `level2` | 求值 | **不触发** |
| TC-04-04 | POI 的 `level2` 为空或不在 `mappings.category_taxonomy` 内 | 求值 | **跳过该点计数**，不报错（字典外数据不得造成引擎异常） |
| TC-04-05 | 3 个同类分布在两天（各 2 个 / 1 个） | 求值 | **不触发**（作用域是 `same_day`） |

---

## 5. 跨规则与执行模型

| ID | 前置 | 触发 | 期望 |
| --- | --- | --- | --- |
| TC-X-01 | 一次加入同时命中 Rule-01（硬）与 Rule-03（软） | 加入 | 先出硬确认；用户确认后，软提示一并渲染；**渲染顺序** hard > soft_warning > soft_hint |
| TC-X-02 | 同一停靠点同时命中 Rule-02 与 Rule-04 | 求值 | 两条提示**并存**（`inline_bubble` 与 `list_banner` 承载位不同，不互相覆盖） |
| TC-X-03 | 同日命中 4 条软提示 | 求值 | 按 `channel_capacity` 渲染：toast ≤3、inline_bubble ≤3、list_banner ≤2；溢出部分合并为「还有 N 条建议」入口 |
| TC-X-04 | 硬确认未被用户处理（`outcome=pending`） | 用户尝试提交行程 | 返回 `RULE_HARD_CONFLICT` + 待确认列表 + `conflict_confirm_token`（见 `errors.json`） |
| TC-X-05 | 同一请求重复提交（带同一 `Idempotency-Key`） | 重放 | 返回首次结果；**不重复调用三方、不重复写 `revision_history`** |
| TC-X-06 | 一次拖拽改变了当日 3 个区段 | 拖拽 | 只重算受影响的区段；三方调用 ≤4 次且并发执行（`mappings.cache_keys.call_budget`） |
| TC-X-07 | 断网（`data_source=degraded`，`degraded_reason=offline`） | 求值 | Rule-01 仍可用本地规则库求值；Rule-02/03 因缺耗时数据 → 进 `skipped_rules`（`reason=missing_data`），**不得静默当作通过** |

---

## 6. 判定顺序（B 实现时的伪代码骨架）

```
def evaluate(trip, day_index, trigger):
    assert trigger in ORDER_MUTATION_WHITELIST or trigger == "load_trip"

    day = trip.days[day_index]
    timeline = build_timeline(day, trip.anchor_arrival, trip.anchor_hotel)   # ① 时序推演
    notices, skipped = [], []

    hard = evaluate_rule_01(day, timeline, trip.poi_lookup)                  # ② 硬规则
    notices += hard
    if any(n.severity == "hard" and n.outcome == "pending" for n in hard):
        # 不短路其余求值，但提交时必须被 RULE_HARD_CONFLICT 拦住（TC-X-04）
        pass

    for rule in (rule_02, rule_03, rule_04):                                 # ③ 软规则并行，互不影响
        result = rule(day, timeline, trip)                                   #    绝不修改 day.ordered_stops
        notices += result.notices
        skipped += result.skipped

    notices.sort(key=lambda n: SEVERITY_ORDER[n.severity])                   # ④ 汇总渲染
    return notices, skipped

# 唯一的改单入口（全部由用户触发）
def move_to_evening(trip, day_index, poi_id):
    day = trip.days[day_index]
    position = last_unlocked_position(day)     # 末尾连续 locked 之前
    apply_move(day, poi_id, position)
    trip.revision_history.append({"operation": "move_to_evening", "target": poi_id})
    return evaluate(trip, day_index, "move_to_evening")
```

**两条铁律**（评审与 code review 的检查点）：
1. `evaluate()` 内**不允许出现对 `ordered_stops` 的任何写操作**（方案 A 的核心）。建议用不可变结构或快照断言测试来强制。
2. 无论哪条规则，**缺数据一律进 `skipped_rules` 并在响应里返回**，不允许静默返回"通过"。

---

## 7. 需要 mock 的数据清单（B 开始写测试前先准备）

| 桩数据 | 用途 | 最少需要 |
| --- | --- | --- |
| POI 规则库 | Rule-01/02/04 | 1 个周闭馆 POI（内/外各一）、1 个含节假日例外的、1 个亮灯 POI、2 个同类 `level2` POI |
| 两地距离与耗时 | Rule-03 | 3 组：远且慢（触发）、远但快（不触发）、近但慢（不触发） |
| 三方路线结果 | 时序推演 | 2 段即可，其中 1 段带换乘步行 320 m（触发 30% 上浮） |
| 站台库 | 进站口展示 | 1 个站，含 2 个出入口与 1 条站内换乘 |
| 时钟 | 时区用例 | 冻结上海时间；跨零点用例单独构造 |

---

## 8. 与其它契约的对应关系

| 本文内容 | 契约文件 |
| --- | --- |
| 规则触发与响应 | `rules.json#/rules` |
| 执行顺序与方案 A | `rules.json#/execution_model` |
| 文案键 | `mappings.json#/notice_templates`（新增 `rule.lightup.still_early`） |
| 硬冲突提交拦截 | `errors.json#RULE_HARD_CONFLICT` |
| 调用预算与并发 | `mappings.json#/cache_keys.call_budget` |
| 时间与时区 | `TIME_BASELINE.md` |
| 字段与类型 | `generated/domain.ts`（前端）、`generated/README.md`（字段表） |
