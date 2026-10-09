# 开发者 A · 开发需求文档 —— 行程与选点

> **主责模块**：模块一（行程初始设定引擎）、模块二（地图互动选点与 POI 详情层，面板部分）
> **你交付的是两个宿主模块**：`trip_engine`（行程数据服务）+ `web_workbench`（前端工作台）
> **交付物**：初始化偏好看板、地图选点工作台、POI 详情抽屉、`Add to Day [X]` 交互
> **不负责**：规则判定（B）、路线数据（C）、推荐排序算法（B 提供结果，你只渲染）
> **契约版本**：`contracts/` 0.3.0-draft（已冻结 C1 时区/时间类型、C2 星期 ISO、C3 方案 A、**C7 模块运行时**）

---

## 0. 你的代码怎么跑起来（先读这节，再读下面）

宿主是「模块工作台」：每个模块是**独立进程**，模块间通过**本地 HTTP** 通信（契约见 `contracts/MODULE_RUNTIME.md`）。

你在 `modules/` 下交付两个目录：

```
modules/
├── trip_engine/                    ← 行程数据服务（后端）
│   ├── manifest.json               dependencies: []
│   └── plugin.py                   run(context) → 起 HTTP 服务
└── web_workbench/                  ← 前端工作台（页面 + 聚合）
    ├── manifest.json               dependencies: ["trip_engine","rules_engine","route_adapter"]
    └── plugin.py                   run(context) → 起 HTTP，serve 前端；反代/调用三个引擎
```

**你的模块纪律**（`MODULE_RUNTIME.md` §1 的硬约束）：

| 规则 | 说明 |
| --- | --- |
| `trip_engine` 只被调用，不主动调别人 | 它是依赖链最上游，**允许被 B/C 调用，禁止反向调用** |
| `web_workbench` 是唯一可以「代表用户」调用其他模块的模块 | 它持有前端会话；所有用户操作都从它出发 |
| 不要把业务数据塞进 `context.config` | 那只是启动时快照，会被页面展示；业务数据一律走 HTTP |
| 不要 import 别的模块的 Python 代码 | 进程隔离，import 的是副本，状态不共享 |
| 端口与令牌 | 每个模块自己占端口（`config.port` 或 `0` 自动分配），启动成功后写 `<root>/data/_registry/<module_id>.json`，格式见 `MODULE_RUNTIME.md` §2 |
| 必须实现 `GET /health` | 唯一不需要令牌的端点；宿主用它显示模块状态 |
| 除 `/health` 外所有请求要带 `X-Module-Token` | 令牌是各模块启动时随机生成并登记在注册表里的，**不要写进配置文件** |

**你消费别人什么**：`web_workbench` 启动时读注册表拿 `rules_engine` / `route_adapter` 的 `base_url` + `token`，然后转发用户的规则求值与路线计算请求。依赖没就绪时轮询 `/health`（最长 30s，200ms→1s 退避）。

**联调最省事的做法**：`web_workbench` 用一个 `ENGINE_BASE` 环境变量指向「真实模块」或「C 的 Mock」，前端代码不动。这样 B/C 没做完时你也能先把界面跑通。

---

## 1. 你手上的契约文件（开工前读完这七个）

| 文件 | 你要用它做什么 |
| --- | --- |
| `contracts/MODULE_RUNTIME.md` | **模块怎么跑、端口怎么登记、令牌怎么传**（先读这个） |
| `contracts/generated/domain.ts` | **唯一的类型来源**，直接 import，不要自己定义 interface |
| `contracts/schemas/poi.schema.json` | POI 字段、必填、枚举、空值语义（详情抽屉全靠它） |
| `contracts/schemas/trip.schema.json` | `TripInstance` 结构、`days[].daily_start_local`、`pin_state` 相关字段 |
| `contracts/schemas/api.schema.json` | 端点清单（你的模块要实现 `trip_engine` 那 6 个，消费 `rules_engine`/`route_adapter` 的端点） |
| `contracts/mappings.json` | `drawer_field_map`（详情 4 行怎么渲染）、`pacing_cap`、`interests_weight`、`weighting` |
| `contracts/enums.json` | `pin_state`（**5 态**）、`day_status`、`stop_type`、`notice_channel` |
| `contracts/errors.json` | `RULE_HARD_CONFLICT`、`VERSION_CONFLICT`、`UPSTREAM_*` 的客户端处理 |

参考样例：`contracts/examples/poi_bund.json`（POI 长什么样）、`contracts/examples/trip_shanghai_2d.json`（含跨零点抵达的完整行程）。

---

## 2. 三条不可违反的约定

| # | 约定 | 为什么 |
| --- | --- | --- |
| A-铁律-1 | **字段名不许改名**。后端返回 `arrival_at`，你就用 `arrival_at`；不许在客户端改成 `arriveTime` | `generated/domain.ts` 是唯一命名来源，改名会导致联调对不上且类型检查失效 |
| A-铁律-2 | **不自己算规则**。是否闭馆冲突、是否亮灯、是否跨度超标，全部由 B 的 `rules_engine` 返回 `notices[]`，你只负责渲染 | 规则逻辑必须在服务端单一实现，否则前后端两套判断必然不一致 |
| A-铁律-3 | **空值不等于空白**。字段为 `null` 时，按 `mappings.drawer_field_map` 的 `null_policy` 处理：**隐藏该行或显示「待确认」，不许显示「—」或空白** | PRD 最典型的坑：承诺展示 `Last Entry` 但示例数据是 `null`，前端如果直接渲染就是 bug |

---

## 3. 你的四个交付模块

### A1 初始化偏好看板（模块一）

**输入**：用户填 7 个字段 → **输出**：服务端返回的 `TripInstance`

| 字段 | 控件 | 契约要点 |
| --- | --- | --- |
| Destination City | 下拉单选 | 一期只有上海 |
| Duration (Days) | 步进器 | 1~15，决定生成几个 `days[]` |
| Party Composition | 胶囊单选 | `solo/couple/family_kids/senior`；选 family_kids/senior 时 `party_walk_multiplier=1.3` 且 `prefer_taxi=true`（**由服务端派生，你只展示结果**） |
| Pacing | 胶囊单选 | 区间按 `mappings.pacing_cap`：`relaxed 1-2 / balanced 3-4 / packed 5-6`（**PRD 写的 `Packed ≥5` 已作废，别照抄**） |
| Interests | 多选标签 | 可留空；留空时排序走 `interests_weight.empty_interests_default` |
| Arrival Anchor | 日期 + 时刻 + 口岸 | `T_start = T_arrival + 90min` 由服务端算，你只读 `activity_start_at` |
| Accommodation | 文本联想 + 地图打点 | 支持英文/拼音检索；反查失败时允许手动打点 |

**必须处理的边界**：`Duration=15` 但只选了 6 个 POI → 其余 9 天显示 `day_status: "empty"`，**不能显示成空白页**；抵达时刻 23:30 → Day 1 会返回 `day_status: "arrival_only"`，要专门设计这个状态的界面。

### A2 地图选点工作台（模块二面板）

- 双语底图 + 常驻锚点图钉（口岸=飞机/高铁、酒店=床位，不可删除）
- **图钉状态机有 5 态**（PRD 只写了 3 态，缺的那两个是前端一定会遇到的）：

| 状态 | 视觉 | 触发事件 |
| --- | --- | --- |
| `default` | 类目图标 + 简短英文名 | 未加入任何一天 |
| `added_current_day_unselected` | **正常色 + 当日序号（灰）** | Add to Day X 但未点击该图钉 |
| `added_other_day` | 灰度弱化 + 角标 `D2` | 已加入其他天 |
| `selected_current_day` | 高亮 + 当日序号 1,2,3 | 点击选中 |
| `added_conflict_warned` | 红色角标/描边 | 用户在闭馆冲突上点了 Proceed anyway |

**迁移事件清单**（每个都要有测试）：Add / Remove / Drag / Move to Evening / Proceed anyway / 切换浏览日。

**多天重复装载**：同一 POI 同时在 D2 与 D5 时显示 `D2/D5`，点击列出所有天并跳转（遗留决策 D-1 之外的交互细节，按此实现）。

### A3 POI 详情抽屉（模块二）

三行标头：英文大字 / 带声调拼音 / 中文规范汉字（拼音缺失时**隐藏 Line 2**，不许显示错误拼音）。

运营约束卡 4 行，**每行都要实现「字段 → 文案模板 → 空值降级」**（照 `mappings.drawer_field_map`）：

| 行 | 字段 | 有值时 | null/空时 |
| --- | --- | --- | --- |
| Opening & Closure | `opening_hours[]` + `closure_rules[]` | 逐条渲染；周闭渲染成 `Closed on Mondays` | `closure_data_status=unknown` → 显示「闭馆信息待确认」；`opening_hours=[]` → 隐藏整行 |
| Last Entry | `last_entry_time` | `16:00 Last Entry` | **隐藏该行** |
| Light-up Hours | `light_up.windows[]` | `19:00 - 23:00 (Summer)` | `light_up=null` 或 `windows=[]` → 隐藏该行 |
| Suggested Dwell | `dwell_time` | `kind=point` → `90 分钟`；`kind=range` → `1.5 - 2 Hours` | 缺失 → 显示默认 90 分钟并标注「参考值」 |
| Reservation（新增） | `reservation_required` | `需提前 N 天预约` | 隐藏该行 |

### A4 `Add to Day [X]` 交互（模块二）

- 点击 → 调 `POST /trips/{trip_id}/days/{day_index}/stops`
- 若返回 `RULE_HARD_CONFLICT`（HTTP 409）→ 按钮黄色警示态 + 弹出二次确认对话框，文案用返回的 `notices[].message_key` 去 `notice_templates` 取
- 用户确认 → 带 `conflict_confirm_token` 重发（`force: true`）
- 加入后卡片打红底警告标签；**用户把该点拖到别的天时，原确认按 `expires_on_reorder` 失效并重新校验**——这个必须实现，不能只在首次加入时判定

---

## 4. AI 开发提示词（可直接复制）

### 提示词 0｜`trip_engine` 模块骨架（**先做这个**）

```
你是资深 Python 后端工程师。项目宿主是「模块工作台」，每个模块是独立进程、通过本地 HTTP 通信。
通信约定见 contracts/MODULE_RUNTIME.md，端点定义见 contracts/schemas/api.schema.json，
字段定义见 contracts/schemas/trip.schema.json / poi.schema.json。

任务：实现宿主模块 modules/trip_engine（行程数据服务）。

要求：
1. manifest.json：{"id":"trip_engine","name":"行程引擎","version":"0.1.0","description":"...","dependencies":[]}
2. plugin.py 导出 run(context)，在 run 里：
   a. 端口取 context.config 的 "port"（缺省或 0 时绑定 0 让系统分配）；
   b. 生成 32 字节 urlsafe 随机令牌；
   c. 绑定成功后把注册文件写到 <root>/data/_registry/trip_engine.json，
      字段严格照 MODULE_RUNTIME.md §2 的格式（module_id/port/base_url/token/pid/
      contract_version/started_at/depends_on/endpoints）；
   d. 退出时删除注册文件；
   e. while not context.wait(1): pass —— 用 context.wait 做可被停止信号打断的主循环。
3. 实现 MODULE_RUNTIME.md §3.2 里属于 trip_engine 的 6 个端点，以及 GET /health。
4. 鉴权：除 /health 外，校验请求头 X-Module-Token 是否等于自己的令牌，否则 403。
5. Host 白名单只允许 127.0.0.1:<自己的端口> 与 localhost:<自己的端口>。
6. 数据持久化：行程存 context.data_dir 下的 JSON 文件，写入用「临时文件 + 原子替换」。
7. 返回值结构一律照 contracts/schemas/*.schema.json；错误体照 contracts/errors.json 的 envelope。

输出：manifest.json + plugin.py + 一个契约测试（启动服务用 port=0，断言 /health 与 /trips 响应体
通过对应 schema 校验）。
```

### 提示词 1｜初始化看板（把这段发给 AI 编码助手，附上 `contracts/` 目录）

```
你是资深前端工程师，在一个已有契约包的项目里开发。契约包在 contracts/ 目录，
字段名与类型一律以 contracts/generated/domain.ts 与 contracts/schemas/trip.schema.json 为准。

任务：实现「行程初始化偏好看板」（模块一）。
要求：
1. 7 个字段：Destination City / Duration(Days) / Party Composition / Pacing / Interests / Arrival Anchor / Accommodation，
   控件类型与校验规则见 contracts/schemas/trip.schema.json 的 required、enum、minimum/maximum。
2. Pacing 的单日点位上限必须从 contracts/mappings.json 的 pacing_cap 读取，
   不要硬编码数字（注意：PRD 里的 "Packed ≥5" 已作废，契约是 5-6）。
3. 提交时调 POST /api/v1/trips（见 contracts/schemas/api.schema.json 的 create_trip），
   请求体只包含 user_profile 与 anchor_* 字段。
4. 不要在客户端计算 T_start、walking 系数、poi_cap —— 这些是服务端派生字段，只读展示。
5. 必须处理两个边界：Duration=15 但只有 6 个 POI（其余天显示 day_status="empty" 的提示）；
   抵达时刻 23:30（Day 1 返回 day_status="arrival_only"，要有专门界面）。
6. 输出：组件代码 + 一个校验用单测，单测断言「family_kids 时展示 prefer_taxi=true 的提示」。

约束：不新增契约里没有的字段；不使用 any；所有网络错误按 contracts/errors.json 的 code 分支处理。
```

### 提示词 2｜POI 详情抽屉（最推荐先做，字段全冻结）

```
你是资深前端工程师。先读 contracts/mappings.json 的 drawer_field_map 与
contracts/schemas/poi.schema.json 的 operating_rules，再实现「POI 详情抽屉」。

要求：
1. 三行标头：names.en（大字）/ romanization.pinyin（带声调）/ names["zh-Hans"]；
   pinyin 缺失时隐藏第二行，不得用 name_zh 自动推导拼音。
2. 运营约束卡按 drawer_field_map 的 4 个条目逐行实现，每行实现三个分支：
   有值 / null / 空数组。降级行为严格按该文件的 null_policy 字段，不许自行发挥。
3. categories：category.label_en / label_zh 直接展示，不要重新翻译。
4. 写单测覆盖「4 行 × 3 种空值状态 = 12 个用例」，全部用 contracts/examples/poi_bund.json 的字段结构。
5. 特别验证：last_entry_time=null 时该行必须隐藏；closure_data_status="unknown" 时必须显示
   「闭馆信息待确认」而不是隐藏。

输出：组件代码 + 12 个单测。不要引入新的状态管理库。
```

### 提示词 3｜图钉状态机

```
实现地图图钉状态机。状态全集与迁移事件见 contracts/enums.json 的 pin_state 与
contracts/schemas/trip.schema.json 的 days[].ordered_stops[]。

要求：
1. 5 个状态：default / added_current_day_unselected / added_other_day /
   selected_current_day / added_conflict_warned。
2. 纯函数实现 getPinState(trip, poiId, currentDayIndex, selectedPoiId, notices)，
   便于单测；不要在图钉组件里内联判断逻辑。
3. 迁移事件：Add / Remove / Drag / MoveToEvening / ProceedAnyway / SwitchDay。
4. 多天重复装载时角标显示 "D2/D5"。
5. 单测：为 5 个状态各写 1 个用例，另加 6 个迁移用例。
```

---

## 5. 预期达到的效果（验收清单）

**模块层验收（新增，先过这关）**
- [ ] `modules/trip_engine` 与 `modules/web_workbench` 都能被宿主「安装 → 启用 → 运行」，页面显示运行中
- [ ] 两个模块启动后各自的 `data/_registry/<id>.json` 格式完全符合 `MODULE_RUNTIME.md` §2
- [ ] `GET /health` 免令牌可访问，宿主能读到 `status: ok`
- [ ] 除 `/health` 外不带 `X-Module-Token` 一律 403
- [ ] `web_workbench` 启动时按依赖轮询 `/health`；把 `rules_engine` 停掉后，`trip_engine` 不受影响，`web_workbench` 对规则相关的请求返回 503 + `UPSTREAM_*` 且界面有明确提示
- [ ] 停止模块后注册文件被删除；残留注册文件（模拟崩溃）下次启动能被正确覆盖或报错

**功能验收**
- [ ] 7 个字段全部可提交，服务端返回的 `TripInstance` 能通过 `trip.schema.json` 校验
- [ ] `Duration=15` 只有 6 个 POI 时，9 天显示 `empty` 状态，不是空白
- [ ] 抵达 23:30 的行程，Day 1 显示为 `arrival_only`
- [ ] 5 个图钉状态在两台设备上视觉一致，6 个迁移事件都能触发
- [ ] 详情抽屉 4 行 × 3 种空值 = 12 个用例全绿，**其中 `last_entry_time=null` 隐藏行、`closure_data_status=unknown` 显示「待确认」**
- [ ] `Add to Day` 遇硬冲突时按钮变黄 → 二次确认 → 确认后卡片红标
- [ ] 把已确认的红标点拖到别的天，红标自动清除并重新校验

**工程质量**
- [ ] 全部类型来自 `generated/domain.ts`，无自建 interface，无 `any`
- [ ] `python contracts/scripts/generate.py --check` 与 `validate.py` 在你本地全绿（说明你没改契约）
- [ ] 单测覆盖：A1 校验、A3 的 12 个空值用例、A2 的 11 个状态用例
- [ ] **单模块可独立测试**：`python -m unittest discover -s modules/trip_engine/tests -v` 不依赖其他模块

**联调验收（第 4–5 天）**
- [ ] `web_workbench` 通过注册表发现 `rules_engine` / `route_adapter`，用 `X-Module-Token` 调用成功
- [ ] 能接收 B 的 `POST /trips/{id}/rules:evaluate` 返回的 `notices[]` 并正确渲染到对应承载位（Toast / 气泡 / Banner / 卡片标签）
- [ ] `skipped_rules[]` 非空时（缺数据导致规则跳过）UI 有对应提示，而不是静默
- [ ] 把引擎切到 C 的 Mock（`ENGINE_BASE` 环境变量）时，前端代码零改动即可跑通

---

## 6. 常见坑（评审时会被挑出来的）

1. **不要把 PRD 的 3 态图钉照抄**——「已加入当天但未选中」是最常见的状态，漏了就没法渲染。
2. **不要把 `Packed ≥5` 照抄**——契约已改为 5-6 区间，硬编码会导致校验逻辑写不出来。
3. **不要在客户端算 `1.3` 系数**——`party_walk_multiplier` 是服务端派生字段，客户端只用它做「优先打车」的展示。
4. **不要显示「—」或空白表示 null**——按 `null_policy` 隐藏或显示「待确认」。
5. **不要用 `name_zh` 自动生成拼音**——多音字（长安 cháng/zhǎng）必错，缺失就隐藏该行。
