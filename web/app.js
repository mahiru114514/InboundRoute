"use strict";
const $ = (id) => document.getElementById(id);
let token = "", modules = [], filter = "all", selected = null, busy = false, shuttingDown = false, folderInstall = null;
let toastTimer, confirmAction;
const labels = {running:"运行中",stopped:"未运行",failed:"运行异常",invalid:"格式异常",completed:"已完成"};
function notify(message, error = false) {
  $("toast").textContent = message; $("toast").className = "toast" + (error ? " error" : "");
  $("toast").hidden = false; clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").hidden = true, error ? 7000 : 4000);
}
async function api(path, body, format) {
  const headers = {"X-Manager-Token":token};
  if (format) headers["X-Install-Format"] = format;
  const response = await fetch(path, body === undefined ? {} : {method:"POST", headers, body:body instanceof File ? body : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}
function element(tag, className, text) {
  const node = document.createElement(tag); node.className = className || "";
  if (text !== undefined) node.textContent = text;
  return node;
}
function attention(m) { return m.error || m.warning || m.status === "failed"; }
const healthLabels = {ok:"健康", down:"无响应", starting:"启动中", no_port:"未注册端口"};
function serviceText(service) {
  const label = healthLabels[service.health] || service.health;
  if (service.health === "ok") return `服务端口 ${service.port} · ${service.health_path} ${label}`;
  if (service.port) return `服务端口 ${service.port} · ${label}（${service.detail || "无详情"}）`;
  return `服务型模块 · ${label}`;
}
function button(text, handler, className = "", disabled = false) {
  const node = element("button", className, text); node.disabled = disabled || busy;
  node.addEventListener("click", handler); return node;
}
function render() {
  $("total").textContent = modules.length;
  $("running").textContent = modules.filter(m => m.status === "running").length;
  $("enabled").textContent = modules.filter(m => m.enabled).length;
  $("errors").textContent = modules.filter(attention).length;
  $("nav-count").textContent = modules.length;
  const query = $("search").value.toLowerCase();
  const visible = modules.filter(m => (m.name + m.id).toLowerCase().includes(query) &&
    (filter === "all" || filter === "running" && m.status === "running" || filter === "disabled" && !m.enabled || filter === "error" && attention(m)));
  $("list-count").textContent = visible.length;
  const list = $("module-list"); list.replaceChildren();
  if (!visible.length) {
    const empty = element("div", "empty"); empty.append(element("strong", "", modules.length ? "没有匹配的模块" : "你的工作空间，准备就绪"),
      element("p", "", modules.length ? "试试其他关键词或筛选条件。" : "点击“安装模块”上传 ZIP，或放入模块文件夹后刷新发现。"));
    list.append(empty);
  }
  for (const m of visible) {
    const card = element("article", "module-card"), body = element("div", "card-body"), top = element("div", "card-top");
    top.append(element("div", "module-icon", m.name.slice(0,1)), element("span", "badge " + m.status, m.status === "stopped" && !m.enabled ? "已禁用" : labels[m.status]));
    body.append(top, element("h3", "", m.name), element("div", "module-meta", `${m.id} / v${m.version}`),
      element("p", "module-description", m.description || "尚未填写模块说明"), element("div", "dependencies", m.dependencies.length ? "依赖 · " + m.dependencies.join("、") : "独立模块 · 无前置依赖"));
    if (m.service) {
      const line = element("div", "module-service " + m.service.health, serviceText(m.service));
      if (m.service.base_url) line.title = m.service.base_url + m.service.health_path;
      body.append(line);
    }
    if (attention(m)) body.append(element("div", "module-warning", m.error || m.warning || "执行失败，请查看运行日志。"));
    // 由启动器/其他窗口拉起的实例：必须说清「在运行、但这里停不掉」，否则用户会去点「运行」
    // 然后撞上「检测到另一个运行实例」，或者以为停止成功了。
    const external = !!m.external;
    if (external) body.append(element("div", "module-note",
      "由启动器（start_software）或其他窗口启动：本页面停不掉它，请在那个窗口按 Ctrl+C。"));
    const foot = element("div", "card-footer");
    const mainButton = button(external ? "运行中（外部）" : (m.status === "running" ? "停止" : "运行"),
      () => action(m, m.status === "running" ? "stop" : "start"), "action-main",
      !!m.error || !m.enabled || external);
    if (external) mainButton.title = "该实例由启动器或其他窗口启动，请到那个窗口停止它";
    foot.append(button(m.enabled ? "禁用" : "启用", () => action(m, m.enabled ? "disable" : "enable"), "", !!m.error),
      mainButton,
      button("配置", () => openDetail(m, "config"), "", !!m.error), button("日志", () => openDetail(m, "logs"), "", !!m.error),
      button("卸载", () => confirm("卸载模块", `将移除“${m.name}”的代码，保留数据、日志与配置。模块需要先禁用，且不能被其他模块依赖。`, () => action(m,"uninstall")), "delete"));
    card.append(body, foot); list.append(card);
  }
  $("upload").disabled = busy; $("refresh").disabled = busy; $("install-folder").disabled = busy;
}
async function refresh(silent = false) {
  try {
    const state = await api("/api/state");
    const changed = JSON.stringify(modules) !== JSON.stringify(state.modules) || !token;
    token = state.token; modules = state.modules;
    // 无状态变化时保留 DOM，避免轮询打断键盘焦点。
    if (changed || !silent) render();
    $("connection-text").textContent = "本机服务已连接"; $("connection-dot").className = "";
    return true;
  } catch (e) {
    $("connection-text").textContent = "服务未连接"; $("connection-dot").className = "off";
    if (!silent) notify("无法连接本机服务，请双击 start.bat 启动。", true);
    return false;
  }
}
async function mutate(task) {
  if (busy) return; busy = true; render();
  try { const result = await task(); notify(result.message || "操作完成"); }
  catch (e) { notify(e.message, true); }
  finally { busy = false; render(); await refresh(true); }
}
function action(m, actionName) { return mutate(() => api(`/api/modules/${encodeURIComponent(m.id)}/${actionName}`, {})); }
function confirm(title, text, callback) {
  $("confirm-title").textContent = title; $("confirm-text").textContent = text; confirmAction = callback; $("confirm").showModal();
}
function tab(which) {
  $("config-panel").hidden = which !== "config"; $("logs-panel").hidden = which !== "logs";
  $("config-tab").classList.toggle("selected", which === "config"); $("logs-tab").classList.toggle("selected", which === "logs");
}
async function openDetail(m, which) {
  try {
    const data = await api(`/api/modules/${encodeURIComponent(m.id)}`); selected = m;
    $("detail-title").textContent = m.name; $("config-editor").value = JSON.stringify(data.config, null, 2);
    $("config-editor").disabled = m.status === "running"; $("save-config").disabled = m.status === "running";
    $("log-content").textContent = data.logs || "暂无日志，运行模块后会显示在这里。"; tab(which); $("detail").showModal();
  } catch(e) { notify(e.message, true); }
}
async function refreshLogs() {
  if (!selected) return;
  try { const data = await api(`/api/modules/${encodeURIComponent(selected.id)}`); $("log-content").textContent = data.logs || "暂无日志"; }
  catch(e) { notify(e.message, true); }
}
$("upload").onclick = () => $("zip-input").click();
$("zip-input").onchange = async () => {
  const file = $("zip-input").files[0]; if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip") || file.size > 20 * 1024 * 1024) notify("请选择不超过 20 MB 的 ZIP 文件。", true);
  else await mutate(() => api("/api/install", file));
  $("zip-input").value = "";
};
$("install-folder").onclick = () => $("dir-input").click();
$("dir-input").onchange = async () => {
  const chosen = Array.from($("dir-input").files || []); $("dir-input").value = "";
  if (!chosen.length) return;
  folderInstall = {folder: chosen[0].webkitRelativePath.split("/")[0], files: {}};
  for (const file of chosen) {
    const name = (file.webkitRelativePath || file.name).split("/").slice(1).join("/");
    // 与服务端保持同样的忽略规则，跳过本地缓存文件。
    if (!name || name.split("/").some(part => part === "__pycache__" || part === ".git") ||
        /\.py[co]$/i.test(name) || file.size > 20 * 1024 * 1024) continue;
    folderInstall.files[name] = file;
  }
  const size = Object.values(folderInstall.files).reduce((sum, file) => sum + file.size, 0);
  if (!Object.keys(folderInstall.files).length) notify("文件夹内没有可安装的文件。", true);
  else if (size > 80 * 1024 * 1024) notify("文件夹内容不能超过 80 MB。", true);
  else await installFolder();
};
async function readFile(file) {
  const buffer = new Uint8Array(await file.arrayBuffer());
  let text = "";
  for (let start = 0; start < buffer.length; start += 0x8000) text += String.fromCharCode(...buffer.subarray(start, start + 0x8000));
  return btoa(text);
}
async function installFolder() {
  const payload = folderInstall; folderInstall = null;
  notify("正在读取文件夹内容…");
  await mutate(async () => {
    const files = {};
    for (const [name, file] of Object.entries(payload.files)) files[name] = await readFile(file);
    return api("/api/install", {folder: payload.folder, files}, "folder");
  });
}
$("refresh").onclick = async () => { if (await refresh()) notify("已刷新本地模块"); };
$("search").oninput = render;
document.querySelectorAll("[data-filter]").forEach(b => b.onclick = () => {
  filter = b.dataset.filter; document.querySelectorAll("[data-filter]").forEach(n => {n.classList.toggle("selected", n === b); n.setAttribute("aria-pressed", String(n === b));}); render();
});
$("guide-open").onclick = $("guide-inline").onclick = () => $("guide").showModal();
$("guide-close").onclick = () => $("guide").close();
$("detail-close").onclick = () => $("detail").close();
$("config-tab").onclick = () => tab("config");
$("logs-tab").onclick = () => { tab("logs"); refreshLogs(); };
$("refresh-logs").onclick = refreshLogs;
$("save-config").onclick = async () => {
  try {
    const config = JSON.parse($("config-editor").value);
    if (!config || Array.isArray(config) || typeof config !== "object") throw new Error("配置必须是 JSON 对象，例如 {}。");
    $("save-config").disabled = true;
    await mutate(() => api(`/api/modules/${encodeURIComponent(selected.id)}/config`, config));
  } catch(e) { notify("配置未保存：" + e.message, true); }
  finally { $("save-config").disabled = false; }
};
$("confirm-cancel").onclick = () => $("confirm").close();
$("confirm-ok").onclick = () => { $("confirm").close(); if (confirmAction) confirmAction(); };
$("shutdown").onclick = () => confirm("关闭管理服务", "将停止所有运行中的模块并关闭本机服务。下次使用时，双击 start.bat 重新打开。", async () => {
  try { await api("/api/shutdown", {}); shuttingDown = true; $("connection-text").textContent = "服务已关闭"; $("connection-dot").className = "off"; notify("管理服务已关闭，可关闭此页面。"); }
  catch(e) { notify(e.message, true); }
});
refresh();
setInterval(async () => {
  if (busy || shuttingDown) return;
  await refresh(true);
  if ($("detail").open && !$("logs-panel").hidden) await refreshLogs();
}, 3000);
