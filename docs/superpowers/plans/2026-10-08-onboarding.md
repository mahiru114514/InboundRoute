# 新手引导 Implementation Plan

> 在当前会话按 executing-plans 执行。目录没有 Git 仓库，直接保留源码和验证记录，不创建提交或分支。

**Goal:** 实现已确认的五步、四语、可跳过和重看的行程工作台引导。

**Architecture:** 独立 onboarding.js 控制原生 dialog，localStorage 保存引导版本；不依赖业务数据或网络。页面与样式复用已有风格，文案进入现有四语字典，服务端注册静态资源。

**Tech Stack:** 原生 JavaScript、HTML、CSS、Node 内置 assert/vm、Python unittest。

## 1. 行为测试

- [x] 新建 tests/onboarding.test.js，通过 DOM 事件运行真实引导脚本，验证首次展示、幂等初始化、前后步边界、跳过/关闭持久化、重开、存储异常、最后定位与焦点、语言重绘。
- [x] 执行 `node tests/onboarding.test.js`，确认缺少引导入口导致断言失败。

## 2. 控制器与页面接线

- [x] 新建 modules/web_workbench/web/onboarding.js，公开 `window.IROnboarding.init()`；事件绑定一次，首次打开 dialog，完成或关闭时写入 `inboundroute.onboarding.seen` 的版本 `1`。
- [x] index.html 添加顶部按钮和 dialog（标题、进度、内容、提示、前后步、跳过）；所有动态节点由 textContent 更新。
- [x] app.js 在 IRLanguage.init 后、第一次 await 前调用 init；engine.py 的 ASSETS 注册 `/onboarding.js`。
- [x] 下一步末页关闭并展开 setup-disclosure，滚动、聚焦 setup-panel；关闭和 Escape 恢复入口焦点。浏览器存储异常捕获后继续交互。

## 3. 样式与四语

- [x] style.css 添加范围限定在 onboarding-dialog 的布局，正文可滚动、底部操作固定；适配窄屏和短屏。
- [x] i18n_catalog.js 加入所有引导标题、正文、提示、按钮文案；进度使用数字 `1 / 5`，语言切换不重置步骤。
- [x] 静态资源统一升到 v=34。
- [x] 运行 `node tests/onboarding.test.js`、`node tests/i18n.test.js`、`node tests/workbench_wiring.test.js`、`python -m unittest discover -s tests -p test_web_workbench.py`。

## 4. 浏览器验证与交付

- [x] 使用临时目录与独立工作台服务，避免修改用户行程。实测首次展示、五步完成、刷新与重开、四语、键盘、手机与短屏布局；保存截图到 docs/onboarding-preview。
- [x] 运行全部现有前端测试（包含新引导测试），按结果记录验证说明；源码 README 加入入口使用说明。
- [x] 更新计划状态，保存 docs/新手引导说明与验收-2026-10-08.md。
