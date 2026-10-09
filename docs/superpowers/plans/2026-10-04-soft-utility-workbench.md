# Soft Utility Workbench Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task in the current session. Steps use checkbox syntax for tracking. 用户已经批准视觉方案；无需再次确认执行方式。

**Goal:** 将游客行程工作台适配为已批准的柔和工具风，并验证已有操作及手机布局。

**Architecture:** 保留原生 HTML/CSS/JS 和全部事件 ID。主页面增加语义化工作区导航，隐藏工作区的导航同步隐藏，避免跳转到不可见目标。现有保存按钮保持在原表单里，通过响应式 CSS 固定到手机底部。

**Tech Stack:** 原生 HTML、CSS，现有 Node 回归测试，Python unittest，Playwright 隔离浏览器验收。

---

### Task 1: 页面结构与文案

**Files:** 修改 `modules/web_workbench/web/index.html`、`app.js`（中文服务名称）与 `flow.js`（历史说明同步）。

- [x] 保留脚本顺序和 ID；全部静态资源版本改为 11。
- [x] 顶部使用 h1，新增导航链接及跳转入口：

```html
<nav class="workspace-nav" aria-label="工作区导航">
  <a href="#setup-panel">01 行程设定</a>
  <a href="#trip-panel">02 行程概览</a>
  <a href="#poi-panel">03 挑选景点</a>
  <a href="#rules-panel">04 时间校验</a>
  <a href="#route-panel">05 区间交通</a>
  <a href="#offline-panel">06 离线问路</a>
</nav>
<a class="back-top" href="#top" aria-label="返回顶部">↑ 返回顶部</a>
```

- [x] 面板添加 `tabindex="-1"`，顶部添加 `id="top"`；对搜索分类补充可访问名称；简化面板说明，保持真实数据和缺失状态说明。
- [x] 服务条使用中文功能名称；`refreshHistory()` 每次更新 `history-hint` 的数量说明。隔离浏览器先验证新建后提示未同步，再把更新逻辑从 `restoreHistory()` 移入 `refreshHistory()` 并验证通过。

### Task 2: 视觉与响应式

**Files:** 修改 `modules/web_workbench/web/style.css`。

- [x] 使用 `--ink:#203b40; --paper:#f4f8f6; --teal:#2d5b63`。浅色成功、提醒、错误、选中背景分别为 `#a9d8cc/#f3c98b/#e6b7b0/#b8c9ed`，全部配深色正文。
- [x] 统一工作区 16px、控件 12px 圆角；浅边界与微弱阴影；文字 14–16px，提示不小于 12px；日程、规则、路线使用条目分隔，保留景点横向列表。
- [x] 焦点采用可见双层边界，浏览器 `:user-invalid/:user-valid` 显示输入错误/完成；禁用控件采用清晰背景及深色文字。
- [x] 导航按目标可见性同步隐藏：

```css
body:has(#trip-panel[hidden]) .workspace-nav a[href="#trip-panel"] { display:none; }
@media (max-width:600px) {
  .form-actions { position:fixed; inset:auto 0 0; padding:12px 16px calc(12px + env(safe-area-inset-bottom)); }
  main { padding-bottom:130px; }
}
@media (prefers-reduced-motion:reduce) {
  html { scroll-behavior:auto; }
  button,input,select,a { transition:none; }
}
```

- [x] 同样覆盖其他隐藏面板；地图图钉保留原有 transform；按下缩放只作用于常规行动按钮，避免地图坐标错位。
- [x] 返回顶部与 toast 留出手机底栏空间；弹窗关闭和加入操作始终可见。

### Task 3: 验证与交付

**Files:** 创建 `tools/verify_soft_utility.cjs` 及 `docs/柔和工具风改造验收-2026-10-04.md`；截图保存 `docs/验收截图/soft-utility-*.png`。

- [x] 执行全部既有前端回归：

```powershell
node tests/workbench_wiring.test.js
node tests/flow.test.js
node tests/drawer.test.js
node tests/map_states.test.js
node tests/map_dom.test.js
node tests/offline_cache.test.js
python -X utf8 -m unittest discover -s tests -p test_web_workbench.py
python -X utf8 -m unittest discover -s tests -p test_workbench_flow.py
```

期望各命令退出码 0。

- [x] Playwright 以 localhost 独立静态服务器运行当前页面；拦截 API 为内存演示数据，不连接真实路线服务或改写现有行程。检查 1440、768、390、320px 下 document 宽度、离境与每日出发无交叠、导航显隐、键盘焦点、表单原生校验、保存新建/更新、筛选、景点弹窗、交通、离线预览。
- [x] 验证减少动态效果与关键文字对比度；输出桌面及手机截图，验收文档记录测试结果和演示数据限制。
- [x] 更新设计状态及实施复选框。目录没有 Git 仓库，本次直接交付工作区文件，不建立 Git 分支或提交。

**Self-review:** 对应设计所有区块；不引入新框架、API、真实图片或运营数据；无待填占位项。新导航和底栏在真实浏览器中验收，既有回归覆盖事件接线。

