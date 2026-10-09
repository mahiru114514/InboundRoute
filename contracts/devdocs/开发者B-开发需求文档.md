# 开发者 B · 开发需求文档 —— 时序与规则

> **主责模块**：模块三（多日行程调度与冲突引擎）= **两个引擎**：Trip & Schedule Engine（时序推演）+ POI & Rules Engine（Rule-01~04）
> **你交付的是宿主模块**：`rules_engine`（依赖 `trip_engine`）
> **附带**：行程版本与冲突确认落库
> **不负责**：路线数据采集（C）、面板渲染（A）
> **契约版本**：`contracts/` 0.3.0-draft（C3 已冻结为**方案 A：软规则不自动改单**；**C7 模块运行时**）

---

## 0. 你的代码怎么跑起来（先读这节）

宿主是「模块工作台」：每个模块是**独立进程**，模块间通过**本地 HTTP** 通信（契约见 `contracts/MODULE_RUNTIME.md`）。

```
modules/rules_engine/               ← 你的模块
├── manifest.json                   dependencies: ["trip_engine"]
└── plugin.py                       run(context) → 起 HTTP 服务
```

**你的模块纪律**：

| 规则 | 说明 |
| --- | --- |
| 依赖 `trip_engine` | manifest 里声明；宿主保证 `trip_engine` 先启动。启动时读 `<root>/data/_registry/trip_engine.json` 拿它的 `base_url` 与 `token`，用它读写行程 |
| 依赖未就绪要等 | 轮询 `trip_engine` 的 `/health`，最长 30s（200ms→1s 退避）；超时则启动失败并写明确日志，不要静默降级 |
| 依赖中途退出 | 你的 `/health` 把 `status` 置 `degraded`、`degraded_reason=upstream_down`；业务端点返回 503 + `UPSTREAM_*`；**不要自己重启依赖**（宿主管生命周期） |
| 只被调用，不反向调 | `trip_engine` 不得调你，你也不得调 `web_workbench` |
| 端口与令牌 | 自己占端口（`config.port` 或 `0` 自动分配），启动成功后写 `data/_registry/rules_engine.json`，格式严格照 `MODULE_RUNTIME.md` §2 |
| 必须实现 `GET /health` | 免令牌；返回 `{module_id, status, contract_version, ready, started_at, degraded, degraded_reason}` |
| 除 `/health` 外都要 `X-Module-Token` | 令牌启动时随机生成并登记，**不要写进 `context.config`**（配置会被页面展示） |

**你要实现的端点**：`POST /trips/{id}/rules:evaluate`、`POST /trips/{id}/conflicts/{notice_id}/confirm`（见 `MODULE_RUNTIME.md` §3.2）。
**你要消费的端点**：`trip_engine` 的 `GET /trips/{id}`（读行程）与 `POST /trips/{id}/days/{d}/stops`、`PATCH /trips/{id}`（写回时间轴与 notices）。

---

## 1. 你手上的契约文件（这是你最主要的工作依据）

| 文件 | 你要用它做什么 |
| --- | --- |
| `contracts/MODULE_RUNTIME.md` | **模块怎么跑、端口与注册表、令牌、依赖等待**（先读这个） |
| `contracts/rules.json` | **规则唯一来源**：4 条规则的触发、硬/软、执行顺序、缺失策略、AC 矩阵 |
| `contracts/RULE_TEST_CASES.md` | **35 条 GWT 用例**，直接当测试清单写，命名用 `TC-xx` 编号 |
| `contracts/TIME_BASELINE.md` | 时区（北京时间）、时间类型、派生公式、跨零点裁决、TZ-1~TZ-4 用例 |
| `contracts/schemas/trip.schema.json` | `days[].daily_start_local`、`arrival_at`/`departure_at`、`$defs/notice`、`revision_history` |
| `contracts/schemas/route.schema.json` | 区段耗时来源、`transfer_overhead.counts_in_timeline` |
| `contracts/mappings.json` | `notice_templates`（文案键→文案）、`category_taxonomy`（Rule-04 计数依赖）、`weighting`（1.3 系数只作用于步行段） |
| `contracts/DECISIONS.md` | C3 的已冻结项（方案 A、末位定义、移动后仍不满足） |

参考样例：`contracts/examples/trip_shanghai_2d.json`（**可直接当输入夹具**，含跨零点抵达、Day2 时间轴、换乘 30% 上浮、已确认的闭馆冲突）。

---

## 2. 四条不可违反的约定（方案 A 的护栏）

| # | 约定 | 为什么 |
| --- | --- | --- |
| B-铁律-1 | **`evaluate()` 内绝对不允许对 `ordered_stops` 写操作**。软规则只产出 `notices`，改单只能由用户显式调 `move_to_evening` | 这是 C3 方案 A 的核心；一旦引擎能改单，就会形成「排序→时间→规则→排序」自触发回路 |
| B-铁律-2 | **缺数据一律进 `skipped_rules[]` 并返回**，绝不静默返回「通过」 | PRD 的 `closure_days: []` 无法区分「不闭馆」和「没采集」，静默放行会让「周一闭馆」这个核心卖点变成误报来源 |
| B-铁律-3 | **文案只产出 `message_key` + `message_args`**，绝不在引擎里拼中文字符串 | 多语言与文案迭代都要求文案与逻辑解耦 |
| B-铁律-4 | **所有星期/时段判定按 `Asia/Shanghai`**，绝不用服务器本地时区或用户时区 | 时区偏移一天会让「周一闭馆」整体错位，且极难测出 |

**建议的强制手段**：为 `evaluate()` 写一条「求值前后对 `ordered_stops` 做深比较快照」的测试。这是方案 A 唯一的技术护栏，靠 code review 一定会漏。

---

## 3. 你的七个交付模块（按依赖顺序）

### B1 Rule-01 闭馆判定（**今天就开工，与时间轴无关**）

- 触发：`Date(Day_n)` 命中 `closure_rules` **且** `is_enclosed_attraction = true`
- **例外优先级**（`rules.json#/rules[rule_01_closure]/exception_precedence`）：
  `holiday_exception_open`（节假日照常开放）> `holiday_exception_closed` > `special_period`/`maintenance` > `weekly`
- 响应：`modal_confirm` + `Proceed anyway`；确认后 `pin_state=added_conflict_warned`、`outcome=confirmed_proceed`、写 `revision_history`
- **缺失数据三态**：`closure_data_status` 为 `unknown` → 软提示但**不得静默放行**；`unverified` → 较弱提示；`verified` → 正常求值
- 落库：`notice.outcome`、`confirmed_at`、`expires_on_reorder`（改期后确认失效）
- 验收：**TC-01-01 ~ TC-01-11 全绿**

### B2 规则执行框架

按 `rules.json#/execution_model` 实现四步，**顺序不可调换**：

```
① 时序推演  → ② 硬规则(Rule-01) → ③ 软规则并行求值(02/03/04) → ④ 汇总渲染
```

- ③ 的软规则**并行求值、互不影响、都不改排序**
- ④ 按 `severity_order`（hard > soft_warning > soft_hint）排序后一次性渲染，按 `channel_capacity` 分配承载位
- `max_iterations: 1`——方案 A 下引擎不自触发，无需迭代
- 验收：TC-X-01 ~ TC-X-07（含 `evaluate()` 不改单的断言、幂等重放、调用预算）

### B3 时序推演（**需要 A 的行程结构；可先用 `trip_shanghai_2d.json` 开发**）

```
Day 1     ：activity_start_at = anchor_arrival.arrival_at + 90min
Day 2..N  ：day_start_at = date(Day_n) + daily_start_local
第 i 个点  ：arrival_at  = 上一站 departure_at + transit_from_previous.duration_seconds
            departure_at = arrival_at + planned_dwell_minutes × 60
```

- 所有 `*_at` 存 UTC 秒，判定用北京时间（`TIME_BASELINE.md` T-1/T-2）
- **`transfer_overhead.counts_in_timeline = true` 时，换乘上浮必须计入耗时**，但用「原值 + 系数」计算，**不改写 `duration_seconds`**（保证多次重算幂等）
- `locked: true` 的点**位置不可被移动**；「末位」= 当日最后一个未锁定位置（末尾连续 locked 的点插在其前）
- 跨零点：`arrival_at` 可跨零点，日期归属按**开始时刻所在日**（TZ-3）
- 验收：时间轴自洽（`departure - arrival == dwell × 60`）、TZ-2 跨零点、区段衔接

### B4 Rule-02 亮灯（含方案 A 特有的两个分支）

- `T_light` 由 `light_up.T_light_rule` 计算（默认 `window_start_minus_30`）；窗口按 `windows[].date_from/to` 匹配，**无匹配窗口则不触发**（不得取就近季节兜底）
- 两个分支：`too_early`（提示 + `Move to Evening`）、`too_late`（**PRD 缺失的对称分支**，建议改天）
- `move_to_evening` 三个必须实现的细节：
  1. `trigger: "user"`——只能用户触发
  2. 插入位置 = 末尾连续 `locked` 点**之前**
  3. **`on_still_failing`**：移动后仍 < `T_light` → 移动生效 + 保留提示 + 文案换 `rule.lightup.still_early` + **不再提供该动作**（避免无效点击）
- 验收：**TC-02-01 ~ TC-02-10**

### B5 Rule-03 地理跨度（**双条件**，依赖 C 的真实耗时，先 mock）

- PRD 只有「直线 >25km」单条件，**已改为双条件**：直线 > `city_config.spread_straight_km` **且** 耗时 > `spread_duration_minutes` **且** 两点 `is_core_urban = true`
- 阈值从 `rules.json#/rules[rule_03_spread]/city_config` 读，**禁止硬编码 25**
- 缺 `is_core_urban` → 跳过（缺数据不猜）
- 验收：TC-03-01 ~ TC-03-06（远且慢触发 / 远但快不触发 / 近但慢不触发 / 郊区不触发）

### B6 Rule-04 同质化

- 按 `category.level2` 在**同一日内**计数，`≥3` 触发
- 文案插值：`count` 必须反映实际数量（**不得写死 3**——出现 5 个时要显示 5）
- 分类不在 `mappings.category_taxonomy` 内 → **跳过该点，不报错**
- 验收：TC-04-01 ~ TC-04-05

### B7 行程版本与冲突确认落库

- `version` 乐观锁：`PATCH` 带 `If-Match`，冲突返回 `VERSION_CONFLICT` + 服务端最新 version
- `revision_history[]` 记录：`create` / `add_stop` / `remove_stop` / `reorder` / `move_to_evening` / `change_anchor` / `confirm_conflict` / `update_config`
- 未处理的硬确认（`outcome=pending`）提交行程时 → `RULE_HARD_CONFLICT` + 待确认列表 + `conflict_confirm_token`

---

## 4. AI 开发提示词（可直接复制）

### 提示词 0｜`rules_engine` 模块骨架（**先做这个**）

```
你是资深 Python 后端工程师。项目宿主是「模块工作台」，每个模块是独立进程、通过本地 HTTP 通信。
通信约定见 contracts/MODULE_RUNTIME.md，端点定义见 contracts/schemas/api.schema.json。

任务：实现宿主模块 modules/rules_engine（规则与时序引擎），依赖 trip_engine。

要求：
1. manifest.json：{"id":"rules_engine","name":"规则引擎","version":"0.1.0","dependencies":["trip_engine"]}
2. plugin.py 导出 run(context)：
   a. 端口取 context.config 的 "port"（缺省或 0 → 绑定 0）；
   b. 生成随机令牌；
   c. 启动前：读 <root>/data/_registry/trip_engine.json 拿 base_url 与 token，
      轮询 GET /health 直到 ready，最长 30s、间隔 200ms→1s 退避；超时则抛错并写明确日志；
   d. 绑定成功后写自己的注册文件到 data/_registry/rules_engine.json（格式照 MODULE_RUNTIME.md §2）；
   e. 主循环用 while not context.wait(1): pass。
3. 实现端点：GET /health（免令牌）、POST /trips/{id}/rules:evaluate、
   POST /trips/{id}/conflicts/{notice_id}/confirm。
4. 鉴权：除 /health 外校验 X-Module-Token。
5. 对外调用 trip_engine 时必须带它的令牌；调用失败按 contracts/errors.json 返回 UPSTREAM_* 错误码，
   同时把自己的 /health 置为 degraded / upstream_down。
6. 不要在引擎里存行程数据 —— 行程的唯一持久化方是 trip_engine。

输出：manifest.json + plugin.py + 契约测试（port=0 启动，断言 /health 与 /rules:evaluate 的响应体过 schema）。
```

### 提示词 1｜Rule-01（今天就能做完的那块）

```
你是资深 Python 后端工程师。项目有契约包 contracts/，规则定义唯一来源是 contracts/rules.json，
时间基准见 contracts/TIME_BASELINE.md，测试用例见 contracts/RULE_TEST_CASES.md。

任务：实现 Rule-01 闭馆日强冲突判定（纯函数，不依赖时间轴）。

要求：
1. 输入：day.date（Asia/Shanghai 日期）、poi.operating_rules（closure_rules[]、closure_data_status、
   is_enclosed_attraction）。
2. 触发条件与例外优先级严格按 contracts/rules.json 的 rules[rule_01_closure]：
   trigger.all 两个条件 + exception_precedence 四条（holiday_exception_open 优先于 weekly 等）。
3. 缺失数据处理按 missing_data_policy 三态：unknown → 软提示 rule.closure.data_unknown（禁止静默放行）；
   unverified → rule.closure.data_unverified；verified → 正常求值。
4. 输出 notice 对象，字段结构照 contracts/schemas/trip.schema.json 的 $defs/notice：
   rule_id / severity / outcome / channel / message_key / message_args / raised_at / expires_on_reorder。
5. 绝对不要在函数里拼中文字符串，只返回 message_key 与 message_args。
6. 星期编号是 ISO 8601（1=周一 … 7=周日），见 contracts/enums.json#/weekday。

输出：实现代码 + 对应 contracts/RULE_TEST_CASES.md 里 TC-01-01 ~ TC-01-11 的 11 个单测。
```

### 提示词 2｜规则执行框架（含方案 A 护栏）

```
实现规则执行框架，严格按 contracts/rules.json 的 execution_model。

要求：
1. 四步顺序固定：时序推演 → 硬规则(Rule-01) → 软规则并行求值(02/03/04) → 汇总渲染。
2. 【关键】evaluate() 内不得出现任何对 ordered_stops 的写操作。软规则只返回 notices。
   请额外写一条测试：求值前后对 ordered_stops 做深比较快照，断言完全一致。
3. max_iterations 固定为 1（方案 A 下引擎不自触发）。
4. 缺数据的规则必须进入返回值的 skipped_rules[]，格式 {rule_id, reason}，
   reason ∈ {missing_data, no_match, locked}。
5. 汇总渲染按 severity_order 排序，按 channel_capacity 分配承载位，溢出合并为「还有 N 条建议」。
6. 返回值结构：{notices: Notice[], skipped_rules: [{rule_id, reason}]}。

输出：框架代码 + TC-X-01 ~ TC-X-07 的测试。
```

### 提示词 3｜时序推演

```
实现多日时序推演，遵循 contracts/TIME_BASELINE.md。

要求：
1. Day 1 起点 = anchor_arrival.arrival_at + border_buffer_minutes(默认90)。
   Day 2..N 起点 = date + days[].daily_start_local。
2. 第 i 个点：arrival_at = 上一站 departure_at + transit_from_previous.duration_seconds；
   departure_at = arrival_at + planned_dwell_minutes * 60。
3. 时间一律按 Asia/Shanghai 判定星期与时段；存储用 UTC 秒。禁止使用服务器本地时区。
4. transfer_overhead.counts_in_timeline=true 时，换乘上浮要计入耗时，
   但必须用 duration_seconds * factor 计算，不得改写 duration_seconds 字段（幂等要求）。
5. locked=true 的停靠点位置不可被移动；「末位」定义为当日最后一个未锁定位置。
6. 跨零点：arrival_at 可跨零点，日期归属按开始时刻所在日。

输出：实现代码 + 测试：① 用 contracts/examples/trip_shanghai_2d.json 断言时间轴自洽；
② 23:30 抵达的跨零点用例；③ transfer_overhead 多次重算结果不变（幂等）。
```

---

## 5. 预期达到的效果（验收清单）

**模块层验收（新增，先过这关）**
- [ ] `modules/rules_engine` 能被宿主安装、启用、运行；页面显示运行中
- [ ] 启动时正确等待 `trip_engine` 就绪；把 `trip_engine` 停掉后，你的 `/health` 变 `degraded`（`upstream_down`），业务端点返回 503 + `UPSTREAM_*`，且**不自己重启依赖**
- [ ] 注册文件格式符合 `MODULE_RUNTIME.md` §2
- [ ] 除 `/health` 外不带令牌一律 403
- [ ] **单模块可独立测试**：`python -m unittest discover -s modules/rules_engine/tests -v`（用 `trip_engine` 的 mock 或真实实例，不要求全链路）

**功能验收**
- [ ] `RULE_TEST_CASES.md` 的 **35 条 TC 全绿**（Rule-01 11 条、Rule-02 10 条、Rule-03 6 条、Rule-04 5 条、跨规则 7 条——注：03/04 合计与文档编号一致即可）
- [ ] **`evaluate()` 快照测试通过**：求值前后 `ordered_stops` 完全一致
- [ ] 输入 `trip_shanghai_2d.json`，输出的时间轴满足 `departure - arrival == dwell × 60`
- [ ] `closure_data_status=unknown` 时返回软提示，**不是空 notices**
- [ ] 同一天命中 4 条软提示时，按承载位容量渲染且不互相覆盖
- [ ] 硬确认未处理时提交行程 → 返回 `RULE_HARD_CONFLICT` + 待确认列表
- [ ] 带同一 `Idempotency-Key` 重放 → 返回首次结果，不重复写 `revision_history`

**工程质量**
- [ ] 规则逻辑里**没有一个中文字符串字面量**（文案全走 `message_key`）
- [ ] 所有阈值来自 `rules.json` / `mappings.json`，无硬编码（尤其 Rule-03 的 25km、Rule-04 的 3）
- [ ] 时区相关测试：TZ-1（伦敦用户判定上海周一）、TZ-2（跨零点）、TZ-4（裸时刻被拒）
- [ ] `contracts/scripts/validate.py` 在你本地全绿

**联调验收**
- [ ] 提供给 A 的 `POST /trips/{id}/rules:evaluate` 返回结构与 `trip.schema.json#/$defs/notice` 一致
- [ ] 用 C 的 mock `RouteSegment` 跑通 Rule-03，切换真实 Adapter 后不需要改规则代码

---

## 6. 常见坑

1. **按 PRD 3.3 的流程图实现会漏两条规则**——流程图只有 3 个框且编号错位，**以 `rules.json` 为准**。
2. **不要为了「体验顺滑」让软规则自动改单**——这是已决策的方案 A，改了 CI 会拦下（`validate.py` 有 6 项方案 A 硬检查）。
3. **不要把 `transfer_overhead` 的结果写回 `duration_seconds`**——会造成反复重算时 30% 叠加成 69%。
4. **不要用「就近季节」兜底 `T_light`**——跨季行程（9–10 月）没有匹配窗口时应当**不触发**。
5. **不要在缺数据时返回「通过」**——`closure_days: []` 与「未采集」是两种语义，必须区分（靠 `closure_data_status`）。
