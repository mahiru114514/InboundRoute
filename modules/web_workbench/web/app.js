"use strict";
/* 页面启动和事件装配；在所有功能脚本之后加载。 */

async function boot() {
  if (window.IRLanguage) window.IRLanguage.init();
  if (window.IROnboarding) window.IROnboarding.init();
  $("setup-form").addEventListener("submit", createTrip);
  $("reset-form").addEventListener("click", resetSetup);
  // 草稿自动保存：刷新或误关页面时，① 里未提交的设定不该丢。
  $("setup-form").addEventListener("input", saveDraft);
  $("setup-form").addEventListener("change", saveDraft);
  applyArrivalDefaults();
  $("poi-search").addEventListener("input", renderPoiList);
  $("poi-category").addEventListener("change", renderPoiList);
  wirePoiScroll();
  $("detail-close").addEventListener("click", () => $("detail").close());
  $("d-add").addEventListener("click", addSelectedToDay);
  // 换一天 = 预检结论作废，必须重新预检，不能沿用上一天的「确认仍然加入」。
  $("d-day").addEventListener("change", resetAddConfirmation);
  $("map-toggle").addEventListener("click", onMapToggle);
  // 口岸 / 住宿：中文、英文、拼音都能联想；下拉框永远只列出匹配项。
  $("hub-search").addEventListener("input", () => renderAnchorPickers());
  $("hotel-search").addEventListener("input", () => renderAnchorPickers());
  $("hotel").addEventListener("change", () => { $("anchor-pick-state").textContent = pickStateText(); });
  wireDeparture();
  if (typeof wireRecommendations === "function") wireRecommendations();
  if (typeof wireDayCardNavigation === "function") wireDayCardNavigation();

  // 先从本模块服务器取会话令牌与地图配置（CSP 不允许内联脚本，因此不能直接注入页面）
  try {
    const session = await api(SESSION_PATH);
    WB.token = session.token;
    WB.base = session.base;
    state.mapConfig = session.map || { ready: false, hint: "" };
  } catch (error) {
    notify(`无法获取会话令牌：${error.message}`, true);
    return;
  }
  if (typeof wireCurrency === "function") await wireCurrency();
  state.currentDayIndex = 1;
  await refreshServices();
  // 口岸/住宿清单来自 trip_engine 的 GET /anchors：取不到就禁用下拉并说明原因。
  // 这里刻意没有「写死的内置清单」兜底——创建行程本来就必须能连上 trip_engine。
  try {
    await loadAnchors();
  } catch (error) {
    renderAnchorPickers();
    notify(`口岸/住宿清单加载失败：${error.message}（创建行程需要先启动 trip_engine）`, true);
  }
  // 恢复未提交的草稿；有草稿时它覆盖上面那组动态默认值。
  try {
    await loadPois();
  } catch (error) {
    notify(`POI 列表加载失败：${error.message}`, true);
  }
  await initMap();
  // 历史恢复与流程初始化（flow.js）：刷新/重开页面都要能把已保存的行程找回来。
  if (typeof initFlow === "function") {
    try {
      await initFlow();
    } catch (error) {
      notify(`恢复历史行程失败：${error.message}`, true);
    }
  }
  const draft = loadDraft();
  if (draft && (draft.trip_id || null) === (state.trip?.trip_id || null)) applyDraft(draft);
  if (typeof renderRecommendations === "function") renderRecommendations();
  setInterval(refreshServices, 3000);
}

/** 启动入口。挂到 window 上是为了让自动化测试/页面自检能等到初始化真正结束，
 *  否则「刷新后行程有没有恢复」这类断言只能靠 sleep 猜。 */
window.__workbenchBoot = boot();
