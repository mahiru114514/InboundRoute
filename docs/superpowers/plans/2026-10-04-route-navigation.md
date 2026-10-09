# 路线导航 Implementation Plan

**Goal:** 工作台查看当前采用路线，并显式点击高德导航。

**Architecture:** 新navigation.js封装日区间坐标解析、模式映射、链接生成、详情/轨迹预览。AmapProvider保留现有polyline与步行说明，RouteAdapter缓存对应选中方案轨迹。

**Tech Stack:** Python标准库、原生JS/SVG/CSS、Node/Edge隔离测试。

- [x] 先添加navigation.test.js和高德轨迹/缓存回归，确认缺少功能时失败。
- [x] 接通providers.py、adapter.py的polyline/步行段，遵循现有route.schema.json，不增加字段。
- [x] 实现navigation.js、接入renderRoute、静态资源版本18及响应式样式，详情折叠不发网络请求。
- [x] 隔离浏览器验证选择方式、换酒店、刷新、模拟禁用、链接参数及四视口；运行Node、路线和工作台回归、契约检查。
- [x] 只读审查，修复后重载路线/工作台，记录手机实测边界；无Git仓库不提交。
