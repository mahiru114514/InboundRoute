# 上海 POI 第二批 Implementation Plan

**Goal:** 默认清单新增20个来源可追溯的上海市区与近郊POI。

**Architecture:** poi_seed.py按自身路径加载独立JSON并追加；旁路审核文件保存坐标原文与运营核对范围。未知可选字段省略，前端详情展示数据说明。

**Tech Stack:** Python、JSON、现有原生JavaScript及隔离Playwright。

- [x] 编写并执行tests/test_shanghai_poi_batch.py：先验证45条覆盖失败，再验证来源与坐标、运营真实性、默认清单和poi_path覆盖。
- [x] 创建modules/trip_engine/data/shanghai_pois_v2.json及shanghai_poi_reviews_v2.json；原始坐标反解后四舍五入6位，并用独立前向转换检查漂移。
- [x] poi_seed.py仅追加新文件；tests/test_poi_expansion.py按schema承认未采集的可选预约与精度字段，不能强迫填假值。
- [x] 抽屉数据说明通过tags展示；tests/drawer.test.js验证未知预约仍不显示无需预约，数据说明显示且用纯文本。
- [x] 执行python -X utf8 -m unittest tests.test_shanghai_poi_batch tests.test_poi_expansion tests.test_poi_crs tests.test_verified_poi_data tests.test_trip_engine tests.test_web_workbench；node tests/drawer.test.js；python contracts/scripts/validate.py；隔离浏览器tools/verify_soft_utility.cjs。
- [x] 对20条新记录执行完整POI schema校验，独立审查数据与集成；修复实际问题。
- [x] 更新验收文档，重启依赖服务使默认清单加载；只读核对45条与服务健康。项目无Git仓库，不创建提交，不写用户行程。
