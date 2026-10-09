# 每日起终点 Implementation Plan

**Goal:** 每日可独立选择起终点，交通按实际换酒店安排计算。

**Architecture:** core/trip_points.py 集中解析 Python 日地点；day_cards.js 中对应前端默认解析和选择控件。Trip PATCH 存可选对象，比较解析结果决定路线失效范围。

**Tech Stack:** Python 标准库、JSON Schema、原生 JS/CSS、Edge/Playwright。

- [x] 添加 tests/test_day_points.py、tests/test_trip_engine.py 起终点保存与继承失效测试，运行确认当前实现失败。
- [x] 实现 core/trip_points.py 的 resolve_day_points(trip)，接入 trip_engine/engine.py 和 route_adapter/service.py；扩展 trip.schema.json 和 api.schema.json，运行生成脚本。
- [x] 扩展 day_cards.js / flow.js 的起终点编辑、封面及空景点交通；style.css 加响应式地点选择，index.html 资源版本17。离线包展示起终点。
- [x] 隔离浏览器覆盖换酒店、继承、恢复默认、保存失败、路线首末点与四个视口；执行 Node、行程HTTP、路线/离线测试及契约检查。
- [x] 只读审查并处理问题；重载受影响模块，写验收记录。当前无Git仓库，不创建提交。
