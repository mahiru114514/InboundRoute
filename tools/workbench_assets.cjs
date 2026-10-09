"use strict";
/* 页面测试与隔离验收共用实际 HTML 和 HTTP 挂载表。 */
const fs = require("node:fs");
const path = require("node:path");

const WEB = path.join(__dirname, "..", "modules", "web_workbench", "web");
const INDEX_HTML = path.join(WEB, "index.html");
const html = fs.readFileSync(INDEX_HTML, "utf8");
const engine = fs.readFileSync(path.join(WEB, "..", "engine.py"), "utf8");
const ASSETS = {};
for (const match of engine.matchAll(/"(\/[\w.]*)":\s*\("([^"]+)",\s*"([^"]+)"\)/g)) {
  ASSETS[match[1]] = { file: match[2], mime: match[3] };
}
const scripts = [...html.matchAll(/<script[^>]+src="([^"?]+)\?v=\d+"/g)].map(match => {
  const url = match[1];
  if (!ASSETS[url]) throw new Error(`页面脚本没有登记 HTTP 挂载：${url}`);
  return { url, path: path.resolve(WEB, ASSETS[url].file) };
});

module.exports = { WEB, INDEX_HTML, html, ASSETS, scripts };
