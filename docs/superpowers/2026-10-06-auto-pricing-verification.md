# 自动参考计费验证

- 新增自动价格测试先红后绿：初次运行5个断言失败、2个缺失功能错误；现10项通过。
- 前端自动模式保存测试初次失败（保存为[]，冻结房晚），实现后通过。
- 完整相关Python回归：119项通过。命令使用项目根目录及tests目录的PYTHONPATH，运行test_auto_pricing、test_budget_assessment、test_budget、test_trip_engine、test_day_points、test_anchor_stops、test_web_workbench、test_workbench_flow、test_offline_timeline。
- tests/*.test.js共13组通过，含119项workbench接线断言和自动计费UI交互。
- contracts/scripts/validate.py：166项通过；generate.py --check生成物同步。
- 独立只读代码审查未发现阻碍交付的重要问题；额外运行20项预算/自动计费Python测试及前端预算测试通过。

覆盖：景点增删、重复停靠、日期价格、特展提示、酒店继承、不重复按停靠收费、实际人数房间分摊、手填0、自动保存重载、切换手动、错误坐标及未知酒店处理、来源链接和脏编辑保留。

当前目录无Git，未提交。参考价格不代表实时可订报价；未知的酒店实体和景点价格仍需用户补充。模块不支持Python热更新，运行中的软件需重启模块并刷新页面加载静态资源v25。
