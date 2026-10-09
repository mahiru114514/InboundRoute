# POI 简介 Implementation Plan

> **For agentic workers:** Use subagent-driven-development for focused UI implementation and independent specification/quality review. 当前没有 Git 仓库，不提交或创建分支。

**Goal:** 45 个上海景点都有简短介绍，用户在推荐结果及每日行程中可据此删改。

**Architecture:** 在原有 POI JSON 加入可选 description_zh；GET /pois 直接交付。独立 poi_content.js 共用读取及兜底函数，四个现有页面模块调用，持久化行程及推荐接口保持原格式。

**Tech Stack:** Python 标准库、JSON Schema 与生成器、原生 JavaScript、unittest、Node VM、现有 Playwright 隔离验收工具。

## Task 1：数据及契约（主代理）

Files: `tests/test_poi_introductions.py`，`modules/trip_engine/data/shanghai_pois_v{1,2}.json`，`modules/trip_engine/data/poi_description_reviews.json`，`contracts/schemas/poi.schema.json`、生成产物。

- [x] 先写数据覆盖/真实 HTTP/旧数据兼容/模型往返测试，运行 `python -m unittest tests.test_poi_introductions` 观察缺 description_zh 的失败。
  ```python
  self.assertEqual(len(POIS), 45)
  for poi in POIS:
      self.assertTrue(poi.get('description_zh', '').strip(), poi['poi_id'])
      self.assertLessEqual(len(poi['description_zh']), 120)
  ```
- [x] 核对政府、场馆官网及现有审核资料，编写主要看点及参观方式。更新 JSON 字段，不改任何原字段；按 poi_id 记录事实来源与编辑建议边界。
- [x] 契约追加 `"description_zh": {"type":"string","minLength":1,"maxLength":120}`，保持可选；运行 `python contracts/scripts/generate.py`，数据/模型测试应通过，`--check` 无差异。

## Task 2：前端四处展示（实施代理）

Files: `modules/web_workbench/web/poi_content.js`、`poi_list.js`、`poi_details.js`、`day_cards.js`、`recommendations.js`、`index.html`、`style.css`、`runtime.js`；后端 `engine.py` 仅新增 ASSETS；`tests/poi_introductions.test.js` 和必要既有 harness。

- [x] 先写 Node 行为测试，运行 `node tests/poi_introductions.test.js`，观察缺介绍展示的失败。
- [x] 新脚本共用纯函数：
  ```javascript
  function poiIntroduction(poi) {
    const text = typeof poi?.description_zh === 'string' ? poi.description_zh.trim() : '';
    return text || '简介待补充';
  }
  ```
  列表与详情用直接 POI；日卡和推荐结果用 poi_id 匹配 state.pois。住宿/口岸停靠点不添加景点简介。
- [x] 四处使用 DOM 文本节点显示；每日编辑列表的简介位于名称下，原移除/锁定/排序/移动保留。旧数据缺字段显示明确兜底。
- [x] ASSETS 挂载 `/poi_content.js`，HTML 在消费者前 defer 加载；全页版本更新为 28。最小响应式样式保留完整文本，长文本可换行。
- [x] 新测试与所有 `tests/*.test.js` 通过，报告变更与测试结果。

## Task 3：集成与独立审查（主代理/审查代理）

- [x] 在 `tools/verify_recommendations.cjs` 增加真实服务验证：景点列表/详情/推荐/日卡都包含实际简介；展开当日后点击移除，状态及界面均删除该点；重载后不出现。手机 768/390/320 宽度无溢出。
- [x] 先做规格审查再代码质量审查，检查可选兼容、纯文本安全、全部 45 条覆盖、现有用户数据及编辑功能保护，修复真实问题后定向复验。

## Task 4：交付验证

- [x] `python tools/verify_project.py` 全组通过；`node tools/verify_recommendations.cjs` 浏览器通过。测试用临时目录及本地隔离服务，不重启用户进程。
- [x] 更新 README 与模块说明，保存验收日志/截图，所有计划勾选只在对应工作完成后更新。

