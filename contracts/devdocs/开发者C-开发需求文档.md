# 开发者 C · 开发需求文档 —— 路线与离线

> **主责模块**：模块四（微观门到门交通路线规划）Route Adapter + 三模态对比卡、模块五（现场求助与离线辅助）离线包 + 问路卡
> **你交付的是两个宿主模块**：`route_adapter`（路线适配，依赖 `trip_engine`）+ `offline_kit`（离线包，依赖 `trip_engine`、`route_adapter`）
> **额外最高优先级**：**Mock 路线服务**（它不属于任何 PRD 模块，但 A 和 B 都在等它）
> **不负责**：规则判定（B）、行程结构（A）
> **契约版本**：`contracts/` 0.3.0-draft（含 **C7 模块运行时**）

---

## 0. 你的代码怎么跑起来（先读这节）

宿主是「模块工作台」：每个模块是**独立进程**，模块间通过**本地 HTTP** 通信（契约见 `contracts/MODULE_RUNTIME.md`）。

```
modules/
├── route_adapter/                  ← 路线适配（三方归一化、降级、缓存）
│   ├── manifest.json               dependencies: ["trip_engine"]
│   └── plugin.py                   run(context) → 起 HTTP
└── offline_kit/                    ← 离线包 + 问路卡
    ├── manifest.json               dependencies: ["trip_engine","route_adapter"]
    └── plugin.py                   run(context) → 起 HTTP
```

**你的模块纪律**：

| 规则 | 说明 |
| --- | --- |
| `route_adapter` 依赖 `trip_engine` | 启动时读 `data/_registry/trip_engine.json` 拿 `base_url` + `token`；轮询 `/health` 最长 30s（200ms→1s 退避） |
| `offline_kit` 依赖两个模块 | 同样按注册表发现；任一未就绪则启动失败并写明确日志 |
| 依赖中途退出 | `/health` 置 `degraded`（`upstream_down`）+ 业务端点 503 + `UPSTREAM_*`；**不自己重启依赖** |
| 只被调用，不反向调 | 你不得调 `rules_engine` 或 `web_workbench` |
| 端口与令牌 | 各自占端口（`config.port` 或 `0`），启动后写 `data/_registry/<module_id>.json`（格式照 `MODULE_RUNTIME.md` §2） |
| 必须实现 `GET /health` | 免令牌；其余端点校验 `X-Module-Token` |
| 三方 key 只在服务端 | **绝不下发给客户端**；key 从 `context.config` 或环境变量读，不进注册表、不进日志 |

**你要实现的端点**（`MODULE_RUNTIME.md` §3.2）：
- `route_adapter`：`POST /trips/{id}/days/{d}/routes:compute`、`GET /stations/{station_id}`、`GET /pois/{poi_id}/drop-off`、`GET /health`
- `offline_kit`：`POST /trips/{id}/offline-package`、`GET /health`

---

## 1. 你手上的契约文件

| 文件 | 你要用它做什么 |
| --- | --- |
| `contracts/MODULE_RUNTIME.md` | **模块怎么跑、端口与注册表、令牌、依赖等待**（先读这个） |
| `contracts/schemas/route.schema.json` | **Adapter 的唯一输出格式**，字段照抄，一个都别改 |
| `contracts/schemas/station.schema.json` | 核心站台库（PRD 缺的实体，进出站口/站内换乘的唯一来源） |
| `contracts/mappings.json` | `crs_conversion`（坐标转换责任）、`step_estimation`（步数假设）、`cache_keys`（geohash7 键与调用预算）、`degradation_matrix`（5 类依赖逐项降级）、`offline_package`（离线包必含字段）、`ask_card_templates`、`provider_field_map` |
| `contracts/errors.json` | `DEGRADED_RESULT`、`UPSTREAM_TIMEOUT`、`UPSTREAM_RATE_LIMITED` 的重试/熔断/幂等策略 |
| `contracts/schemas/api.schema.json` | `compute_routes` / `get_station` / `export_offline_package` 三个端点的请求响应 |
| `InboundRoute_PRD_三方能力核实清单.md`（工作区根目录） | **14 条必须实测的三方能力**，这是你的关键技术风险 |

参考样例：`contracts/examples/route_transit_transfer.json`（含长换乘 + 站台库出入口 + 30% 上浮系数）、`contracts/examples/route_degraded.json`（降级样例）、`contracts/examples/station_nanjing_east.json`（站台库）。

---

## 2. 三条不可违反的约定

| # | 约定 | 为什么 |
| --- | --- | --- |
| C-铁律-1 | **`source` 字段必须如实标注**：进出站口、站内换乘、落客点都要带 `source`（`curated` / `api` / `manual`） | 前端靠它区分「真的有」和「猜的」——缺失时隐藏该行，而不是显示占位或错误出口 |
| C-铁律-2 | **降级必须在数据层表达**：`data_source: "degraded"` + `degraded_reason` + `degraded_notice_key` + 数值字段为 `null`（**不是 0**） | 0 会被当成「免费/零换乘」参与规则计算，导致 Rule-02/03 级联失真 |
| C-铁律-3 | **坐标系统一由你单点负责**：内部主数据一律 `WGS84`，三方入参/返回按 `crs_conversion` 转换，**单向**，客户端与 B 的引擎不得自行转换 | 高德/腾讯=GCJ-02、百度=BD-09，混用会产生数百米偏移——而这正是 PRD 自述的痛点 |

---

## 3. 你的十个交付模块（**C1 最优先**）

### C1 Mock 路线服务（**第一天就出**）

- 输出结构必须与真实 Adapter **完全同签名**，`data_source: "mock"`
- 数据来源：`contracts/examples/route_transit_transfer.json` + `route_degraded.json`
- 验收：A 能用它渲染对比卡、B 能用它跑 Rule-03，且**通过 `route.schema.json` 校验**
- 切换真实实现时**只改一个环境变量**，调用方代码不动

### C2 Adapter 骨架（三方归一化）

- 把三家的返回映射成统一 `RouteSegment`，字段映射见 `mappings.provider_field_map`
- 同一段路的三种输入（高德/腾讯/百度）产出结构必须一致
- 三模态统一放 `variants[]`（Transit/Taxi/Walk），客户端不为每种模式各写一套

### C3 坐标系统一

- 入参/返回按 `provider_crs` 转换到 WGS84，**单向**（WGS84 是内部基准）
- 精度要求：入口点级 `precision_m ≤ 50`
- 验收：已知坐标的转换往返误差 < 50m

### C4 缓存与调用预算（直接决定 1.2s 指标能否达标）

- 缓存键：`{geohash7(from)}:{geohash7(to)}:{mode}:{departure_bucket_30min}`，TTL 1800s
- **一次拖拽的三方调用 ≤4 次且并发执行**（`cache_keys.call_budget`）
- 策略：`prefetch_modes: ["transit"]`、`lazy_modes: ["taxi","walk"]`（非当前 Tab 懒加载）
- 验收：mock 计数断言一次拖拽 ≤4 次调用；缓存命中率可观测

### C5 降级与部分成功（5 类依赖逐项）

按 `mappings.degradation_matrix` 逐项实现，**不允许只做「三方超时→直线距离」这一条**：

| 依赖 | 失败时 | 关键要求 |
| --- | --- | --- |
| Direction API | 直线距离粗算 | `cost`/`transfer_count`/`congestion_level` 返回 `null` + `degraded_reason` |
| 逆地理编码 | 要求用户手动打点 | `must_notify: true` |
| 实时公交 | 用计划时刻表，换乘预警不可用 | 文案必须提示 |
| 规则库（闭馆/亮灯） | **软提示，禁止静默放行** | 这条与 B 的 Rule-01 联动 |
| 地图瓦片 | 保留纯文字流程树 | 与模块五联动 |

**另外要实现**：连接 1s / 读取 2s 超时、重试 ≤2 次（300/800ms 退避）、429 不重试、错误率 >50% 熔断 5s、`Idempotency-Key` 24h、**降级后要有恢复探测**（PRD 缺失）

### C6 三模态对比卡

- 每个区间展示 Transit / Taxi / Walk-Bike 三组，字段见 `route.schema.json#/$defs/variant`
- 三个展示项必须真的有数据来源：**「距离 ≤3km 高亮」**（`distance_meters`）、**「步行总长」**（`walking_distance_meters`）、**「消耗步数」**（`estimated_steps`，按 `step_estimation` 的步长/步速假设）
- 费用是区间（`cost.min/max`），不是单值；`congestion_level` 枚举
- `prefer_taxi=true` 时打车置 `is_default_tab`（是否自动切换是遗留决策 **D-1**，先按契约实现开关）

### C7 CuratedStation 数据导入与覆盖标注

- 字段模型见 `station.schema.json`：进出站口（`access_points[]`）、站内换乘（`interior_transfers[]`）、线路方向与颜色
- **`coverage.completeness`** 决定前端能展示到哪一层：`full` / `partial` / `access_points_only` / `none`
- `none` 时 3.5 的微观增强**整体降级为纯文本**，不显示占位
- 覆盖范围是遗留决策 **D-5**，先按「上海核心枢纽 Top N」实现

### C8 离线包

- 必含字段见 `offline_package.must_include`：**固化时序 + 站点中英文名 + 线路号与颜色 + 进出站口编号 + 区段步行距离与方向 + 问路卡模板键**
- 存储收敛为 **IndexedDB**（LocalStorage 容量与 5MB 配额冲突）
- 版本化：绑定 `trip.version`，不匹配时提示「离线数据可能过期」；`ttl_hours: 24`
- **不含**：三模态对比卡（拥堵/费用离线不可得）、实时公交
- 体积 ≤5MB（字体子集 ≤1.5MB）

### C9 问路卡（5 类节点模板）

- 节点类型：`station_entrance` / `transfer` / `station_exit` / `drop_off` / `poi_arrival`，模板见 `ask_card_templates`
- **方向字段缺失时用 `direction_fallback`**：宁可只问「请问 2 号线怎么走」，也不显示空方向
- 交互：高对比度模态（白底纯黑、字号 ≥32pt）、关闭方式、防熄屏（现场举手机给路人看是高频场景）

### C10 三方能力实测（14 条）并回填

按 `InboundRoute_PRD_三方能力核实清单.md` 逐条实测，回填 `mappings.provider_field_map`；**不可得的字段要从 3.5 承诺里删除或降级**，不要留假数据。

---

## 4. AI 开发提示词（可直接复制）

### 提示词 0｜`route_adapter` 模块骨架 + Mock 开关（**第一天就做这个**）

```
你是资深 Python 后端工程师。项目宿主是「模块工作台」，每个模块是独立进程、通过本地 HTTP 通信。
通信约定见 contracts/MODULE_RUNTIME.md；RouteSegment 的唯一格式是 contracts/schemas/route.schema.json；
参考实现见 contracts/examples/route_transit_transfer.json 与 route_degraded.json。

任务：实现宿主模块 modules/route_adapter，并内置可切换的 Mock 数据源。

要求：
1. manifest.json：{"id":"route_adapter","name":"路线适配器","version":"0.1.0","dependencies":["trip_engine"]}
2. plugin.py 导出 run(context)：
   a. 端口取 context.config 的 "port"（缺省或 0 → 绑定 0）；
   b. 生成随机令牌；轮询 trip_engine 的 /health 直到 ready（最长 30s，200ms→1s 退避）；
   c. 启动成功后写 data/_registry/route_adapter.json（格式照 MODULE_RUNTIME.md §2）；
   d. 主循环 while not context.wait(1): pass。
3. 数据源开关：config 里读 "provider"，取值 "mock" | "amap" | "tencent" | "baidu"。
   mock 模式下不访问外网，返回参考样例的结构，data_source 填 "mock"。
   【关键】mock 与真实实现必须同签名，切换只改配置，调用方代码零改动。
4. 实现端点：GET /health（免令牌）、POST /trips/{id}/days/{d}/routes:compute、
   GET /stations/{station_id}、GET /pois/{poi_id}/drop-off。
5. 三方 key 只从 context.config 或环境变量读取，绝不写进注册表或日志，绝不下发给客户端。
6. 另提供 MOCK_DEGRADE 开关：打开时返回 route_degraded.json 那种结构
   （数值字段为 null、data_source="degraded"、degraded_reason="timeout"、degraded_notice_key 已填），
   供 A 和 B 验证降级路径。

输出：manifest.json + plugin.py + 契约测试：① /health 通过 schema；② mock 响应通过
route.schema.json 校验；③ MOCK_DEGRADE 打开时数值字段为 null 而不是 0。
```

### 提示词 1｜Mock 路线服务（已被提示词 0 覆盖时跳过）

```
你是资深后端工程师。项目有契约包 contracts/，RouteSegment 的唯一格式定义是
contracts/schemas/route.schema.json，参考实现在 contracts/examples/route_transit_transfer.json
与 contracts/examples/route_degraded.json。

任务：实现一个 Mock 路线服务，供其他两位开发者联调。

要求：
1. 接口签名与真实 Adapter 完全一致（POST /api/v1/trips/{trip_id}/days/{day_index}/routes:compute），
   通过一个环境变量 ROUTE_PROVIDER=mock|amap 切换，调用方代码不需要改动。
2. 返回值必须通过 contracts/schemas/route.schema.json 校验，data_source 填 "mock"。
3. variants[] 至少返回 transit 与 taxi 两种，transit 里包含一段 kind="transfer" 的 segment，
   transfer.walking_distance_meters = 320（触发长换乘预警），source = "curated"。
4. 提供一个特殊开关 MOCK_DEGRADE=1：返回 route_degraded.json 那种降级结构
   （数值字段为 null、data_source="degraded"、degraded_reason="timeout"、degraded_notice_key 已填）。
5. 不要硬编码地理数据；用从库里按 from/to 查表的方式返回，便于后续替换。

输出：服务代码 + 一个测试，断言 mock 响应通过 route.schema.json 校验。
```

### 提示词 2｜Adapter 归一化与坐标转换

```
实现 Route Adapter：把高德/腾讯/百度的路线结果归一化为 contracts/schemas/route.schema.json 的结构。

要求：
1. 坐标系统一：内部基准 WGS84；高德/腾讯返回 GCJ-02、百度返回 BD-09，
   全部单向转换到 WGS84（见 contracts/mappings.json 的 crs_conversion）。
   转换只允许在 Adapter 内发生，不要把转换函数暴露给调用方。
2. 三模态统一放 variants[]（transit/taxi/walk 或 bike），字段照 $defs/variant。
3. 距离类字段不得缺失：distance_meters、walking_distance_meters、estimated_steps
   （步数按 mappings.step_estimation 的步长假设计算）。
4. 长换乘：transfer.walking_distance_meters >= 200 时置 has_long_transfer=true，
   并填 transfer_overhead{applies_to:"walking_segment", factor:1.3, counts_in_timeline:true}。
   【关键】不要改写 duration_seconds，只提供系数，保证多次重算幂等。
5. 缺失字段一律返回 null，不要用 0 或空字符串兜底。

输出：Adapter 代码 + 测试：① 三家输入产出结构一致；② 已知坐标转换误差 <50m；
③ 同一区间连续归一化两次，transfer_overhead 结果不变。
```

### 提示词 3｜降级与部分成功

```
实现降级机制，严格按 contracts/mappings.json 的 degradation_matrix 与 contracts/errors.json。

要求：
1. 五类依赖逐项实现降级：route_api / reverse_geo / realtime_transit / rules_data / tiles。
   不允许只做「三方超时→直线距离」这一条。
2. 降级时：data_source="degraded"、degraded_reason 取枚举值、数值字段为 null（不是 0）、
   partial=true、degraded_notice_key 指向 mappings.notice_templates 里已登记的键。
3. HTTP 状态：降级仍返回 200（errors.json 的 DEGRADED_RESULT），但响应体必须带 above 标记；
   真正失败才返回 504/429/501。
4. 重试与熔断：connect 1s / read 2s；重试 ≤2 次（300ms、800ms 退避）；
   429 不重试；错误率 >50% 熔断 5s。
5. 支持 Idempotency-Key（24h 窗口，重放返回首次结果，不重复调用三方）。
6. 降级后要有恢复探测（PRD 缺失）：熔断窗口结束后半开探测，恢复则切回正常数据源。

输出：实现代码 + 逐依赖的故障注入测试（5 个），断言返回结构与文案键正确。
```

### 提示词 4｜离线包

```
实现离线包生成与端侧缓存，按 contracts/mappings.json 的 offline_package。

要求：
1. must_include 的字段必须全部包含：固化时序（arrival_at/departure_at）、站点中英文名、
   线路号与颜色、进出站口编号、区段步行距离与方向、问路卡模板键（不是最终文案）。
2. 存储用 IndexedDB；容量上限 5MB（字体子集 ≤1.5MB 计入）。
3. 版本化：绑定 trip.version；本地版本与服务端不一致时提示「离线数据可能过期」；
   ttl_hours=24。
4. excluded：三模态对比卡（拥堵/费用离线不可得）、实时公交 —— 离线态要给出对应降级文案。
5. 离线态下问路卡必须仍可用（数据来自 must_include 的进出站口字段）。

输出：生成接口 + 端侧缓存代码 + 测试：① 飞行模式冷启可查全部时序；② 版本不匹配时提示；
③ 包体积断言 ≤5MB。
```

---

## 5. 预期达到的效果（验收清单）

**模块层验收（新增，先过这关）**
- [ ] `modules/route_adapter` 与 `modules/offline_kit` 能被宿主安装、启用、运行
- [ ] 启动时正确等待依赖就绪；把 `trip_engine` 停掉后 `/health` 变 `degraded`（`upstream_down`），业务端点 503 + `UPSTREAM_*`
- [ ] 两个模块的注册文件格式符合 `MODULE_RUNTIME.md` §2
- [ ] 除 `/health` 外不带令牌一律 403；**三方 key 不出现在注册文件、日志、任何响应体里**
- [ ] Mock 与真实数据源切换**只改 `config.provider`**，调用方（A 的 `web_workbench`、B 的 `rules_engine`）零改动
- [ ] **单模块可独立测试**：`python -m unittest discover -s modules/route_adapter/tests -v`

**Mock 与 Adapter**
- [ ] Mock 服务第一个交付，A 能渲染对比卡、B 能跑 Rule-03
- [ ] 三家地图返回归一化后结构一致（同一段路对比测试）
- [ ] 坐标转换误差 <50m，且转换函数未暴露给其他模块
- [ ] 一次拖拽的三方调用 **≤4 次**且并发

**降级（评审重点）**
- [ ] 5 类依赖逐项故障注入通过，降级时数值为 `null`（不是 0）
- [ ] 降级响应 HTTP 200 但带 `degraded_reason` + `degraded_notice_key`，前端能直接展示
- [ ] 重试/熔断/幂等/恢复探测都有测试

**展示项有数据来源**
- [ ] 「距离 ≤3km 高亮」用 `distance_meters` 判定
- [ ] 「步行总长」用 `walking_distance_meters`
- [ ] 「消耗步数」用 `estimated_steps`（按步长假设）
- [ ] 「换乘 ≥200m 预警」用 `transfer.walking_distance_meters`，展示原始值 + 30% 系数说明

**站台库与离线**
- [ ] `coverage.completeness=none` 时微观增强整体降级为纯文本，不显示占位
- [ ] 离线包含进出站口编号（否则问路卡会退化为空）
- [ ] 5 类问路卡模板可用；方向缺失时走 `direction_fallback`
- [ ] 离线包 ≤5MB，版本不匹配有提示

**实测**
- [ ] 14 条三方能力有实测结论，`provider_field_map` 已回填
- [ ] 不可得字段已从 3.5 承诺中移除或降级，**没有留假数据**

---

## 6. 常见坑

1. **不要把降级做成「数值填 0」**——0 会被 B 的规则当成「免费」「零换乘」，导致 Rule-02/03 级联失真。
2. **不要只做一句降级**——PRD 只写了「三方超时→直线距离」，实际有 5 类依赖，漏掉逆地理编码会让整个行程不可用却没有任何提示。
3. **不要让调用方做坐标转换**——转换必须收敛在 Adapter 内部，否则三个模块各转一次，偏移会叠加。
4. **不要用 `has_long_transfer` 这个布尔值做展示**——它只是派生结果，展示要用 `walking_distance_meters` 原始值（契约已明确保留原值）。
5. **不要忘记 `source` 字段**——进出站口/换乘/落客点少了它，前端无法判断该隐藏还是该展示，最后会显示出错误的出口编号。
6. **不要假设三方一定给得出进出站口**——这是 14 条实测里风险最高的一条，实测结论直接决定 `CuratedStation` 要不要建、3.5 那一整段能不能交付。
