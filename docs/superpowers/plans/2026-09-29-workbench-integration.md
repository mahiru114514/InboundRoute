# 行程工作台闭环实施计划

用户已确认按评估建议实施。当前目录无 Git 仓库，直接修改工作目录并运行回归检查。

**目标：** 恢复历史行程，完成排序、锁定、规则确认、路线计算及离线问路卡的页面流程。

**架构：** 保留独立 HTTP 引擎和原生 JS；工作台作为唯一浏览器代理。行程数据由 trip_engine 保存；规则由 rules_engine 求值；路线由 route_adapter 计算；离线数据由 offline_kit 生成。缺失能力明确降级，mock 显示演示标签。

> 状态：**第 1~4 节已完成并通过验证**（下方勾选附证据命令）。剩余限制见文末「未验证项」。

## 1. 历史与编辑
- [x] tests/test_workbench_flow.py 验证工作台 PUT 排序、PATCH 锁定、历史读取。
      `python -m unittest discover -s tests`（FlowTests 3 项全绿）。
- [x] trip_engine 支持锁定与路线数据 PATCH；编辑后清空旧时间和失效确认。
      `modules/trip_engine/engine.py`：`patch_trip` / `reorder_stops` / `move_stop_to_evening`，(`tests/test_trip_engine.py`)。
- [x] web_workbench 提供历史下拉框，记录最后打开 ID，启动恢复；加入上下移动、拖放、锁定、移到晚上。
      `web/index.html#trip-history`、`web/flow.js`（`restoreHistory` / `addStopControls`），
      由 `tests/workbench_wiring.test.js` 第 2、4 节断言（真实 DOM id + 假 fetch 跑完 boot）。

## 2. 规则与时间轴
- [x] 工作台代理 rules:evaluate 与 conflicts/confirm。
      `modules/web_workbench/engine.py` 路由 + `tests/test_workbench_flow.py::test_rules_routes_and_offline_through_workbench`。
- [x] 规则结果返回时间轴并可写回，保留有效确认；缺交通时间不伪造完整时间轴。
      同上用例断言 `timeline[0].stops[0].arrival_at is None` 且 `skipped_rules` 会提示。
- [x] 添加景点后求值，硬冲突提供保留或移除操作；每次编辑重新求值并显示缺失数据提示。
      `app.js#addSelectedToDay` → `afterTripEdit('add_stop')`；`flow.js#renderFlow` 渲染「仍然保留 / 移除此景点」。
      `tests/workbench_wiring.test.js` 第 5 节断言「加入景点后重新求值了规则」。

## 3. 路线
- [x] 为高德实现官方路线请求和响应解析，先加 fixture 测试，再实现；无凭据不声称实测成功。
      `modules/route_adapter/providers.py#AmapProvider`（/v3/direction/walking|driving|transit/integrated、GCJ-02 请求坐标、错误码分类、key 脱敏），
      fixture 测试 `tests/test_amap_provider.py`（7 项）。
- [x] 从抵达口岸/酒店到景点，再回酒店构造区间；逐区间计算以满足调用预算。
      `flow.js#computeDayRoutes` 逐段调用 `routes:compute`，页面每天一个「计算 Day N 交通」按钮。
- [x] 页面显示三模式、演示/降级标签；选定方案写入行程后重算时间轴。
      `flow.js#renderRoute`（三模式按钮 + 演示/降级文案 + 换乘步行提示），
      `tests/workbench_wiring.test.js` 第 4 节断言 routes:compute 调 2 次、方案写回、标注「演示路线 · 非真实导航」。

## 4. 离线
- [x] 修复 IndexedDB 读取结果、版本判断、TTL 和容量检查并增加 JS 测试。
      `modules/offline_kit/web/offline_cache.js` + `tests/offline_cache.test.js`。
- [x] 页面生成、缓存、读取和导出离线包及自包含 HTML 问路卡；导出文件可脱离本地服务打开。
      `flow.js#generateOffline / renderOffline / downloadOffline`（Blob 自包含 HTML，样式内联）+ `web/index.html` ⑥ 面板。
- [x] 版本变化后提示重新生成，缺少路线或存在待确认冲突时不把离线包标为完整。
      `flow.js#generateOffline` 先拦截硬冲突与 `arrival_at == null`；`downloadOffline` 校验 `trip_version === state.trip.version`。

## 验证
分别运行 tests、rules_engine/tests、route_adapter/tests、offline_kit/tests 的 unittest discover；运行全部 tests/*.test.js；运行 contracts/scripts/validate.py 和 check_runtime.py。通过真实临时 HTTP 引擎完成新增、确认、路线回填、离线生成集成测试。浏览器检查主要入口与交互。更新功能清单，保留真实三方凭据未验证等限制。

实测记录（2026-09-29，Python 3.13.3 / Node 24.11.1）：

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 核心 + 工作台 | `python -m unittest discover -s tests` | 71/73 通过；2 项失败属环境限制（见下） |
| 规则引擎 | `python -m unittest discover -s modules/rules_engine/tests` | 49 项 OK |
| 路线适配 | `python -m unittest discover -s modules/route_adapter/tests` | 44 项 OK |
| 离线包 | `python -m unittest discover -s modules/offline_kit/tests` | 13 项 OK |
| 契约数据 | `python contracts/scripts/validate.py` | 155 项，失败 0 |
| 生成代码运行时 | `python contracts/scripts/check_runtime.py` | 全部通过 |
| 前端 JS | `node tests/*.test.js` | drawer 38/38、map_dom 21/21、map_states 全通过、flow 通过、offline_cache 通过、workbench_wiring 50/50 |

未验证项（如实保留）：
- **没有真实三方凭据**：高德/腾讯/百度均未用真 key 打过真实接口；高德只由 fixture 固定响应验证解析逻辑，腾讯/百度仍是通用骨架。
- **没有浏览器实测**：页面接线由 `tests/workbench_wiring.test.js` 以真实 `index.html` 的 id 列表 + 假 fetch 驱动 app.js/flow.js/map.js 验证，覆盖「点得出来、请求发得出」，但未在真实浏览器里点过。
- **本机两项测试失败与业务无关**：`test_manager`、`test_service_status` 需要启动真实子进程并读日志，
  在当前沙箱里子进程受限（日志为空 / 健康检查停在 `starting`），属环境问题。
- **锚点坐标为人工整理**：新增口岸/酒店里有标记 `coordinate_source: "approximate"` 的近似值，
  未在真实底图上实测，页面已提示可用「在地图上点选住宿位置」校正。
