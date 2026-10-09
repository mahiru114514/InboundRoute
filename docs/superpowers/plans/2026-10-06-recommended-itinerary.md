# 推荐行程 Implementation Plan

**Goal:** 用户填写住宿和出入境资料，按兴趣、节奏及指定日期一键生成可继续编辑的上海游玩行程。

**Architecture:** recommendation_engine 只通过本地 HTTP 读取 trip_engine，返回可解释的纯规划结果；trip_engine 负责原子创建或补空白日，web_workbench 代理并装配页面交互。闭馆日期判定提取到 core 的纯函数供两个模块复用。

**Tech Stack:** Python 标准库、原生 JavaScript、现有插件注册表、unittest 和 Node VM。当前目录无 Git，不创建分支或提交。

## 固定接口

```text
POST /trips:preview                 body=原创建设定；返回 Trip，绝不保存
POST /trips:recommended             body={setup, plan}；返回保存后的 Trip
POST /trips/{id}/recommendations:apply  body={plan}；必须 If-Match；返回 Trip
POST /recommendations:generate      body={trip_id 或 setup, day_indices}；返回 Recommendation
```

`plan = {days: [{day_index: 整数, stops: [{poi_id, planned_dwell_minutes}]}]}`。
`Recommendation = {plan, days, skipped_days, warnings, trip_id, trip_version}`。
`days` 中每项带 day_index、date、stops；每个建议点带 poi_id、name_zh、planned_dwell_minutes、reasons、warnings，可附估算的 local 时间但不得写成真实交通。
`skipped_days = [{day_index, reason}]`，记录已有安排或候选不足的天。
新请求恰好提供 trip_id 或 setup 之一。新建计算用 preview 骨架；已存在的行程返回读取时的版本。选中日必须为有效、不重复的整数；不自动扩展选中范围。

浏览器走对应 `/api/...` 路径。已有行程的生成使用已保存设定；若表单存在未保存更改，先提示保存，推荐操作本身不预先改写设定。

## Task 1：推荐计算和服务

Files: `modules/recommendation_engine/{planner,client,service,http_api,plugin}.py`、`manifest.json`、模块 `tests/`；`core/poi_availability.py`、`modules/rules_engine/rules.py`。

- [x] 先写真实规划测试，使用周闭、开放例外、不同兴趣/节奏、远近景点、已有锁定点和日期边界，验证缺失实现失败。
- [x] 实现纯函数 `generate_plan(trip, pois, day_indices)`；不修改输入，基于酒店/每日锚点进行地理和时间约束排序，过滤日期明确不适合的景点，同一行程不重复推荐。
- [x] 复用共享闭馆判定，保留数据核验提示；开放时段、停留、交通/休息估算作为初筛，候选不足明确返回原因。
- [x] 新建独立插件，依赖 trip_engine，注册 health 和只读生成端点；客户端按请求重读注册表。
- [x] 用真实 HTTP 测试鉴权、预览/已有行程输入、健康状态和服务降级；运行模块测试。

## Task 2：原子写入与契约

Files: `modules/trip_engine/recommendations.py`、`service.py`、`http_api.py`、`plugin.py`，`tests/test_recommendation_apply.py`，`contracts/schemas/api.schema.json`、推荐请求/计划/响应 schema。

- [x] 写失败测试：有效方案一次落盘、无效末尾 POI 整体不写、版本冲突、已有点/跨天重复、非法日期/时长、全部为空和新建失败不留空壳。
- [x] 实现 `preview_trip`、`create_recommended_trip`、`apply_recommendations`；应用前先完整校验，持有同一行程锁，使用原 stop 结构和 ID，一次保存并递增一次版本。
- [x] 必须校验 If-Match；不覆盖任何已安排/锁定点，停止点默认为可编辑。路线与离线结果按原修改逻辑失效。
- [x] 登记契约和端点，不随意改变 trip schema 的持久化字段；重新生成产物并校验同步。

## Task 3：工作台代理和页面

Files: `modules/web_workbench/{engine,proxy}.py`、`manifest.json`、`web/{recommendations,anchors,setup,app,itinerary,services}.js`、`index.html`、`style.css`、`tests/recommendations.test.js`、页面接线测试。

- [x] 新接口代理、POST If-Match 转发、推荐模块可选依赖与状态展示；真实代理测试先失败再实现。
- [x] 添加推荐日期选择，默认 2..N-1；1～2 天提示用户选择。推荐按钮显示模块就绪/进度/错误，重复点击只提交一次。
- [x] 新建流程先推荐，再原子保存完整结果；已有流程只补空白日，传入计算时版本，失败不改变当前行程。
- [x] 生成后刷新现有行程/历史/规则界面，显示简短理由和缺少资料提示；仍可使用所有编辑功能。
- [x] 支持自己的住宿名称及地图位置，保留候选住宿使用方式，并纳入草稿和设定回填。
- [x] 按实际 HTML 顺序加载新脚本并统一递增资源版本；前端行为测试和既有 wiring 通过。

## Task 4：集成、审查和交付

- [x] 用真实 trip_engine、recommendation_engine 与工作台跑新建/已有行程生成链路；检查生成失败/缺模块/版本冲突不留下半份数据。
- [x] 独立审查规格一致性和代码质量，修复发现的问题。
- [x] 更新 README、模块职责文档与统一验证工具，将新模块测试纳入完整回归。
- [x] 运行完整 Python/JS/契约/运行时/启动器验证；不改写用户 config/data，不自动重启用户正在运行的模块。
- [x] 写明入口与使用方法、验证结果、交通估算和数据核验边界。

