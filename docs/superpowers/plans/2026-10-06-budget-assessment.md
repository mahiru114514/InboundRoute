# 人均费用评估 Implementation Plan

**Goal:** 分类汇总当前行程全部人均费用，与每人预算比较并给出有依据的调整建议。

**Architecture:** core/budget_assessment.py 校验 cost_inputs 并统一生成只读 budget_assessment。TripStore 返回行程时派生评估，派生结果不落盘。每天 end_transit 保存最后一区段。独立 budget_assessment.js 展示评估与可展开的费用设置，保存时只更新费用参数。

**Tech Stack:** Python、原生 JavaScript、JSON Schema、unittest、Node VM。

在现有非 Git 工作目录执行，不创建分支或提交。

- [x] 新增 tests/test_budget_assessment.py：共享费用、重复门票、返程、缺失/零元、模拟费用、区间比较、外币与未知币种、保存与失效。
- [x] 验证失败用例后实现 core/budget_assessment.py，统一金额、区间、分类、建议及预算判断。
- [x] cost_inputs 创建/PATCH 校验，费用更新保留交通，Store 动态派生评估，结构变化要求核对。
- [x] day.end_transit 保存、失效、计算及切换保存、刷新恢复及导航读取。
- [x] 费用 UI 和临时 HTTP 贯通测试，覆盖保存、刷新、缺失提示、路线保持及后台刷新保留未保存输入。
- [x] 完成各项费用输入、实际房晚增删、来源明细与调整建议。
- [x] 更新挂载表、静态版本 v24、Trip/API 契约，重新生成产物。
- [x] 回归及独立代码审查完成，验证记录见 ../specs/2026-10-06-budget-assessment-verification.md。
