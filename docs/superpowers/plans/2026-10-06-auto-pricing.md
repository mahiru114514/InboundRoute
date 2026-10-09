# Automatic pricing Implementation Plan

**Goal:** 已选景点和酒店自动进入人均预算，保留手填优先、价格范围与来源。

**Architecture:** core/reference_prices.py读取价格快照并匹配实体，core/budget_assessment.py派生费用。预算编辑器以空白表示沿用自动价格，自动房晚不写入固定房晚列表。

**Tech Stack:** Python unittest，原生JS，JSON Schema。

- [x] 新增tests/test_auto_pricing.py，先验证缺少自动景点/酒店费用的失败；覆盖日期、特展、移除、继承、分摊与手填优先。
- [x] 新建core/reference_prices.py；修改预算评估，增加自动票价与房晚、来源、假设和提示。
- [x] 扩展cost_inputs.lodging_rooms及相关契约并运行生成工具；保持旧手动房晚兼容。
- [x] 增加前端回归测试后修改预算编辑器，显示自动参考价格、来源链接、住宿自动/手动切换；升级静态资源版本。
- [x] 运行预算和行程相关Python测试、JS回归、契约验证，记录结果。当前目录无Git，不创建提交或工作树。
