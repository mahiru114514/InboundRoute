"use strict";
/* 服务健康状态条；依赖 runtime。 */

/* ---------------------------------------------------------------- 引擎状态条 */

function renderServices() {
  const box = $("engine-status");
  box.replaceChildren();
  const list = state.services.services || [];
  const missing = list.filter((item) => !item.ready);
  const names = {trip_engine:"行程", recommendation_engine:"推荐", rules_engine:"时间校验", route_adapter:"交通", offline_kit:"离线问路"};
  for (const item of list) {
    const chip = element("span", "chip " + (item.ready ? "ok" : "off"));
    chip.textContent = `${names[item.module_id] || item.module_id} ${item.ready ? "就绪" : "未就绪"}`;
    chip.title = `${item.purpose}\n${item.detail}${item.base_url ? `\n${item.base_url}` : ""}`;
    box.append(chip);
  }
  const hint = $("ancillary-hint");
  const optional = missing.filter((item) => item.module_id !== "trip_engine");
  if (optional.length) {
    hint.textContent = "以下功能暂不可用：" +
      optional.map((item) => names[item.module_id] || item.module_id).join(" · ");
  } else {
    hint.textContent = "";
  }
  // 引擎可能中途启动：状态变了要同步刷新 时间校验、日卡交通与离线面板的「为什么不能用」说明。
  if (typeof renderFlow === "function" && state.trip) renderFlow();
  if (typeof renderRecommendations === "function") renderRecommendations();
}

async function refreshServices() {
  try {
    state.services = await api("/api/services");
  } catch (error) {
    state.services = { services: [], ready: {} };
  }
  renderServices();
}
