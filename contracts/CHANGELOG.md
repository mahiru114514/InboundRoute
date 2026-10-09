# 契约变更日志

> 规则：任何字段增删改都要记一条。破坏性变更 → 主版本（`0.1.0` → `1.0.0`），其余 → 次/补丁版本。
> 冻结后三位开发按本文档与 `generated/` 对齐，不允许自行加字段。

## 2026-10-06 — 自动参考费用

- 新增可选 `cost_inputs.lodging_rooms`，1—100间，供自动住宿范围估算；缺省显示按1间估算。
- `lodging_nights=null` 或缺省自动跟随行程酒店与房晚；明确数组仍为用户手动房晚，空数组明确无住宿费用。
- 门票手填金额优先（包括0），空白/null沿用可用基础参考价；未知价格保持待补充。
- 派生 `budget_assessment` 增加价格来源、查询日期、住宿人数/房间数假设、特展提示及编辑器参考值；无需持久化这些派生字段。
- 更新生成的类型、模型、校验器和字段文档，兼容旧手动费用输入。

## 0.3.3 — 2026-10-04（每日起终点与换酒店）

- 新增可选 `days[].start_anchor/end_anchor`；包含类型、中英文名及带坐标系的坐标，null 或缺省恢复默认，旧行程兼容。
- 首日起点默认抵达口岸，后续默认前日终点；酒店选择成为后续默认住宿，末日终点默认离境口岸。
- 日地点修改按实际首末点变化清理交通与时间轴，包括继承变化的后续日期；实际地点不变时保留交通。
- 离线包附带每日起终点；注册表及三个独立服务版本统一为0.3.3，其余服务读注册表版本。

## 2026-10-04 — 每日出发时间实现与语义补充

- 落地既有 `PATCH days[].daily_start_local` 配置入口，无需同时传 `ordered_stops`；保持原统一字段向后兼容。
- 按天修改仅清理目标日旧交通/时间轴，保留其他日的独立设置。
- 首日起点取该日设定与抵达缓冲结束的较晚值，用户可推迟首日出发；跨零点保护保持。
- 更新schema字段说明、时间基线与对应生成产物；字段名称、类型和响应结构不变。

## 0.3.4-draft — 2026-09-29（修复「依赖重启后连不上」的启动故障）

**新增 `registry.wait_for_registration(workspace_root, module_id, timeout=30)`（向后兼容的新 API）**
- 问题（真实故障，`logs/rules_engine.log` 2026-09-29 22:52:33）：rules_engine 等到超时退出，
  日志写着等 `http://127.0.0.1:53559`，而同一时刻 `data/_registry/trip_engine.json` 里是 `53182`。
  上一轮运行遗留的注册文件指向已死端口，而 `wait_for_dependency()` 把 `base_url` 固定在
  第一次读到的值上，等待期间从不重读注册表；新实例换了端口它也不知道。
  叠加 `start_software.py` 一次性拉起全部模块（依赖方与被依赖方几乎同时启动），必然踩中。
- 约定：等待依赖时必须**每轮重读注册文件**，拿到新注册信息就用新 `base_url` + `token`；
  注册文件尚未出现时继续等待，不立刻判「未运行」。超时仍然是抛 `RegistryError`（不静默降级）。
  返回 `(最新 Registration, health 响应)`。
- `wait_for_dependency(registration, ...)` **保留不变**，但文档标注为「只适合注册信息不会变的短等待」，
  新代码请用 `wait_for_registration`。`contracts/scripts/check_runtime.py` 两者都继续校验，并新增 2 项。
- `MODULE_RUNTIME.md` §5 增加两行：等待期间重新登记、依赖中途退出后自动跟到新端口。

**新增 `registry.refresh(workspace_root, module_ids)`（新 API）**
- 常驻模块刷新上游登记信息用；返回 `{module_id: Registration | None}`，键与入参一致。
- 用于修掉同源缺陷：`route_adapter` / `offline_kit` 原来把启动那一刻的 `upstreams` 快照一直用下去，
  trip_engine 重启换端口后，它们会**永久**对着死端口——`/health` 一直 `degraded`、业务端点一直 503，
  现象是「上游明明在跑，却一直说不可用」。现在监控循环与调用路径都会先刷新。

**模块侧落地**
- `rules_engine/plugin.py`：改用 `wait_for_registration()`；`TripEngineClient` 增加可选 `resolver`，
  每次请求前重新解析上游注册信息（trip_engine 重启会换端口和令牌，抱着旧的不放会一直打已死端口）。
- `route_adapter/service.py` / `offline_kit/service.py`：新增 `upstream_ids`（固定依赖清单）+
  `_refresh_upstreams()`；监控循环每轮、每次上游调用前都重新解析注册表；
  连接失败统一按 `UPSTREAM_*` 上报，不再漏成 500。
- `start_software.py`：改为**按依赖层启动并逐层等就绪**，被依赖方就绪后再启动下一层。

**影响**：`generated/` 无变化；API 只增不改，老调用方（`wait_for_dependency`、`discover`）不受影响。

## 0.3.3-draft — 2026-09-25（A 的模块落地 + 可选依赖约定）

**开发者 A 的模块落地**（`modules/trip_engine`、`modules/web_workbench`）
- `trip_engine`：行程创建/读取/修改、POI 查询、停靠点增删改序 + `move_to_evening`；19 个集成测试。
- `web_workbench`：零构建前端（初始化看板 / 行程概览 / POI 选点与详情）+ 到引擎的代理；15 个集成测试。
- 浏览器**不接触任何引擎令牌**：页面从 `/api/session` 取工作台令牌，引擎令牌只留在代理进程内。

**C7 新增 `service.optional_dependencies`（重要修正）**
- 问题：启动器把 `manifest.dependencies` 全部当硬依赖，导致 `web_workbench`（设计上允许规则/路线引擎缺失）**根本无法启动**。
- 约定：硬依赖写 `dependencies`（缺失则拒绝启动）；可选依赖写 `service.optional_dependencies`（缺失只降级，不阻塞启动）。可选依赖若也在启动列表里，顺序仍排在被依赖方之前。
- `start_software.py`：拓扑排序与分层都读这个字段；`--list` 在依赖列显示「（可选：…）」。
- `web_workbench/manifest.json` 改为 `dependencies: ["trip_engine"]` + `optional_dependencies: ["rules_engine","route_adapter","offline_kit"]`。

**`MODULE_RUNTIME.md` §2.5** 补充两者的区别与示例。

**影响**：不涉及 `generated/` 字段；`start_software.py` 向后兼容（没有该字段的模块仍按硬依赖处理）。

## 0.3.2-draft — 2026-09-25（R-3 部分 / R-4 落地 + 启动器）

**R-4 宿主展示端口与健康状态**（改 `core/manager.py`、`web/app.js`、`web/style.css`，不涉及契约字段）
- `Manager.list()` 每个模块新增 `service` 字段：`{service, health_path, open_path, title, port, base_url, health, detail, checked_at}`；非服务模块为 `null`。
- `health` 取值：`ok`（/health 通过）/ `down`（注册了端口但探测失败）/ `starting`（运行中但尚未写注册文件）/ `no_port`。
- 探测超时 0.4s、结果缓存 2s，避免页面 3 秒轮询打满模块服务；探测失败不抛异常（一个模块卡住不影响页面）。
- **注册文件读两个位置**：`data/_registry/<id>.json`（启动器与契约 runtime 用）与 `data/<id>/registry.json`（模块自行登记用），共享目录优先。
- 管理页面模块卡片新增一行：`服务端口 51234 · /health 健康`。

**启动器 `start_software.py`**（新增，工作台侧入口，不是契约的一部分）
- 读 `config/state.json` 取已启用模块 → 按 `manifest.dependencies` 拓扑排序（检测缺依赖/循环依赖）→ 分层启动 → 对服务型模块并发轮询 `/health` → 打开主界面。
- 模式：`--list` / `--status` / `--stop` / `--all` / `--only` / `--exclude` / `--port` / `--timeout` / `--no-browser` / `--no-server`。
- 部分模块启动失败时**回收已启动的模块**；Ctrl+C 逆序停止；退出码 0/1/2/3/130。
- `start_software.bat` 双击入口。

**新增测试与文档**
- `tests/test_service_status.py`：6 个用例覆盖 service 元信息、端口解析、健康四态、探测缓存、注册文件损坏、service 字段异常。
- `MODULE_RUNTIME.md` 新增 §2.5「清单里的 `service` 约定」。
- 工作台 `README.md`：补充两个入口的分工与卡片状态说明。

**影响**：`core/manager.py` 的行为是**附加式**改动（新增字段，未改既有字段语义），旧页面忽略新字段也照常工作；`generated/` 无变化。

## 0.3.1-draft — 2026-09-25（R-1 / R-2 落地）

**R-1 后端 Python 模型生成器**（`generate.py` 新增两个产物）
- `generated/models.py`：从 schema 生成 dataclass 模型（74 KB，覆盖 Poi / Trip / Route / Station 及其 `$defs` 与**内联对象**）。
  - 全部 `@dataclass(kw_only=True)`，可按契约顺序混排必填与选填；
  - `from_dict()` 忽略未知字段（前向兼容），嵌套对象与对象数组递归构造；
  - `to_dict()` 还原 JSON 字段名、**跳过未设置的选填字段**；
  - JSON 非法标识符自动转义：`from → from_`、`zh-Hans → zh_Hans`，双向自动映射；
  - 选填字段默认值取 schema 的 `default`（如 `congestion_level="unknown"`、`crs="WGS84"`）。
- `generated/schema_store.py`：内联后的自包含 schema + `validate()` / `is_valid()`，供模块在自己进程内校验（不依赖仓库结构）。

**R-2 模块运行时公共库**（新增 `runtime/registry.py`，纯标准库）
- 端口与令牌：`resolve_port()`、`bind_socket()`、`new_token()`；
- 注册表：`read()` / `write()`（原子写）/ `remove()` / `try_read()`，字段与 C7 §2 一致，`contract_version` 取常量；
- 启动保护：`check_no_live_instance()`（探测残留注册文件的 `/health`，有响应则拒绝双实例）；
- 依赖等待：`wait_for_dependency()`（30s 上限、200ms→1s 退避，超时抛错，**不静默降级**）；
- 调用辅助：`discover()`（按依赖清单发现上游）、`call_json()`（自动带 `X-Module-Token`）。

**工具与仓库整理**
- 新增 `scripts/check_runtime.py`：42 项断言验证 R-1/R-2 产物（模型往返、别名还原、schema 校验、注册表读写、双实例保护、/health 探测、依赖超时）。
- 新增 `scripts/_bundle.py`：schema 内联与 `$defs` 打平逻辑抽出，供 `validate.py` / `generate.py` 共用；内联时**剥离 `$comment`**（否则会混进被校验的数据）。
- 目录约定固化：**运行时库 → `runtime/`，生成物 → `generated/`，共享逻辑 → `scripts/_bundle.py`**；`runtime/` 不依赖 `generated/`，反之亦然。

**CI 三步**（三者都必须绿）
```bash
python contracts/scripts/validate.py       # 155 项：契约自身
python contracts/scripts/generate.py --check
python contracts/scripts/check_runtime.py  # 42 项：生成物与运行时库
```

**影响**：无 schema 字段变更，`generated/domain.ts` 仅因枚举常量块与 `$comment` 剥离而重排；`trip/poi/station/route` 的 JSON 契约不变。

## 0.3.0-draft — 2026-09-25（C7 模块运行时：方案一）

**背景**：宿主「模块工作台」的隔离机制是「每模块独立进程 + 模块间无法互相调用」，而 InboundRoute 的三个引擎必须互相调用。决策：**模块自己暴露本地 HTTP，宿主只管生命周期**（方案一）。

**新增契约 `MODULE_RUNTIME.md`（C7）**
- 职责边界：宿主只管生命周期、不转发业务请求、不分配端口；模块间**只能走 HTTP**（禁止 import 别人的代码、禁止读写别人的 `data_dir`）。
- 端口与注册表：模块自己占端口（`config.port` 或 `0` 自动分配），启动成功后写 `<root>/data/_registry/<module_id>.json`，格式固定（含 `token`、`contract_version`、`endpoints`）；退出时删除；残留注册文件先探测 `/health` 再决定覆盖或报错。
- 端点约定：所有服务型模块必须实现 `GET /health`（免令牌）；业务端点清单与 `schemas/api.schema.json` 对齐。
- 鉴权：除 `/health` 外必须带 `X-Module-Token`；令牌是**各模块启动时随机生成并登记在注册表**，不进 `context.config`（配置会被页面展示）。
- 调用方向：恒为下游 → 上游；宿主只调 `/health` 做状态展示。
- 启动与失败：依赖未就绪轮询 `/health`（最长 30s，200ms→1s 退避）；依赖中途退出时 `/health` 置 `degraded`（`upstream_down`）+ 业务端点 503 + `UPSTREAM_*`，**不自动重启依赖**。
- 契约副本：模块依赖 `scripts/generate.py` 的生成物，不读仓库根目录的 schema 原件（打包分发时不存在）。
- 待补项 R-1~R-4：Python 模型生成器、注册表读写工具、Mock 同签名验证脚本、宿主显示端口与健康状态。
  - **R-1 已完成**（见 0.3.1）；**R-2 已完成**（见 0.3.1）；R-3（Mock 同签名验证脚本）、R-4（宿主显示端口与状态）仍待做。

**五个宿主模块与三个人的对应**（新增，见 `../InboundRoute_模块化开发执行手册.md` §0）
`trip_engine`(A) → `rules_engine`(B) / `route_adapter`(C) → `web_workbench`(A) / `offline_kit`(C)

**文档更新**
- 三份 `devdocs/开发者{A,B,C}-开发需求文档.md` 全部重写为**模块视角**：新增「你的代码怎么跑起来」（manifest / 端口 / 注册表 / 令牌 / 依赖等待）、模块层验收清单、模块骨架提示词（提示词 0）、单模块测试命令。
- `../InboundRoute_模块化开发执行手册.md` 更新：新增 §0 五个模块与三人的对应、通信纪律；工作包表增加「归属模块」列与 A0/B0/C1 模块骨架；集成切口改为走注册表发现；CI 五步与 PR 模板五项；新增建目录命令。

**影响**：`generated/` 无字段变化（C7 是运行时约定，不改数据模型）；`scripts/validate.py` 155 项仍全通过。

## 0.2.0-draft — 2026-09-25（C3 软规则决策：方案 A）

**决策**：软规则**不自动改行程顺序**，改单必须由用户显式触发（方案 A）。备选方案与代价分析存档在 `SOFT_RULE_DECISION.md`。

**`rules.json` 变更**
- `execution_model.iteration_policy` 重写：新增 `auto_apply_soft_rules: false`、`order_mutation_allowed` 白名单（仅用户操作）、`engine_mutation: 禁止`、`max_iterations: 1`。
- 新增 `execution_model.soft_rule_decision`（记录决策、时间、被否决方案及理由）。
- `rule_02_lightup.branches[too_early].on_action.move_to_evening` 细化：
  - 新增 `trigger: "user"`（明确该动作只能由用户触发）；
  - 新增 `last_position_definition`：**「末位」= 当日最后一个未锁定位置**，末尾连续 `locked` 的点不动，新位置插在其之前；
  - 新增 `records_revision: "move_to_evening"`；
  - 新增 **`on_still_failing`** 分支：移动后仍早于 `T_light` 时 → 移动生效 + 保留提示 + 文案换 `rule.lightup.still_early` + 不再提供该动作（避免无效点击）。
- `notice_message_keys` 新增 `rule.lightup.still_early`。
- `ac_matrix.rule_02_lightup` 新增 4 条：AC-R2-04（软规则不改单）、AC-R2-05（末位与 locked）、AC-R2-06（移动后仍不满足）、AC-R2-07（改期后提示失效）。

**`mappings.json` 变更**
- `notice_templates` 新增 `rule.lightup.still_early`（中英双语，含 `{arrival_local}` 插值）。

**新增文档**
- `SOFT_RULE_DECISION.md`：三方案对比、外滩实例推演、不收敛场景分析（决策存档）。
- `RULE_TEST_CASES.md`：35 条 GWT 用例（Rule-01~04 各 9/10/6/5 条 + 跨规则 7 条），B 可直接照着写测试；含伪代码骨架与 mock 数据清单。

**`DECISIONS.md` 变更**
- C3「软规则是否改排序」「迭代上限」「移动后仍不满足」「末位定义」四项转为 ✅ 已冻结。
- 新增「遗留待决策项」表（D-1~D-5，均不阻塞开工）。

**影响**：`generated/` 无字段变化；`scripts/validate.py` 新增 `still_early` 文案键与 AC 完整性检查。

## 0.1.1-draft — 2026-09-25（决策确认）

**已冻结（人工确认）**
- **C1 时区：一律 `Asia/Shanghai`（北京时间，UTC+8）**。客户端本地时区只影响自身显示格式化，不得用于任何规则判定。`trip.timezone` 在 schema 中为 `const`，写错即校验失败。
- **C1 时间类型**：`*_at`=UTC 秒 / `date`=上海本地日期 / `*_local`=同日时刻；`days[].daily_start_local` 新增；跨零点两条裁决。
- **C2 星期编号：ISO 8601（1=周一 … 7=周日）**。`enums.json#/weekday` 已标注冻结理由。
- **C5 CRS 责任、C4 鉴权与三方 key 服务端代理**：维持既定（用户确认无异议）。

**待决策**
- **C3 软规则是否自动改行程顺序**：新增决策简报 `SOFT_RULE_DECISION.md`（方案 A 只提示 / B 自动改单 / C 仅换提示顺序），决策前 `rules.json` 维持方案 A 草案。影响面已在简报 §5 列出。

**影响**
- `generated/README.md` 与 `generated/domain.ts` 无需变更（本次为语义冻结，无字段增删）。
- `scripts/validate.py`：148 项检查仍全通过。

## 0.1.0-draft — 2026-09-25（首次建立）

**建立**：契约包骨架（JSON Schema + 枚举 + 规则表 + 映射表 + 错误码 + 校验器 + 生成器 + 示例）。

### C1 时间基准（新增文件 `TIME_BASELINE.md`）
- 冻结时区为 `Asia/Shanghai`；定义 `*_at`（UTC 秒）/ `date`（本地日期）/ `*_local`（同日时刻）三种类型。
- 新增 `days[].daily_start_local`，解决 Day 2..N 时间轴断链。
- 定义跨零点三条裁决。

### C2 实体字段表（相对 PRD 4.1/4.2 的改动）
- `POIMaster`：`name_en/name_zh/name_pinyin` → `names{}` + `romanization{}`（含 `pinyin_plain`）；`category`/`sub_category` → 三级 `category` 对象；`suggested_drop_off_coordinate` → `drop_off_locations[]`；`standard_opening_hours` → `opening_hours[]`；`closure_days` → `closure_rules[]` + `closure_data_status`；`light_up_required`+`light_up_schedule{summer,winter}` → `light_up{required, T_light_rule, windows[]}`；`suggested_dwell_minutes` → `dwell_time{kind, minutes|min,max}`。新增 `reservation_required`、`advance_booking_days`、`provider_refs`、`provenance`。
- `TripInstance`：`timestamp` → `arrival_at`；新增 `user_id`、`version`、`status`、`created_at`、`updated_at`、`anchor_departure`、`unassigned_pois`、`revision_history`；`days[]` 新增 `day_status`、`daily_start_local`、`poi_cap`；`ordered_stops[]` 新增 `stop_type`、`locked`、`arrival_at`、`departure_at`、`rule_notices`，`target_arrival_time` 拆为 `arrival_at` + `user_preferred_arrival_local`；`user_profile` 新增 `party_walk_multiplier`、`prefer_taxi`、`interests`。
- **新增实体** `CuratedStation`（`schemas/station.schema.json`）：PRD 架构图提到但第 4 章缺失，3.5/3.6/3.7 都依赖它。

### C3 规则执行规范（新增 `rules.json`）
- 以正文 4 条规则为准，**作废 PRD 3.3 的流程图**（只有 3 个框、编号错位）。
- 定义执行顺序：时序推演 → 硬规则 → 软规则并行 → 汇总渲染；软规则不改排序。
- 定义循环依赖处理：最大迭代 3 次，不收敛保留用户操作。
- 补 Rule-01 缺失数据策略（`unknown` 不得静默放行）、Rule-02 对称分支（到得太晚）、Rule-03 双条件与城市参数、Rule-04 分类字典依赖与文案插值。
- 为 4 条规则建立 AC 用例骨架（9 条）。

### C4 API 契约（新增 `schemas/api.schema.json`、`errors.json`）
- 14 个端点、统一响应信封、13 个错误码、幂等键、Schema 版本兼容策略、限流与埋点要求。

### C5 Route Adapter 归一化（新增 `schemas/route.schema.json`）
- `transit_from_previous` 的 5 个标量 → 完整 `RouteSegment`：新增距离/步行/步数/费用区间/拥堵/`variants[]`/`segments[]`/`drop_off`/降级标记。
- 定义 CRS 转换责任与幂等的 30% 上浮表达。

### C6 三方能力实测（新增 `mappings.json#/provider_field_map`）
- 列出三方已知可得字段与必须来自站台库的字段；实测结论待回填。

### 工具
- `scripts/validate.py`：148 项检查（schema 自检、示例校验、时间自洽、契约自洽、非法样例回归）。
- `scripts/generate.py`：从 schema 生成 `generated/domain.ts` 与 `generated/README.md`（字段表）。
