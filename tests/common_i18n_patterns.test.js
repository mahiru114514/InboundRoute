"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const web=path.join(__dirname,'../modules/web_workbench/web');
const context={window:null,document:{getElementById:()=>null}};context.window=context;vm.createContext(context);
for(const name of ['i18n_catalog.js','poi_i18n_catalog.js','common_i18n_catalog.js','suggestions_i18n.js','common_i18n_patterns.js','i18n.js']) {
  const file=path.join(web,name);if(fs.existsSync(file))vm.runInContext(fs.readFileSync(file,'utf8'),context);
}
const api=context.IRLanguage;
const samples=[
  'Day 3 出发时刻',
  'Day 3 起始点搜索','Day 3 终止点','Day 3 添加住宿或口岸',
  '抵达当天最早 10:15 出发。',
  '最早 10:15 出发；修改后自动保存并重新校验，请重算当天交通。',
  '前一天结束在自定义酒店甲，当天从Custom Hotel出发，请确认住宿或接驳安排。',
  '3 个景点 · 2 项住宿 / 口岸 · 停留 150 分钟 · 游览 10:15–18:30',
  '0 个景点 · 0 项住宿 / 口岸 · 停留 0 分钟 · 10:15 出发',
  '抵达与入住 · 2026-10-08 10:15 缓冲结束',
  '10:15 出发 · 结束待定',
  '10:15 抵达 · 18:30 离开',
  '2 段交通待补','2 段交通方式受限',
  '2026-10-08 起 · 5 天','建议 2/3',
  '共 3 份已保存行程；刷新或重开页面会自动恢复上次编辑的那一份。',
  '上海 · 2026年10月8日出发 · 5天（行程2）',
  '上海 · 日期待设置 · 天数待设置',
  'Day 3 出发时刻已保存为 10:15；请重新计算当天交通。',
  '每日地点已保存；请重新计算 Day 2、3 的交通。',
  '为第 3 个景点选择目标日期',
  'Day 3 没有景点且起终点相同，无需计算交通。',
  'Day 3：第 2/4 段计算失败——HTTP 503。已保留前面算出的区段。',
  '另有 3 条非硬建议未就地展示（硬冲突已全部列出）。',
  '展开全部建议（3 条）',
  '公共交通暂不可用，请选择下方可用方案（演示路线，非真实导航）',
  '预检发现硬冲突：HTTP 409。再次点击「加入行程」表示仍然保留。',
  '预检发现 2 条硬冲突，已在抽屉里说明',
  '已加入 Day 3；Warning 2（仅提示，可继续添加）',
  '无法获取会话令牌：HTTP 503',
  '口岸/住宿清单加载失败：HTTP 503（创建行程需要先启动 trip_engine）',
  'POI 列表加载失败：HTTP 503',
  '恢复历史行程失败：HTTP 503',
  '行程已更新，但规则未完成校验：HTTP 503',
  '行程创建后规则校验被拒绝，已回滚：HTTP 409',
  '行程已创建，但规则未完成校验：HTTP 503',
  '自动回滚失败，请手动删除行程 custom-trip-123：HTTP 503',
  '浏览器缓存失败：HTTP 503。仍可下载离线文件。',
  '汇率获取失败：HTTP 503。保留 ECB · 2026-10-08 · 参考汇率已过期，请更新核对。',
  '汇率无效：Error 2。请填写有效汇率，或选择人民币。',
  'ECB · 2026-10-08 · 缓存已过期，请更新核对 · 外币金额为近似值。',
  'ECB · 2026-10-08 · 缓存参考汇率 · 外币金额为近似值。',
  'Budget须为非负金额，最多2位小数',
  '底图加载失败，已降级为示意地图。原因：HTTP 503。请检查高德 key、安全密钥与域名白名单。',
  '高德瓦片不可用，已自动切换到备用底图（OpenStreetMap）；视野与图钉不受影响。',
  '高德地图（CDN）',
  '当前筛选命中 3 / 45 个 POI；全览模式：已框入全部 3 个 POI；市中心区域被压缩属正常。图钉状态：默认（白） / 已加入当天（浅绿） / 已加入其他天（D 角标） / 当前选中（深绿） / 有冲突（红）。',
  '当前筛选命中 3 / 45 个 POI；默认聚焦市中心 2 个点位；1 个远郊点（私人名称甲）用「显示全部」查看。图钉状态：默认（白） / 已加入当天（浅绿） / 已加入其他天（D 角标） / 当前选中（深绿） / 有冲突（红）。',
  '约12分钟','150米','步行150米','3站','Custom Station上车','Custom Station下车',
  '步行 · 150米 · 约3分钟 · Custom entrance',
  'Line 2 · Custom Station上车 · Other Station下车 · Direction A · 3站 · 约12分钟',
  '换乘 · Custom passage · 步行150米 · 约3分钟',
  '按计划起点出发 · 公共交通。手机尝试打开高德App；无法打开时可使用网页版。高德会重新规划，具体线路可能不同。',
  '驾车导航到落客点：Custom Entrance。下车后请核实步行入口。',
  '住宿按行程前 4 晚、2 人、1 间房估算；跨零点、提前入住或延住请切换手动房晚。',
  'Day 3 CustomMuseum门票',
  'Day 3 第 2 段交通（返程 / 终点）',
  'Day 3 第 2 段交通',
  '2026-10-08每人餐饮',
  '机动费用 10%',
  'Day 3 CustomMuseum门票费用待补充（免费或不发生请明确填写 0）',
  '2026-10-08 自定义酒店甲：酒店价格待核实（自选位置或酒店实体冲突请手填）',
  '2026-10-08 Custom Hotel：每间房价、房间数或实际同行人数待补充',
  'Day 3 CustomMuseum门票：¥60.00 / 人 · Manual Quote（查询于 2026-10-08）',
  'Custom Hotel 每间每晚参考 ¥500.00–¥600.00；自动模式保留区间，手动模式请填实际房价。',
  'Day 3 · CustomMuseum 门票 / 人',
  '2026-10-08 餐饮 / 人（空白沿用每日金额）',
  '留空自动计入 ¥60.00',
  ' 来源3',
  '参考 ¥60.00',
  'cost_inputs.travelers 必须是 1~100 的整数',
  'cost_inputs.ticket_cents 必须是金额映射，最多 240 项',
  'travelers请输入整数',
  '请求体超过 1048576 字节',
  'Day 3 不存在（行程共 2 天）',
  'POI 不存在：custom-poi-3',
  '行程不存在：custom-trip-123',
  '路线服务未就绪：未运行（无注册文件）。',
  'Day 1 第 1 段交通：已选路线或人民币费用待补充',
  'Day 1 第 2 段交通（返程 / 终点）：已选路线或人民币费用待补充',
  'Day 1 第 1 段交通：演示路线不能计入真实费用',
  'Day 1 第 1 段交通：实际同行人数和打车车辆数待补充',
  '至少 2 Hours','请求失败（HTTP 503）','推荐失败：请求失败（HTTP 503）',
];
for(const original of samples)for(const language of ['en','ja','ko']) {
  const result=api.translate(original,language);
  assert.notEqual(result,original,`Missing ${language}: ${original}`);
  if(language==='en')assert.ok(!/[\u4e00-\u9fff]/.test(result.replaceAll('自定义酒店甲','').replaceAll('私人名称甲','')),`Partial English: ${result}`);
  assert.deepEqual(result.replaceAll('1인당','').replaceAll('1박','').match(/\d+(?:\.\d+)?/g),original.match(/\d+(?:\.\d+)?/g),`Numeric or date change: ${original} => ${result}`);
  assert.equal(api.translate(original,'zh-CN'),original);
}
for(const language of ['en','ja','ko']) {
  for(const value of ['私人名称甲 2026-10-08 10:15','宿营地 起航口 终点书店','Custom name Day 3'])assert.equal(api.translate(value,language),value);
  assert.ok(api.translate(samples[6],language).includes('自定义酒店甲'));
  for(const prefix of ['酒店','口岸','景点','当前住宿','已保存地点','自动','行程口岸'])for(const name of ['上海外滩华尔道夫酒店','我的自定义酒店','Custom Hotel']) {
    const translated=api.translate(`${prefix} · ${name}`,language);
    assert.equal(translated.split(' · ')[1],name,`${language} must preserve selector name: ${name}`);
    assert.equal(api.translate(`${prefix} · ${name}`,'zh-CN'),`${prefix} · ${name}`);
  }
  const boundary='前一天结束在上海外滩华尔道夫酒店，当天从我的自定义酒店出发，请确认住宿或接驳安排。';
  const translated=api.translate(boundary,language);
  assert.ok(translated.includes('上海外滩华尔道夫酒店') && translated.includes('我的自定义酒店'));
}
assert.equal(api.translate('约12分钟','en'),'About 12 min');
assert.equal(api.translate('Day 3 出发时刻','ja'),'3日目の出発時刻');
assert.equal(api.translate('Day 3 出发时刻','ko'),'3일차 출발 시간');
console.log(`common i18n patterns: ${samples.length} dynamic UI strings in en/ja/ko, numbers, dates and custom names passed`);
