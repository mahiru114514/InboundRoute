# InboundRoute 模块化开发执行手册

> 前置：契约包 `contracts/` 已冻结到 **0.3.0-draft**（C1 时区/时间类型、C2 星期 ISO、C3 方案 A、C4 鉴权与三方 key 代理、C5 CRS 责任、**C7 模块运行时**）。
> 宿主：工作区里的「模块工作台」（`manager.py` / `core/` / `web/`）——**InboundRoute 的每个引擎都是一个可插拔模块**，独立进程、独立启停、通过本地 HTTP 互相调用。
> 本文回答一个问题：**契约定了、宿主有了，三个人具体怎么开发、怎么并行、怎么合。**
> 配套文档：`InboundRoute_模块开发说明书.md`（模块拆解）、`contracts/devdocs/开发者{A,B,C}-开发需求文档.md`（各自的需求）、`contracts/MODULE_RUNTIME.md`（通信约定）。

---

## 0. 五个模块与三个人的对应

| 宿主模块 | 目录 | 主责 | 依赖 |
| --- | --- | --- | --- |
| `trip_engine` | `modules/trip_engine` | **A** | 无 |
| `rules_engine` | `modules/rules_engine` | **B** | `trip_engine` |
| `route_adapter` | `modules/route_adapter` | **C** | `trip_engine` |
| `web_workbench` | `modules/web_workbench` | **A** | `trip_engine`、`rules_engine`、`route_adapter` |
| `offline_kit` | `modules/offline_kit` | **C** | `trip_engine`、`route_adapter` |

依赖链 `trip_engine → rules_engine / route_adapter → web_workbench / offline_kit` 与模块说明书里的三条硬依赖完全一致；宿主会强制启动顺序、禁止卸载被依赖的模块。

**通信纪律（C7，违反就会变成调不通的 bug）**：
- 模块间**只能走 HTTP**；端口自己占并登记到 `<root>/data/_registry/<module_id>.json`（格式见 `MODULE_RUNTIME.md` §2）；
- 除 `/health` 外都要带 `X-Module-Token`（各模块启动时随机生成，**不进配置文件**）；
- 调用方向恒为「下游 → 上游」，反向调用一律禁止；
- 不 import 别的模块的 Python 代码、不直接读写别的模块的 `data_dir`。

---

## 1. 开发的总原则（四条，违反就会返工）

| # | 原则 | 含义 | 怎么强制 |
| --- | --- | --- | --- |
| P1 | **契约优先** | 先定接口与字段，再写实现。字段名、类型、枚举一律照 `contracts/`，不许自己加 | CI 跑 `scripts/validate.py` + `generate.py --check` |
| P2 | **单一聚合点** | 行程数据的唯一持久化方是 `trip_engine`；时间轴与 notices 由 `rules_engine` 写回。谁都不直接改别人的数据目录 | 代码评审：只有 `trip_engine` 写 `data/trip_engine/` |
| P3 | **Mock 优先** | C 先出 Mock 数据源，A/B 不等真实三方 API；切换只改 `config.provider` | `route.schema.json` 的 `data_source: "mock"` 是合法值 |
| P4 | **每模块可独立跑测** | 每个模块的测试不要求全链路 | `python -m unittest discover -s modules/<id>/tests -v` |

---

## 2. 三个人各自的工作包

> 每块工作都归属一个宿主模块；**每块的验收都包含「模块能独立启停 + 单模块测试能跑」**（见各自 devdoc 的模块层验收）。

### A —— 行程与选点（模块 `trip_engine` + `web_workbench`）

**依赖的契约**（开工前必须读）
- `MODULE_RUNTIME.md`（模块怎么跑、端口与注册表、令牌）
- `generated/domain.ts`（前端类型，直接 import）
- `schemas/poi.schema.json`、`schemas/trip.schema.json`（字段与必填）
- `schemas/api.schema.json`（`trip_engine` 要实现 6 个端点；`web_workbench` 消费 `rules_engine`/`route_adapter`）
- `mappings.json`：`drawer_field_map`（详情 4 行怎么渲染）、`pacing_cap`、`interests_weight`、`weighting`（1.3 系数）
- `enums.json`：`pin_state`（**5 态，不是 PRD 的 3 态**）、`day_status`、`stop_type`

**工作包（可独立验收的 7 块）**

| # | 交付 | 归属模块 | 用到的契约 | 验收方式 |
| --- | --- | --- | --- | --- |
| A0 | `trip_engine` 模块骨架（manifest + `run(context)` + 注册表 + `/health` + 令牌） | `trip_engine` | `MODULE_RUNTIME.md` §2/§3 | 宿主能安装启用；注册文件格式正确；`/health` 免令牌可访问 |
| A1 | 初始化看板：7 字段控件 + 校验 | `web_workbench` | `api.create_trip`、`pacing_cap` | 提交后返回的 `TripInstance` 通过 schema 校验 |
| A2 | Day 容器与 `day_status` 可视化（含「未装载天数」） | `web_workbench` | `enums.day_status`、`unassigned_pois` | 选 15 天只填 6 个点 → 9 天显示 `empty` |
| A3 | 地图选点工作台 + 锚点图钉 | `web_workbench` | `enums.pin_state`、`weighting.prefer_taxi_effect` | 5 态逐态截图 + 状态迁移用例 |
| A4 | POI 详情抽屉（三行标头 + 运营约束 4 行） | `web_workbench` | `mappings.drawer_field_map` | 4 行 × 3 种空值 = 12 个用例 |
| A5 | `Add to Day [X]` 的警示态与二次确认 | `web_workbench` | `errors.json#RULE_HARD_CONFLICT`、`$defs/notice` | 硬冲突时按钮黄、确认后卡片红标；改期后红标清除 |
| A6 | 偏好参数映射层（UI 选择 → 引擎参数） | `trip_engine` | `mappings.weighting`、`pacing_cap`、`interests_weight` | 单测：`family_kids → party_walk_multiplier=1.3, prefer_taxi=true` |

**现在就能开工**：A0、A1、A2、A4。
**要等**：A5 依赖 B 的 `rules_engine`；A3 的「优先打车」是否自动切 Tab 是遗留决策 **D-1**。

> **A 的关键提醒**：`web_workbench` 是**唯一可以代表用户调用其他模块**的模块。它启动时读注册表拿 `rules_engine` / `route_adapter` 的 `base_url` + `token`；依赖没就绪时轮询 `/health`，超时要明确报错，不要静默降级成「没有提示」。

---

### B —— 时序与规则（模块 `rules_engine`）

**依赖的契约**
- `MODULE_RUNTIME.md`（模块骨架、依赖等待、注册表）
- `rules.json`（**唯一规则来源**：执行顺序、硬软、缺失策略、AC 矩阵）
- `RULE_TEST_CASES.md`（35 条 TC，直接当测试清单）
- `TIME_BASELINE.md`（时区、类型、派生公式、跨零点裁决）
- `schemas/trip.schema.json`（`days[].daily_start_local`、`arrival_at`/`departure_at`、`rule_notices`）
- `schemas/route.schema.json`（区段耗时与 `transfer_overhead`）
- `mappings.json`：`notice_templates`（文案键）、`category_taxonomy`（Rule-04 计数依赖）

**工作包（严格按依赖顺序，前两块可并行）**

| # | 交付 | 依赖 | 验收 |
| --- | --- | --- | --- |
| B0 | `rules_engine` 模块骨架（依赖 `trip_engine`、等待就绪、注册表、`/health`） | `MODULE_RUNTIME.md` | 宿主能安装启用；`trip_engine` 停掉后 `/health` 变 `degraded` |
| B1 | **Rule-01 闭馆判定（先做）** | 只依赖 `closure_rules` + `is_enclosed_attraction`，**与时间轴无关** | TC-01-01 ~ TC-01-11 全绿 |
| B2 | 规则执行框架（顺序 + 并集渲染 + `skipped_rules`） | `rules.json#/execution_model` | TC-X-01 ~ TC-X-07；断言 `evaluate()` 不写 `ordered_stops` |
| B3 | 时序推演（逐点 `arrival_at`/`departure_at`） | `daily_start_local`、区段耗时、`transfer_overhead.counts_in_timeline` | 时间轴自洽：`departure - arrival == dwell × 60`；跨零点用例 TZ-2 |
| B4 | Rule-02 亮灯（含 `still_early` 分支与 locked 末位） | B3 + `light_up.T_light_rule` | TC-02-01 ~ TC-02-10 |
| B5 | Rule-03 跨度（双条件 + 城市阈值表） | 区段真实耗时（`route_adapter`，先 mock） | TC-03-01 ~ TC-03-06 |
| B6 | Rule-04 同质化（分类字典 + 插值） | `category_taxonomy` | TC-04-01 ~ TC-04-05 |
| B7 | 行程版本与冲突确认落库 | `version`、`revision_history`、`notice.outcome` | 改期后旧确认失效；`RULE_HARD_CONFLICT` 拦截提交 |

**现在就能开工**：B0、B1（今天就能写完 + 11 条测试全绿）、B2 的框架骨架。
**要等**：B3 依赖 `trip_engine` 的行程结构（可先用示例 `trip_shanghai_2d.json` 当输入）；B5 依赖 `route_adapter` 的耗时（先 mock）。

> **B 的关键提醒**：`evaluate()` 里**绝对不允许出现对 `ordered_stops` 的写操作**。建议用「求值前后深比较快照」的测试来强制这条——这是方案 A 唯一的技术护栏，靠 code review 容易漏。

---

### C —— 路线与离线（Adapter + 面板③④）

**依赖的契约**
- `schemas/route.schema.json`（**Adapter 的唯一输出格式**，字段照抄）
- `schemas/station.schema.json`（核心站台库）
- `mappings.json`：`crs_conversion`、`step_estimation`、`cache_keys`、`degradation_matrix`、`offline_package`、`ask_card_templates`、`provider_field_map`
- `errors.json`（`DEGRADED_RESULT`、`UPSTREAM_*` 的重试与熔断策略）

**工作包（优先级：先 Mock，再真实）**

| # | 交付 | 依赖 | 验收 |
| --- | --- | --- | --- |
| C1 | **`route_adapter` 模块骨架 + Mock 数据源（最高优先）** | `MODULE_RUNTIME.md`、`route.schema.json` | 宿主能安装启用；`config.provider=mock` 时返回合法 RouteSegment；A/B 可立即联调 |
| C2 | Adapter 三方归一化 + 字段映射 | `mappings.provider_field_map` | 同一段路三种输入的输出结构一致 |
| C3 | 坐标系统一（GCJ-02/BD-09 → WGS84，单向） | `mappings.crs_conversion` | 往返用例：已知坐标转换误差 < 50m |
| C4 | 缓存与调用预算 | `cache_keys`（geohash7 键、TTL、`call_budget` ≤4 次） | 一次拖拽的三方调用数 ≤4（用 mock 计数） |
| C5 | 降级与部分成功 | `degradation_matrix`（5 类依赖逐项） | 逐依赖故障注入：返回 `degraded_reason` + `must_notify` 文案，`cost`/`transfer_count` 为 null 而非 0 |
| C6 | 三模态对比卡（Transit/Taxi/Walk） | `variants[]`、`congestion_level`、`cost` 区间 | 「≤3km 高亮」「步行总长」「消耗步数」三个展示项有数据来源 |
| C7 | CuratedStation 数据导入与 `coverage` 标注 | `station.schema.json` | 站台库缺该站时（`completeness: none`）整体降级，不显示占位 |
| C8 | `offline_kit` 模块骨架 + 离线包生成 | `MODULE_RUNTIME.md`、`offline_package.must_include` | 含站名/线号/进出站口；`version` 不匹配时提示过期 |
| C9 | 问路卡（按 5 类节点模板） | `ask_card_templates` | 方向字段缺失时用 `direction_fallback`，不显示空方向 |
| C10 | 三方能力实测（14 条）并回填 `provider_field_map` | 附录 D 清单 | 实测报告；不可得字段从 3.5 承诺中移除或降级 |

**现在就能开工**：C1（Mock 是全场最解除阻塞的一件事）、C3、C4、C5 的框架、C8、C9。
**要等**：C2/C10 依赖真实三方 key 与实测；C7 的覆盖范围是遗留决策 **D-5**。

> **C 的关键提醒**：`variants[]` 里每个指标都要带 `data_source`，`segments[].transfer` 和 `drop_off` 要带 `source`（`curated` vs `api`）。这样前端才能区分「真的有」和「猜的」——**缺失时隐藏该行，而不是显示占位或错误出口**。三方 key 只从配置/环境变量读，**不进注册表、不进日志、不下发客户端**。

---

## 3. 并行与集成（谁先谁后）

```
第 1 天    A0/A1/A2/A4 开工      B0/B1（Rule-01）开工     C1（route_adapter + Mock）开工   ← 三方互不阻塞
          （A0/B0/C1 都是模块骨架，建议同一天各自跑通「宿主能安装启用」）
第 2–3 天  A3 图钉                B2 规则框架              C2/C3 骨架
第 4–5 天  A5 与 B 联调           B3 时序（用 trip_engine） C4/C5 缓存与降级
第 6 天    ——                     B4 Rule-02               C6 对比卡（接真实 B3 时间轴）
第 7 天    ——                     B5 Rule-03（接 route_adapter） C7 站台库
第 8 天    A6 偏好映射             B6/B7 收尾               C8/C9 离线与问路卡
第 9–10 天 端到端联调 + 契约测试 + 三方实测回填
```

**三条集成切口**（每次合并只走这三个接口 + 注册表发现，避免三个人互相改对方的代码）

| 切口 | 提供方 → 消费方 | 传输方式 | 契约 |
| --- | --- | --- | --- |
| ① 行程结构 | `trip_engine` → `rules_engine` | HTTP（读注册表拿 base_url/token） | `trip.schema.json` |
| ② 规则求值 | `rules_engine` → `web_workbench` | HTTP | `rules.json`、`$defs/notice` |
| ③ 区段数据 | `route_adapter` → `rules_engine` / `web_workbench` | HTTP | `route.schema.json` |

> **Mock 替换点**：`route_adapter` 的 `config.provider`（`mock` / `amap` / `tencent` / `baidu`）**必须同签名**。切换时只改配置，不改调用方代码——这样 B 的 Rule-03 在 C10 实测前就能跑通。

---

## 4. 每天的验证回路（CI 五步）

```bash
python contracts/scripts/validate.py                  # 155 项：schema 自检 + 示例 + 时间自洽 + 方案 A 回归
python contracts/scripts/generate.py --check          # 确认 generated/ 与 schema 同步
python -m unittest discover -s modules/<你的模块>/tests -v   # 你的模块单测（不要求全链路）
python -m unittest discover -s tests -v               # 宿主自身测试（若你改了 core/）
python contracts/scripts/check_registry.py            # 注册表与 /health 连通性自检（R-3 待补）
```

**PR 模板必填五项**：
1. 改了哪个模块（`modules/<id>`）、是否改了 `manifest.json` 的 `dependencies`；
2. 改了哪个契约文件（若改了 schema，说明是加可选字段还是破坏性变更）；
3. 对应的 TC 编号（规则类改动必须引用 `TC-xx`）；
4. 是否触碰行程数据的写入（若是，必须说明写的是自己 `data_dir` 还是经 `trip_engine`）；
5. 三方调用数变化（若增加，说明缓存策略）。

---

## 5. 四个必须同步的约定（否则会互相踩）

| 约定 | 说明 |
| --- | --- |
| **字段名不许别名** | 后端返回 `arrival_at`，前端就必须用 `arrival_at`，不许在客户端重命名成 `arriveTime`。`generated/domain.ts` 是唯一命名来源 |
| **枚举不许扩展** | 需要新枚举值 → 改 `enums.json` 并升契约版本，不许在前端硬编码字符串 |
| **文案不许写死** | 规则只产出 `message_key` + `message_args`，最终文案从 `mappings.notice_templates` 取。**不允许在引擎里拼中文字符串**（多语言会崩） |
| **模块间只走 HTTP** | 不 import 别人的 Python 代码、不读别人的 `data_dir`、不反向调用上游（C7 硬约束） |

---

## 6. 开工前的最终检查清单

- [ ] 全员：`modules/trip_engine`、`modules/rules_engine`、`modules/route_adapter`、`modules/web_workbench`、`modules/offline_kit` 五个目录已建好（`manager.py` 只认 `manifest.json`，空目录会被显示为格式异常，见下方「建目录」）
- [ ] 全员：读完 `contracts/MODULE_RUNTIME.md`，能说清端口、注册表、令牌三件事
- [ ] A：能 import `contracts/generated/domain.ts`，且 TS 编译无错
- [ ] B：`RULE_TEST_CASES.md` 的 mock 数据清单已备齐（1 个周闭馆 POI + 1 个节假日例外 + 1 个亮灯 POI + 2 个同类 POI + 3 组距离耗时 + 2 段路线）
- [ ] C：`route_adapter` 的 mock 响应能通过 `route.schema.json` 校验（`data_source: "mock"`）
- [ ] 全员：`python contracts/scripts/validate.py` 本地全绿
- [ ] 全员：知道遗留决策 D-1~D-5（`contracts/DECISIONS.md`）里哪一条卡在自己手上

**建目录**（宿主不会自动创建，需手工建；已有 `modules/heartbeat` 作参考）：

```powershell
cd E:\携程
'modules\trip_engine','modules\rules_engine','modules\route_adapter','modules\web_workbench','modules\offline_kit' |
  ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
# 每个目录下放 manifest.json + plugin.py，插件接口见 README.md「开发模块」一节：
#   def run(context): context.config / context.data_dir / context.log / context.should_stop / context.wait
```

> 注意：宿主当前**没有模块间通信能力**，通道完全由模块自己实现（C7）。宿主也不会给模块分配端口——这是刻意的：模块自己占端口并登记，宿主只读注册表做健康检查展示。

---

## 7. 一句话总结

**契约已经定死了「长什么样」，手册定的是「谁先动、怎么合」。**

三个人的顺序是：**C 先出 Mock（解除全场阻塞）→ A 出行程结构 → B 用真实结构跑时序与规则 → A/C 接 B 的提示与时间轴**。任何时刻，只要遵守 §3 的三个集成切口，三个人就不需要读对方的代码。
