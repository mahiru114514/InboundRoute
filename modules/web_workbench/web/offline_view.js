"use strict";
/* 离线显示层只消费固化的包数据；预览与下载共用，不依赖引擎、地图或网络。 */
const ASK_TEMPLATES = {
  station_entrance:{zh:'请问去往 {access_name_zh} 怎么走？',en:'Excuse me, which way is {access_name_en}?',ja:'すみません、{access_name_en} へはどう行けばよいですか？',ko:'실례합니다, {access_name_en}에는 어떻게 가나요?'},
  station_exit:{zh:'请问 {access_name_zh} 在哪个方向？',en:'Excuse me, which way is {access_name_en}?',ja:'すみません、{access_name_en} はどちらですか？',ko:'실례합니다, {access_name_en}은 어느 방향인가요?'},
  transfer:{zh:'请问换乘 {line_name_zh} 怎么走？',en:'Excuse me, how do I transfer to {line_name_en}?',ja:'すみません、{line_name_en} へはどう乗り換えればよいですか？',ko:'실례합니다, {line_name_en}으로 어떻게 환승하나요?'},
  direction_fallback:{zh:'请问 {line_name_zh} 怎么走？',en:'Excuse me, which way is {line_name_en}?',ja:'すみません、{line_name_en} はどちらですか？',ko:'실례합니다, {line_name_en}은 어느 방향인가요?'},
  drop_off:{zh:'请把我送到 {desc_zh}。',en:'Please drop me off at {desc_en}.',ja:'{desc_en} で降ろしてください。',ko:'{desc_en}에서 내려 주세요.'},
  poi_arrival:{zh:'请问 {poi_name_zh} 怎么走？',en:'Excuse me, how do I get to {poi_name_en}?',ja:'すみません、{poi_name_en} へはどう行けばよいですか？',ko:'실례합니다, {poi_name_en}에는 어떻게 가나요?'}
};
const OFFLINE_LABELS = {
  namesReview:['地名英文待确认','Unconfirmed place names','地名の英語表記を確認してください','장소 영문 이름 확인 필요'],
  namesMissing:['部分地名缺少英文','Some place names have no English translation','一部の地名に英語表記がありません','일부 장소의 영문 이름이 없습니다'],
  namesNote:['以下为拼音候选或尚缺译名，可在工作台填写确认后的英文并重新生成。','These names use provisional romanization or have no translation. Confirm their English names in the planner and regenerate the pack.','仮のローマ字表記または未翻訳の地名です。旅行画面で英語表記を確認し、再作成してください。','임시 로마자 표기 또는 번역이 없는 이름입니다. 플래너에서 영문 이름을 확인하고 다시 생성하세요.'],

  title:['离线行程与问路卡','Offline trip & direction cards','オフライン旅行・道案内カード','오프라인 여행 및 길 안내 카드'],
  version:['行程版本','Trip version','旅行バージョン','여행 버전'],
  generated:['生成于','Generated on','作成日時','생성일'],
  validity:['有效期','Valid for','有効期限','유효 기간'],
  hours:['小时','hours','時間','시간'],
  timezone:['所有时间为北京时间（UTC+8）。','All times are China time (UTC+8).','時刻はすべて中国時間（UTC+8）です。','모든 시간은 중국 시간 (UTC+8)입니다.'],
  note:['离线快照：请核实实时交通与开放情况。','Offline snapshot: verify live transport and opening hours.','オフラインの保存版です。最新の交通と営業時間を確認してください。','오프라인 저장본입니다. 실시간 교통과 운영 시간을 확인하세요.'],
  stale:['离线数据可能已过期，请在工作台重新生成。','Offline data may be outdated. Generate a new pack in the planner.','オフライン資料は期限切れの可能性があります。旅行画面で再作成してください。','오프라인 자료가 만료되었을 수 있습니다. 플래너에서 다시 생성하세요.'],
  start:['起点：','Start: ','出発：','출발: '],end:['终点：','End: ','到着：','도착: '],
  dailyStart:['计划开始时间','Planned start time','予定開始時刻','예정 시작 시간'],
  unknown:['未设置','Not set','未設定','미설정'],
  unavailable:['信息待补充','Information unavailable','情報なし','정보 없음'],
  arrivalUnknown:['到达时间未确定','Arrival time unconfirmed','到着時刻は未確定','도착 시간 미정'],
  arrival:['抵达','Arrival','到着','도착'],departure:['离开','Departure','出発','출발'],
  stay:['停留','Stay','滞在','체류'],minutes:['分钟','min','分','분'],meters:['米','m','m','m'],
  poi:['景点','Attraction','観光地','관광지'],rest:['休息','Rest','休憩','휴식'],overnight:['过夜住宿','Overnight stay','宿泊','숙박'],
  gateway:['口岸','Airport / station','空港・駅','공항 / 역'],
  final:['当天终点交通','Final transfer','最終地点への移動','당일 마지막 구간 교통'],
  finalMissing:['终点交通未包含在此快照中，请重新计算交通并生成离线包。','Final transfer unavailable in this snapshot. Recalculate transport and regenerate the pack.','最終地点への移動がありません。移動を再計算して保存版を再作成してください。','마지막 구간 교통이 없습니다. 교통을 다시 계산하고 패키지를 다시 생성하세요.'],
  finalNone:['起终点相同，无需额外交通。','Same start and end point; no additional transfer needed.','出発・到着地点が同じため、追加の移動は不要です。','출발과 도착 지점이 같아 추가 교통이 필요하지 않습니다.'],
  empty:['当天没有景点停靠。','No attraction stops on this day.','この日に観光地の立ち寄りはありません。','이 날짜에는 관광지 방문이 없습니다.'],
  mode:['选定交通','Selected transport','選択した交通','선택한 교통'],
  transit:['公共交通','Public transport','公共交通','대중교통'],taxi:['打车','Taxi','タクシー','택시'],walk:['步行','Walk','徒歩','도보'],bike:['骑行','Cycle','自転車','자전거'],
  duration:['预计耗时','Estimated duration','所要時間の目安','예상 소요 시간'],
  station:['车站与进出站口','Stations and access points','駅と出入口','역 및 출입구'],
  line:['线路','Line','路線','노선'],access:['进出站口编号','Access number','出入口番号','출입구 번호'],
  walking:['步行与换乘提示','Walking and transfer notes','徒歩と乗り換えの案内','도보 및 환승 안내'],
  transfer:['换乘步行','Transfer walk','乗り換えの徒歩','환승 도보'],
  ask:['向当地人问路','Ask a local','現地の方に道を尋ねる','현지인에게 길 묻기'],
  noCards:['暂无完整问路卡，请核实目的地和入口。','Direction cards unavailable. Verify your destination and entrance.','道案内カードがありません。目的地と入口を確認してください。','길 안내 카드가 없습니다. 목적지와 입구를 확인하세요.'],
  demo:['演示路线，不能用于真实导航。','Demo route. Do not use for actual navigation.','デモ経路です。実際の案内には使えません。','시연 경로입니다. 실제 길 안내에 사용하지 마세요.'],
  source:['路线来源','Route source','経路の出典','경로 출처'],
};
function offlineLocale(code) {const base=String(code || '').toLowerCase().split(/[-_]/)[0];return base==='zh' ? 'zh-CN' : ['en','ja','ko'].includes(base) ? base : 'en';}
function offlineCurrentLanguage() {return typeof window !== 'undefined' && window.IRLanguage ? window.IRLanguage.language : 'zh-CN';}
function offlineLabel(key,locale) {return OFFLINE_LABELS[key][['zh-CN','en','ja','ko'].indexOf(offlineLocale(locale))];}
function askCardText(card, locale=offlineCurrentLanguage()) {
  const template=ASK_TEMPLATES[card.template_key];if (!template) return null;
  locale=offlineLocale(locale);
  const local=locale==='ja' || locale==='ko' ? locale : 'en';
  const valid=text=>[...text.matchAll(/\{([^}]+)\}/g)].every(match=>typeof card.args?.[match[1]]==='string' && card.args[match[1]].trim());
  if (![template.zh,template.en,template[local]].every(valid)) return null;
  const fill=(text,code)=>text.replace(/\{([^}]+)\}/g,(_,key)=> {
    if(code!=='ja' && code!=='ko') return card.args[key];
    const base=key.replace(/_en$/,'');
    return offlineField(card.args,base,code,card.template_key==='station_exit' ? 'exit' : card.template_key==='station_entrance' ? 'entrance' : '');
  });
  return {zh:fill(template.zh,'zh-CN'),en:fill(template.en,'en'),local:fill(template[local],local),language:local};
}
function escapeOffline(value) {return String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
/* 地名与指令由同一快照渲染；仅匹配完整名称或已知句式，不对用户名字做子串猜译。
   景点/住宿复用四语目录。目录未覆盖的专名保留罗马字，通用交通词随语言切换。 */
const OFFLINE_NATIVE_NAMES=[
  ['外滩','The Bund','外灘（バンド）','와이탄'],
  ['人民广场',"People's Square",'人民広場','인민광장'],
  ['上海图书馆','Shanghai Library','上海図書館','상하이 도서관'],
  ['交通大学','Jiao Tong University','交通大学','자오퉁대학'],
  ['南京东路','East Nanjing Road','南京東路','난징둥루'],
  ['南京西路','West Nanjing Road','南京西路','난징시루'],
  ['陆家嘴','Lujiazui','陸家嘴','루자쭈이'],
  ['静安寺',"Jing'an Temple",'静安寺','정안사'],
  ['七宝','Qibao','七宝','치바오'],
  ['上海动物园','Shanghai Zoo','上海動物園','상하이 동물원'],
  ['中山公园','Zhongshan Park','中山公園','중산공원'],
  ['长风公园','Changfeng Park','長風公園','창펑공원'],
  ['国际客运中心','International Cruise Terminal','国際クルーズターミナル','국제 크루즈 터미널'],
  ['天潼路','Tiantong Road','天潼路','톈퉁루'],
  ['娄山关路','Loushanguan Road','婁山関路','러우산관루'],
  ['打浦桥','Dapuqiao','打浦橋','다푸차오'],
  ['曲阜路','Qufu Road','曲阜路','취푸루'],
  ['淞虹路','Songhong Road','淞虹路','쑹훙루'],
  ['红宝石路','Hongbaoshi Road','紅宝石路','훙바오스루'],
  ['陕西南路','South Shaanxi Road','陝西南路','산시난루'],
  ['隆德路','Longde Road','隆徳路','룽더루'],
  ['龙华中路','Middle Longhua Road','龍華中路','룽화중루'],
  ['昌邑路','Changyi Road','昌邑路','창이루'],
  ['迎春路','Yingchun Road','迎春路','잉춘루'],
  ['一大会址·黄陂南路','Site of the First CPC National Congress · South Huangpi Road','一大会址・黄陂南路','제1차 당대회 유적지 · 황피난루'],
  ['封浜','Fengbang','封浜','펑방'],
  ['桂桥路','Guiqiao Road','桂橋路','구이차오루'],
  ['康文路','Kangwen Road','康文路','캉원루'],
  ['航头','Hangtou','航頭','항터우'],
  ['浦东国际机场',"Pudong Int'l Airport",'浦東国際空港','푸둥 국제공항'],
  ['浦东1号2号航站楼','Pudong Airport Terminal 1 & 2','浦東空港第1・第2ターミナル','푸둥공항 제1·2터미널'],
  ['虹桥2号航站楼','Hongqiao Airport Terminal 2','虹橋空港第2ターミナル','훙차오공항 제2터미널'],
  ['虹桥东交通中心','Hongqiao East Transportation Center','虹橋東交通センター','훙차오 동부 교통센터'],
  ['市域机场线','Airport Link Line','空港連絡線','공항 연결선'],
];
function offlineKnownName(zh,en,locale) {
  const rows=[...OFFLINE_NATIVE_NAMES,...(typeof window!=='undefined' ? window.IRLanguageCatalog || [] : [])];
  const row=rows.find(row=>zh ? row[0]===zh : en && row[1]===en);
  return row?.[locale==='ja' ? 2 : 3] || null;
}
function offlineNameTranslation(zh,en,locale,kind='') {
  if(locale!=='ja' && locale!=='ko') return en || '';
  const pick=(ja,ko)=>locale==='ja' ? ja : ko;
  zh=typeof zh==='string' ? zh.trim() : '';en=typeof en==='string' ? en.trim() : '';
  const known=offlineKnownName(zh,en,locale);if(known) return known;
  // 英文端点也可能来自「中文 / English」形式的用户锚点。
  if(zh.includes(' / ')) return offlineNameTranslation(zh.split(' / ')[0],en,locale,kind);
  const access=/^(Entrance|Exit|Gate)\s*(\d+[A-Za-z]?)$/i.exec(en);
  if(access) return `${access[2]}${pick('番','번 ')}${access[1].toLowerCase()==='exit' ? pick('出口','출구') : pick('入口','입구')}`;
  const toward=/^Towards (.+)$/i.exec(en);
  if(toward) {const target=/^往(.+)方向$/.exec(zh)?.[1];return offlineNameTranslation(target,toward[1],locale)+pick('方面',' 방면');}
  const line=/^(Line|Bus) (\d+[A-Za-z]?)(.*)$/.exec(en);
  if(line) return `${line[2]}${line[1]==='Line' ? pick('号線','호선') : pick('番バス','번 버스')}${offlineNameTranslation('',line[3],locale)}`;
  const terminals=/^(.*?)\s*\((.+ — .+)\)$/.exec(en);
  if(terminals) return `${offlineNameTranslation('',terminals[1],locale)} (${offlineNameTranslation('',terminals[2],locale)})`;
  for(const separator of [' — ',' / ']) if(en.includes(separator)) return en.split(separator).map(part=>offlineNameTranslation('',part,locale)).join(separator);
  const annotated=/^(.+?) \(([^()]+)\)$/.exec(en);
  if(annotated) return `${offlineNameTranslation('',annotated[1],locale)} (${offlineNameTranslation('',annotated[2],locale)})`;
  const split=zh.match(/^(.+?)(地铁站|辅路|步行街)$/);
  if(split) return offlineNameTranslation(split[1],en.replace(/ (Metro Station|service road|pedestrian street)$/i,''),locale)+
    ({地铁站:pick('地下鉄駅',' 지하철역'),辅路:pick('側道',' 보조도로'),步行街:pick('歩行者通り',' 보행자 거리')}[split[2]]);
  // 专名没有本地日韩译名时保留其罗马字；只本地化通用类型词。
  const words=[['Airport Link Line','空港連絡線','공항 연결선'],['night bus','深夜バス','심야 버스'],
    ['Metro Station','地下鉄駅','지하철역'],['Railway Station','鉄道駅','기차역'],['service road','側道','보조도로'],
    ['pedestrian street','歩行者通り','보행자 거리'],['North Square','北広場','북광장'],['South Square','南広場','남광장'],
    ['Road Number Two','第2通り','제2로'],['Road','通り','로'],['Rd','通り','로'],['Avenue','大通り','대로'],
    ['Highway','幹線道路','간선도로'],['Street','通り','거리'],['Hotel','ホテル','호텔'],['Inn','旅館','여관'],
    ['Airport','空港','공항'],['Terminal','ターミナル','터미널'],['Park','公園','공원'],['Line','線','노선'],
    ['Entrance','入口','입구'],['Exit','出口','출구'],['Gate','入口','입구'],
    ['East','東','동쪽'],['West','西','서쪽'],['North','北','북쪽'],['South','南','남쪽']];
  const escaped=words.map(row=>row[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  return en ? en.replace(new RegExp('\\b('+escaped.join('|')+')\\b','gi'),match=>{
    const row=words.find(row=>row[0].toLowerCase()===match.toLowerCase());return row[locale==='ja'?1:2];
  }) : zh;
}
function offlineField(point,base,locale,kind='') {
  const native=point?.[`${base}_${locale}`],zh=point?.[`${base}_zh`];
  const bound=point?.[`${base}_${locale}_for_zh`];
  if((locale==='ja' || locale==='ko') && typeof native==='string' && native.trim() && (!bound || bound===zh)) return native;
  return offlineNameTranslation(zh,point?.[`${base}_en`],locale,kind);
}
const OFFLINE_WALK_ACTIONS=[
  ['bear right and continue','右前方へ進む','오른쪽 앞 방향으로 이동'],['bear left and continue','左前方へ進む','왼쪽 앞 방향으로 이동'],
  ['bear back-right and continue','右後方へ進む','오른쪽 뒤 방향으로 이동'],['bear back-left and continue','左後方へ進む','왼쪽 뒤 방향으로 이동'],
  ['enter the right-turn lane','右折専用車線へ入る','우회전 전용 차선으로 진입'],['enter the left-turn lane','左折専用車線へ入る','좌회전 전용 차선으로 진입'],
  ['go up the pedestrian overpass','歩道橋を上る','육교로 올라가기'],['go down the pedestrian overpass','歩道橋を下りる','육교에서 내려가기'],
  ['enter the service road','側道へ入る','보조도로로 진입'],['take the stairs up','階段を上る','계단으로 올라가기'],
  ['take the stairs down','階段を下りる','계단으로 내려가기'],['exit the stairs','階段を出る','계단에서 나오기'],
  ['enter the road on the right','右側の道へ入る','오른쪽 도로로 진입'],['enter the road on the left','左側の道へ入る','왼쪽 도로로 진입'],
  ['enter the ramp','連絡路へ入る','연결 도로로 진입'],['arrive at your destination','目的地に到着','목적지에 도착'],
  ['keep right','右側を進む','오른쪽으로 이동'],['keep left','左側を進む','왼쪽으로 이동'],
  ['continue straight','直進','직진'],['go straight','直進','직진'],['turn right','右折','우회전'],['turn left','左折','좌회전'],
];
function offlineWalkNote(walk,locale) {
  if(locale!=='ja' && locale!=='ko') return walk.note_en || '';
  if(walk[`note_${locale}`]) return walk[`note_${locale}`];
  const pick=(ja,ko)=>locale==='ja' ? ja : ko;
  const known=offlineKnownName(walk.note_zh,walk.note_en,locale);if(known) return known;
  function action(text) {
    const row=OFFLINE_WALK_ACTIONS.find(row=>row[0].toLowerCase()===text.toLowerCase());
    if(row) return row[locale==='ja' ? 1 : 2];
    const prefix=OFFLINE_WALK_ACTIONS.find(row=>text.toLowerCase().startsWith(row[0]+' and '));
    if(prefix) {const rest=action(text.slice(prefix[0].length+5));return rest ? prefix[locale==='ja'?1:2]+pick('、',' 후 ')+rest : null;}
    const reach=/^reach (.+)$/.exec(text);return reach ? offlineNameTranslation('',reach[1],locale)+pick('に到着','에 도착') : null;
  }
  const compass={east:pick('東','동쪽'),west:pick('西','서쪽'),north:pick('北','북쪽'),south:pick('南','남쪽'),
    northeast:pick('北東','북동쪽'),northwest:pick('北西','북서쪽'),southeast:pick('南東','남동쪽'),southwest:pick('南西','남서쪽')};
  function instruction(text) {
    const match=/^Walk (\d+) m(?: (northeast|northwest|southeast|southwest|east|west|north|south))?(?: along (.+?))?(?:, (.+)| to (.+))?$/i.exec(text);
    if(!match) return action(text);
    const [,distance,direction,road,turn,arrival]=match;
    const name=road ? offlineNameTranslation('',road,locale) : '';
    const tail=turn || arrival ? action(turn || arrival) : '';
    if((turn || arrival) && !tail) return null;
    return (road ? pick(`${name}に沿って`,`${name}을 따라 `) : '')+
      (direction ? compass[direction.toLowerCase()]+pick('へ','으로 ') : '')+
      pick(`${distance}m歩く`,`${distance}m 걷기`)+(tail ? pick('、',' 후 ')+tail : '');
  }
  const pieces=String(walk.note_en || '').split(/;\s*/).filter(Boolean).map(instruction);
  return pieces.length && pieces.every(Boolean) ? pieces.join(pick('；','; ')) : walk.note_zh || '';
}
function offlineNames(point, fallback='',locale=offlineCurrentLanguage()) {
  const names=[point?.name_zh,offlineField(point,'name',offlineLocale(locale),point?.kind)].filter(Boolean);
  return escapeOffline([...new Set(names)].join(' / ') || fallback);
}
/* 线路行以「线路名」为主：只在确实像线路号时才带出短号（2、18、10A），
   三方主键（如 900000160000）与已经出现在名称里的号码都不显示；老包没有 code 也不受影响。 */
function offlineLineCode(line) {
  const code=String(line?.code ?? '').trim();
  return /^[0-9]{1,4}[A-Za-z]?$/.test(code) ? code : '';
}
function offlineLineLabel(line,lineLabel='',locale=offlineCurrentLanguage()) {
  const name=offlineNames(line,'',locale),code=offlineLineCode(line);
  if (name) return name + (code && !name.includes(code) ? ` · ${escapeOffline(code)}` : '');
  return code ? `${lineLabel} ${escapeOffline(code)}`.trim() : null;
}
function offlineDirection(line,locale=offlineCurrentLanguage()) {
  const names=[line?.direction_zh,offlineField(line,'direction',offlineLocale(locale))].filter(Boolean);
  return names.length ? escapeOffline([...new Set(names)].join(' / ')) : '';
}
function offlineTime(seconds,dayDate) {
  if (!Number.isFinite(seconds)) return null;
  const date=new Date(seconds*1000);
  const time=date.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Shanghai'});
  const actualDate=date.toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});
  return dayDate && actualDate!==dayDate ? `${actualDate} ${time}` : time;
}
function offlineStopHTML(stop,locale,final=false,dayDate=null) {
  const l=key=>escapeOffline(offlineLabel(key,locale));
  let html=`<article class="offline-stop"><h3 data-i18n-ignore>${offlineNames(stop,l('unavailable'),locale)}</h3>`;
  const type=stop.stop_type==='hotel' ? stop.hotel_stay_kind==='rest' ? 'rest' : 'overnight' : stop.stop_type==='poi' ? 'poi' : stop.stop_type==='gateway' ? 'gateway' : 'unavailable';
  if (!final) html+=`<p class="offline-type">${l(type)}${Number.isFinite(stop.planned_dwell_minutes) ? ` · ${l('stay')} ${escapeOffline(stop.planned_dwell_minutes)} ${l('minutes')}` : ''}</p>`;
  const arrival=offlineTime(stop.arrival_at,dayDate),departure=offlineTime(stop.departure_at,dayDate);
  if (!final) html+=`<p>${arrival ? `${l('arrival')} <time>${arrival}</time>` : l('arrivalUnknown')}${departure ? ` · ${l('departure')} <time>${departure}</time>` : ''}</p>`;
  if (stop.mode) html+=`<p>${l('mode')}: ${OFFLINE_LABELS[stop.mode] ? l(stop.mode) : escapeOffline(stop.mode)}${Number.isFinite(stop.duration_seconds) ? ` · ${l('duration')} ${escapeOffline(Math.ceil(stop.duration_seconds/60))} ${l('minutes')}` : ''}</p>`;
  if (stop.from || stop.to) html+=`<p data-i18n-ignore>${offlineNames(stop.from,'',locale)} → ${offlineNames(stop.to,'',locale)}</p>`;
  if (stop.data_source==='mock') html+=`<p class="offline-warning"><b>${l('demo')}</b></p>`;
  else if (stop.data_source) html+=`<p class="offline-muted">${l('source')}: ${escapeOffline(stop.data_source)}</p>`;
  if (stop.stations?.length) {
    html+=`<h4>${l('station')}</h4><ul>`;
    for (const station of stop.stations) {
      html+=`<li><strong data-i18n-ignore>${offlineNames(station,'',locale)}</strong>`;
      for (const line of station.lines || []) {
        const color=/^#[0-9a-f]{6}$/i.test(line.color_hex || '') ? line.color_hex : '#50696d';
        const label=offlineLineLabel(line,l('line'),locale),toward=offlineDirection(line,locale);
        if (!label) continue;
        html+=`<p class="offline-line"><span class="offline-line-color" style="background:${color}"></span><span data-i18n-ignore>${label}</span></p>`;
        if (toward) html+=`<p class="offline-line-direction" data-i18n-ignore>${toward}</p>`;
      }
      for (const access of station.access_points || []) html+=`<p>${l('access')} ${escapeOffline(access.access_no)} · <span data-i18n-ignore>${offlineNames(access,'',locale)}</span></p>`;
      html+='</li>';
    }
    html+='</ul>';
  }
  if (stop.walk_segments?.length) {
    html+=`<h4>${l('walking')}</h4><ul>`;
    for (const walk of stop.walk_segments) {
      const note=offlineWalkNote(walk,locale);
      html+=`<li>${l(walk.kind==='transfer' ? 'transfer' : 'walk')}${Number.isFinite(walk.distance_meters) ? ` · ${escapeOffline(walk.distance_meters)} ${l('meters')}` : ''}<p data-i18n-ignore>${escapeOffline(walk.note_zh || '')}${walk.note_zh && note && note!==walk.note_zh ? '<br>'+escapeOffline(note) : !walk.note_zh ? escapeOffline(note) : ''}</p></li>`;
    }
    html+='</ul>';
  }
  html+=`<h4>${l('ask')}</h4>`;
  let count=0;
  for (const card of stop.ask_cards || []) {
    const text=askCardText(card,locale);if (!text) continue;count++;
    html+=`<div class="ask" data-i18n-ignore><p lang="zh-CN">${escapeOffline(text.zh)}</p><p lang="${text.language}">${escapeOffline(text.local)}</p></div>`;
  }
  if (!count) html+=`<p class="offline-muted">${l('noCards')}</p>`;
  return html+'</article>';
}
function offlineContent(pkg, locale=offlineCurrentLanguage(), now=Math.floor(Date.now()/1000)) {
  locale=offlineLocale(locale);const l=key=>escapeOffline(offlineLabel(key,locale));
  const ttl=Number.isFinite(pkg.ttl_hours) && pkg.ttl_hours>0 ? pkg.ttl_hours : 24;
  const generated=Number.isFinite(pkg.generated_at) ? new Date(pkg.generated_at*1000).toLocaleString(locale,{timeZone:'Asia/Shanghai',hour12:false}) : offlineLabel('unavailable',locale);
  let html=`<div class="offline-document" lang="${locale}" data-i18n-ignore><header><h1>${l('title')}</h1><p>${l('version')} ${escapeOffline(pkg.trip_version)} · ${l('generated')} ${escapeOffline(generated)} · ${l('validity')} ${ttl} ${l('hours')}</p><p>${l('timezone')}</p><p class="offline-muted">${l('note')}</p></header>`;
  if (!Number.isFinite(pkg.generated_at) || now-pkg.generated_at>ttl*3600) html+=`<p class="offline-warning">${l('stale')}</p>`;
  const report=pkg.payload?.translation_report;
  if (report && report.status!=='complete') {
    html+=`<aside class="offline-warning"><strong>${l(report.status==='missing'?'namesMissing':'namesReview')}</strong><p>${l('namesNote')}</p><ul>`;
    for(const item of report.items || []) html+=`<li>${escapeOffline(item.name_zh)}${item.name_en ? ' / '+escapeOffline(item.name_en) : ''}</li>`;
    html+='</ul></aside>';
  }
  const days=pkg.payload?.days || [];
  const dayLabel=index=>locale==='ja' ? `${index}日目` : locale==='ko' ? `${index}일차` : `Day ${index}`;
  html+='<nav class="offline-days" aria-label="Days">'+days.map(day=>`<a href="#offline-day-${escapeOffline(day.day_index)}">${escapeOffline(dayLabel(day.day_index))}</a>`).join('')+'</nav>';
  for (const day of days) {
    html+=`<section class="offline-day" id="offline-day-${escapeOffline(day.day_index)}"><h2>${escapeOffline(dayLabel(day.day_index))} · ${escapeOffline(day.date)}</h2>`;
    if (day.daily_start_local) html+=`<p>${l('dailyStart')}: ${escapeOffline(day.daily_start_local)}</p>`;
    if(day.start_anchor || day.end_anchor) html+=`<p>${l('start')}<span data-i18n-ignore>${offlineNames(day.start_anchor,offlineLabel('unknown',locale),locale)}</span> → ${l('end')}<span data-i18n-ignore>${offlineNames(day.end_anchor,offlineLabel('unknown',locale),locale)}</span></p>`;
    for (const stop of day.stops || []) html+=offlineStopHTML(stop,locale,false,day.date);
    if (!(day.stops || []).length) html+=`<p>${l('empty')}</p>`;
    html+=`<h3>${l('final')}</h3>`;
    if (day.end_transfer) html+=offlineStopHTML(day.end_transfer,locale,true);
    else html+=`<p class="${day.end_transfer_required===false ? 'offline-muted' : 'offline-warning'}">${l(day.end_transfer_required===false ? 'finalNone' : 'finalMissing')}</p>`;
    html+='</section>';
  }
  return html+'</div>';
}
function offlineDocument(pkg,locale=offlineCurrentLanguage()) {
  locale=offlineLocale(locale);
  return `<!doctype html><html lang="${locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>${escapeOffline(offlineLabel('title',locale))}</title><style>body{font:16px/1.7 system-ui,sans-serif;margin:0;background:#f4f8f6;color:#203b40}main{max-width:880px;margin:auto;padding:24px 16px}h1{font-size:28px;line-height:1.3}h2{margin-top:32px}h4{margin-bottom:8px}p{overflow-wrap:anywhere}.offline-stop{border:1px solid #d8e3df;border-radius:14px;padding:20px;margin:16px 0;background:white}.offline-stop h3{margin-top:0}.offline-muted{color:#50696d;font-size:14px}.offline-warning{background:#fff1d8;color:#79501d;border-radius:10px;padding:14px}.offline-days{display:flex;flex-wrap:wrap;gap:8px}.offline-days a{color:#2d5b63;padding:6px 12px;border:1px solid #bdcfca;border-radius:8px;text-decoration:none}.ask{padding:14px;background:#e5f1ed;border-radius:10px;margin:12px 0}.ask p{margin:4px 0;font-size:22px}.offline-line-color{display:inline-block;width:12px;height:12px;margin-right:8px;border-radius:50%}.offline-line{margin:6px 0}.offline-line-direction{color:#50696d;font-size:14px;margin:2px 0 8px}li p{margin:4px 0}time{font-weight:600}@media(max-width:480px){.offline-stop{padding:14px}.ask p{font-size:19px}h1{font-size:24px}}@media print{body{background:white}.offline-days{display:none}.offline-stop{break-inside:avoid}main{max-width:none;padding:0}.ask{border:1px solid #bdcfca}}</style></head><body><main>${offlineContent(pkg,locale)}</main></body></html>`;
}
