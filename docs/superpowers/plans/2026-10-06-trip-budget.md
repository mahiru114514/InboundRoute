# 每人预算 Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task in this session.

**Goal:** 在行程设定增加人民币每人整趟预算，支持完整保存与回填。

**Architecture:** TripInstance.budget 保存 scope=per_person、currency=CNY、amount_cents；空白存 null。前端元字符串转换成整数分。预算单独更新不影响交通。

**Tech Stack:** Python 标准库 HTTP、原生 JavaScript、JSON Schema、unittest、Node VM。

当前工作目录不是 Git 仓库；直接在现有工作目录执行，无提交或 worktree 操作。

## 1. 后端与契约

- [x] 在 tests/test_budget.py 写创建、读取、复制、更新、清空、非法类型/金额及保留交通的失败用例。
- [x] 运行 `python -m unittest tests.test_budget -q` 确认旧代码未保存预算。
- [x] modules/trip_engine/engine.py 加 `_validate_budget`，创建时设置 `budget`，PATCH 时更新该字段，单独 budget 更新跳过交通失效。
- [x] contracts/schemas/trip.schema.json 增加可空 budget 对象与整数分范围，重新生成契约。
- [x] 重跑后端预算用例。

## 2. 工作台

- [x] tests/workbench_wiring.test.js 增加输入、元分转换、保存/回填/清空、草稿和概览的失败断言。
- [x] modules/web_workbench/web/index.html 加 optional number 输入，每人预算（元），min=0，step=0.01。
- [x] app.js 的 readSetup、formFromTrip、formSnapshot、applyDraft、renderTrip、saveSettings 接入预算。校验十进制最多两位小数；只改变预算时仅 PATCH budget，保留路线缓存。元分转换示例：12.34 -> 1234，0 -> 0，空白 -> null。
- [x] 更新静态资源版本并运行所有 JS 回归。

## 3. 完成验证

- [x] 运行行程引擎、预算与工作台 HTTP 测试，契约 generate --check 与 validate。
- [x] 自查旧行程空值兼容、清空后的回填与仅预算更新的交通保持；记录最终结果。

最终结果：62 项行程/预算/锚点/每日起终点 Python 测试、8 项 HTTP 贯通测试、12 组 JS 测试通过；页面接线 119 条断言通过；契约同步检查通过，163 项契约校验通过。静态资源版本 23。
