"use strict";
/* 使用说明独立于业务请求；仅保存已看版本，不读写行程或表单草稿。 */
(() => {
  const storageKey = 'inboundroute.onboarding.seen';
  const version = '1';
  const steps = [
    {
      title: '先确定这趟旅程', location: '行程设定',
      body: '填写行程天数、抵达时间和已预订的住宿，再选择兴趣与节奏，点击“保存行程”开始规划。',
      tip: '返程信息可选；预算填写每人整趟金额。所有时间按北京时间安排。',
    },
    {
      title: '选出想去的地方', location: '行程设定 / 挑选景点',
      body: '想省心，可以选择游玩日期后生成推荐行程；想自己选，可以搜索景点，打开详情并加入指定日期。',
      tip: '安排景点前先保存行程。推荐结果可以继续编辑，生成前请确认要安排的日期。',
    },
    {
      title: '把每一天排顺', location: '每日行程',
      body: '展开某一天，查看起点和终点，调整景点顺序，再计算区间交通并选择合适的出行方式。',
      tip: '需要途中休息或更换酒店时，可添加住宿或口岸；调整安排后记得重新计算交通。',
    },
    {
      title: '检查提醒与费用', location: '行程提醒 / 费用评估',
      body: '查看开放、预约与时间冲突提醒，按提示调整安排。展开每日行程上方的费用评估，核对预算和费用明细。',
      tip: '门票和住宿金额是规划参考；待补充项与开放信息需要在出发前确认。',
    },
    {
      title: '出发前保存问路包', location: '离线问路',
      body: '安排确认后生成离线包，下载问路卡 HTML 并保存到设备。下载的文件可以在没有网络或关闭本地服务时打开。',
      tip: '中文地名和问路卡方便向当地人问路。行程修改后，请重新生成并下载最新文件。',
    },
  ];
  let initialized = false, index = 0, restoreFocus = null, jumpToSetup = false;
  const el = id => document.getElementById(id);
  const t = text => window.IRLanguage ? window.IRLanguage.translate(text) : text;

  function render(resetReading = true) {
    const step = steps[index];
    el('onboarding-progress').textContent = `${index + 1} / ${steps.length}`;
    el('onboarding-step-title').textContent = t(step.title);
    el('onboarding-location').textContent = `${t('所在区域')} · ${t(step.location)}`;
    el('onboarding-body').textContent = t(step.body);
    el('onboarding-tip').textContent = t(step.tip);
    const detail = window.IROnboardingContent[index];
    detail.howto.forEach((text, i) => { el('onboarding-howto-' + i).textContent = t(text); });
    el('onboarding-example').textContent = t(detail.example);
    detail.faq.forEach((item, i) => {
      el('onboarding-question-' + (i + 1)).textContent = t(item.question);
      el('onboarding-answer-' + (i + 1)).textContent = t(item.answer);
      if (resetReading) el('onboarding-faq-' + (i + 1)).open = false;
    });
    steps.forEach((_, i) => el('onboarding-chapter-' + i).setAttribute('aria-current', i === index ? 'step' : 'false'));
    if (resetReading) el('onboarding-content').scrollTop = 0;
    el('onboarding-prev').disabled = index === 0;
    el('onboarding-next').textContent = t(index === steps.length - 1 ? '去设置行程' : '下一步');
  }

  function open() {
    if (el('onboarding-dialog').open) return;
    restoreFocus = document.activeElement;
    jumpToSetup = false;
    index = 0;
    render();
    el('onboarding-dialog').showModal();
  }

  function init() {
    const dialog = el('onboarding-dialog');
    if (initialized || !dialog || typeof dialog.showModal !== 'function') return;
    initialized = true;
    el('onboarding-open').addEventListener('click', open);
    steps.forEach((_, i) => el('onboarding-chapter-' + i).addEventListener('click', () => {
      index = i;
      render();
      el('onboarding-chapter-' + i).scrollIntoView({block: 'nearest', inline: 'nearest'});
    }));
    el('onboarding-prev').addEventListener('click', () => {
      if (index > 0) { index--; render(); }
    });
    el('onboarding-next').addEventListener('click', () => {
      if (index < steps.length - 1) { index++; render(); }
      else { jumpToSetup = true; dialog.close(); }
    });
    for (const id of ['onboarding-skip', 'onboarding-close']) {
      el(id).addEventListener('click', () => dialog.close());
    }
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      dialog.close();
    });
    dialog.addEventListener('close', () => {
      try { window.localStorage?.setItem(storageKey, version); } catch (_) { /* 存储不可用仍可关闭 */ }
      if (jumpToSetup) {
        jumpToSetup = false;
        el('setup-disclosure').open = true;
        el('setup-panel').scrollIntoView({behavior: 'instant', block: 'start'});
        el('setup-panel').focus({preventScroll: true});
      } else {
        const target = restoreFocus && restoreFocus !== document.body ? restoreFocus : el('onboarding-open');
        target?.focus({preventScroll: true});
      }
    });
    window.addEventListener?.('inboundroute:languagechange', () => { if (dialog.open) render(false); });
    let seen = false;
    try { seen = window.localStorage?.getItem(storageKey) === version; } catch (_) { /* 首次仍展示 */ }
    if (!seen) open();
  }

  window.IROnboarding = {init};
})();
