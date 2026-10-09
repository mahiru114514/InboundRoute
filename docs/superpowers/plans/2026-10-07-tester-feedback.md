# 测试反馈 Implementation Plan

> 使用 subagent-driven-development 和 dispatching-parallel-agents 执行互不重叠的前后端任务，之后按规格、质量顺序独立审查。当前无 Git 仓库，以源码备份和验收记录交付。

**Goal:** 费用默认折叠、住宿统一搜索并支持途中休息、预算联网外币换算。

**Architecture:** 行程与费用继续按人民币整数分保存；可选 hotel_stay_kind 表示 rest/overnight。汇率网络单独后端模块，currency.js 统一换算和浏览器偏好，旧版契约及住宿保留。前端文件按原有功能职责管理。

**Tech Stack:** Python 标准库、JSON Schema 生成器、原生 JavaScript、unittest、Node VM、Playwright。

## 1. 后端与装配（主代理）

- [x] 备份源代码，使用临时目录写休息/过夜兼容与汇率测试，先观察新行为失败。
- [x] 修改 `core/trip_points.py`、`modules/trip_engine/stops.py` 和 `contracts/schemas/trip.schema.json`，新增可选停靠点用途，旧数据缺字段仍继承住宿。
  ```python
  if stop.get('stop_type') == 'hotel' and stop.get('hotel_stay_kind', 'overnight') == 'overnight':
      hotel = _endpoint(stop, 'hotel') or hotel
  ```
  测试：插入 rest 不改变下一日默认酒店；overnight 改变；重复住宿停靠不重复收费；不允许非酒店携带用途。
- [x] 新增 `modules/web_workbench/currency_rates.py`：固定白名单 URL 调用 `https://api.frankfurter.dev/v2/rate/{currency}/cny`，请求带 `User-Agent: InboundRoute/1.0`，8 秒超时、64KB 上限、6 小时内存缓存，校验日期、币种及正有限汇率；失败不返回虚构值。返回 `{currency, cny_per_unit, date, source, source_url, cached, stale}`。
- [x] `engine.py` 登记 currency.js 和鉴权 GET `/api/currency-rates?currency=USD`。测试使用可注入 opener/mock，覆盖缓存、错误、超限、鉴权与无外部 URL 输入。
- [x] HTML 登记汇率控件和费用 disclosure；全页资源 v31，构建 v15；启动在 session 后调用 `wireCurrency()`。

## 2. 住宿前端（实施代理）

- [x] 修改 `anchors.js`、`setup.js`、`day_points.js`、`day_cards.js`、`flow.js`、`app.js`，取消手填/地图点选装配；保留 hotel-search/hotel 统一搜索控件与 anchor-pick-state 简短选择提示。旧已保存酒店补入可搜资料，不偷偷改坐标。
- [x] 日卡把起终点和住宿/口岸添加收进各自 details；住宿添加有搜索、插入位置、分钟数、rest/overnight 用途和单一添加按钮。复用 addAnchorStop 的第五个可选 hotelStayKind 参数。
- [x] setup 预留 currency.js 钩子：readCurrencyBudget(value)、setCurrencyBudgetInput(cents)、currencySnapshot()、applyCurrencySnapshot(snapshot)。缺 helper 时沿用旧 CNY 行为。
- [x] 更新住宿相关 Node 用例（包括推荐与真实接线旧 harness），先红后绿，验证保存酒店恢复、任意插入及用途、查询无结果提示。

## 3. 费用与外币前端（实施代理）

- [x] 新增 currency.js 与 `tests/currency.test.js`，修改 budget_assessment.js 与预算 Node 测试。金额先用十进制字符串转换为整数分，再按正有限汇率换算并检查范围；所有服务器金额保持 CNY。
- [x] 控件 IDs：currency-select、currency-rate、currency-refresh、currency-hint；预算父 details 为 budget-disclosure，summary 为 budget-summary，内层 budget-assessment 不变。
- [x] 接口导出 wireCurrency()、readCurrencyBudget(text)、setCurrencyBudgetInput(cents)、currencySnapshot()、applyCurrencySnapshot(snapshot)、formatCurrencyMoney(cents)。币种 CNY/USD/EUR/GBP/JPY/HKD/AUD/CAD/SGD。
- [x] 默认折叠摘要显示金额、状态及缺项数。金额、余额、节省建议双币显示；费用编辑仍明确人民币。刷新/重算保留脏编辑 DOM 和展开状态。
- [x] 汇率变更/刷新不改变已保存 CNY 金额；异步响应按最新币种生效，错误保留可辨认的旧参考值或提示手填，草稿包含币种上下文。测试换算、输入无效、乱序响应、手动覆盖、草稿恢复和费用编辑保护。

## 4. 集成审查与交付

- [x] 更新真实临时服务浏览器工具，验证三块变化和旧行程；测试汇率使用独立 mock 路由，不消耗真实行情或用户数据，另只读核验一次真实参考接口。
- [x] 新鲜代理先规格审查，再质量审查；修复问题并定向复验。
- [x] `python tools/verify_project.py` 全量回归及隔离浏览器通过，生成器 --check 同步，检查 768/390/320px 无溢出。
- [x] 文档/截图/日志保存到 docs；对应工作通过后勾选。用户运行中的服务、配置、行程不改写。

