# 模块化整理 Implementation Plan

**Goal:** 按业务职责拆分现有大文件，保持启动入口、HTTP 接口、行程数据格式和页面行为兼容。

**Architecture:** 沿用 `core/`、`contracts/`、`modules/<id>/` 的插件边界。行程模块内部区分领域定义、输入校验、停靠点操作、候选查询、行程服务与 HTTP 适配；工作台按功能拆分原生脚本，继续零构建，通过 HTML 的 defer 顺序装配。

**Tech Stack:** Python 标准库、原生 JavaScript、unittest、Node VM。

## 1. 建立基线

- [x] 执行 `python -m unittest discover -s tests` 和 `node tests/workbench_wiring.test.js`，记录现有结果。
- [x] 将待修改源码备份到系统临时目录；不改动用户行程、配置、注册表或日志。

## 2. 行程模块

- [x] 新建 `modules/trip_engine/domain.py`：原常量、时间转换、断言与行程事务装饰器；`errors.py` 管理领域异常。
- [x] 新建 `validation.py`：`TripValidation`，承接 `_validate_anchor`、`_validate_budget`、`_validate_cost_inputs`、`_validate_day_anchor`。
- [x] 新建 `stops.py`：`StopOperations`，承接添加、排序、移除、跨天移动以及日状态与路线失效处理；保留原事务装饰器。
- [x] 新建 `catalog.py`：`CatalogueQueries`，承接 POI 和口岸/住宿查询。
- [x] 新建 `service.py`：`TripService(TripValidation, StopOperations, CatalogueQueries)`，保留创建、预校验、查询、复制、更新和提交；由一个服务统一持有 store、时钟和锁。
- [x] 新建 `http_api.py`：原 `build_handler`、`build_server`、`serve`，只负责请求适配和服务器生命周期。
- [x] 将 `engine.py` 改为兼容导出入口；模块内部用相对导入，兼容旧脚本加载方式。修正 `store.py` 的 POI 包内导入。

## 3. 工作台模块

- [x] 提取 `modules/web_workbench/map_config.py`，承接底图配置和 CSP；`engine.py` 保留静态资源挂载与代理路由，并兼容导出原函数。
- [x] 将 `web/app.js` 按已有函数边界拆成 `runtime.js`、`services.js`、`anchors.js`、`setup.js`、`itinerary.js`、`poi_list.js`、`map_view.js`、`poi_details.js`；`app.js` 只负责启动与事件装配。
- [x] 为每个脚本声明职责与依赖，保留已有共享状态与函数签名，避免功能性改动。
- [x] 在 HTTP 挂载表与 `index.html` 中登记脚本，统一递增资源版本号。
- [x] 页面接线测试改为按 HTML 中的真实脚本顺序加载；详情和地图测试读取拆分后的文件；同步验收工具资源表。

## 4. 文档与验收

- [x] 更新两模块 `plugin.py` 的实现文件说明和包内导入。
- [x] 新增 `docs/模块化管理说明.md`，描述职责、依赖方向、新增功能位置、测试与运行数据边界；README 链接该说明。
- [x] 运行核心与三个模块的全部 Python 测试、所有前端 Node 测试、契约校验与生成同步检查、启动器 `--list`。
- [x] 检查机械搬迁的原文切片覆盖、29 个行程方法完整性、70 个前端函数重名情况与全部行为回归，避免遗漏或重复。
- [x] 将原内嵌的 25 条 POI 迁入 `data/shanghai_pois_v1.json`，搬迁时检查嵌套字段深层相等。

## 执行结果

完成情况与验证证据见 `docs/模块化整理验收-2026-10-06.md`。

## 环境说明

受限 Windows 沙箱下，Python `TemporaryDirectory` 创建的目录可能因 ACL 不可写，既有测试在整理前已出现 `PermissionError`。使用经自动审批允许的普通权限测试命令验证，不向交付代码添加环境绕行逻辑。
