# InboundRoute PRD 数据架构审查报告（第 2 章 / 4.1 / 4.2 + 全文被引用字段）

审查对象：`新建 DOCX 文档.docx`（V1.0.0-Release，研发就绪）— 只读解析，未修改。
提取产物：`_prd_text.txt`（由 `_extract_docx.py` 解析 `word/document.xml` 生成）。

---

## 一、最关键问题摘要（Top 5）

1. **`closure_days` 取值域未定义，最"硬"的规则建立在空数组上。** Rule-01「检查 $Date(Day_n)$ 对应的星期，若与目标 POI 的 `closure_days` 集合匹配」，4.1 实际值 `[]`，无元素类型、无节假日例外、无临时闭馆。
2. **示例 JSON 自相矛盾。** `anchor_arrival.timestamp = 1789728000` = 2026-09-18 18:40 (UTC+8，星期六)，而 `days[0].date = "2026-10-12"`（星期一），差 24 天；`target_arrival_time = "19:30"` 与 `activity_start_time`（= timestamp+5400s）脱节；同一示例并存 epoch 秒 / `YYYY-MM-DD` / `HH:mm` 三种时间，全文无时区字段。
3. **第 2 章承诺的「Curated Stations (核心站台库)」在 4 章无实体定义**，而 3.5/3.6 直接消费「Enter via: Entrance 2 (2号口)」「Exit via: Exit 7 (7号口)」「Line 2 (Green)」等站台库语义。
4. **坐标系与精度责任归属完全缺失**（无 WGS84/GCJ-02/BD-09 声明），却要求"后端强制重映射"落客点。
5. **RouteSegment 不存在**：3.4 要求三模态对比（费用区间、拥堵等级、步数），数据模型只有 `mode/duration_seconds/cost_cny/transfer_count/has_long_transfer`。

---

## 二、字段完整性与规则引用一致性

**[严重度: 阻断] `walking_distance`、`drop_off_locations`、`T_light` 被规则引用但未进字典**
—— 依据：3.5「若三方 API 返回的换乘步行段 `walking_distance ≥ 200 m`……明确打印：Long Transfer: ~X meters」；3.5「后端强制将其重映射至地图 API 的 `drop_off_locations` 推荐停靠点」；Rule-02 引用 `light_up_required` 与 `T_light`，而 4.1 只有 `light_up_schedule` 对象。
—— 影响：POI & Rules Engine 与 Route Adapter 输入契约不存在；`has_long_transfer` 无判定输入；落客纠偏结果无处落库；`T_light` 与 `light_up_schedule` 无换算定义。
—— 建议补全：`transit_from_previous` 增 `walking_distance_m`(integer, 米)、`walking_baseline_seconds`(integer)、`long_transfer_threshold_m`(integer, 默认200)、`transfer`(object: `at_station_id`,`from_line`,`to_line`,`transfer_min_minutes`,`transfer_max_minutes`,`is_in_station_transfer`(boolean),`entrance_no`,`exit_no`,`source`(enum: api|station_library|estimated))；POIMaster 的 `suggested_drop_off_coordinate`(单值) 改为 `drop_off_locations`(array: {coordinate{lat,lng}, desc_zh, desc_en, source, verified_at, confidence})。

**[严重度: 阻断] Curated Stations 无实体，界面直接消费其字段**
—— 依据：第 2 章「- Curated Stations (核心站台库)」；3.5「Enter via: Entrance 2 (2号口)」「Exit via: Exit 7 (7号口)」「Ride 2 stops (3 mins) ➔ Arrive at Zhongshan Park (中山公园)」「Take indoor escalators」「Estimated transfer time: 6-8 mins」；3.6「精确包含中英双语的站名、线号、进出站口编号」。
—— 影响：进出站口编号、线号配色、行车方向名普遍不在三方路线规划稳定返回中；双语问路卡、离线单、换乘预警不可靠。
—— 建议补全：新增 `CuratedStation`：`station_id`(string PK)、`name_zh`/`name_en`、`line_code`(string)、`line_color_hex`(string)、`operator`(string)、`platform_direction_zh`/`_en`、`entrances`(array<{entrance_no, name_en, name_zh, lat, lng, landmark_desc_en, landmark_desc_zh, is_barrier_free}>)、`exits`(同构)、`interior_transfer_minutes`({min:int,max:int,escalator_note_en})、`vertical_gap_note_en`(string)、`station_group_id`(string 换乘站聚合)、`source`(string)、`updated_at`(timestamp)。

**[严重度: 高] 实体中定义但没有来源的字段**
—— 依据：4.2 `anchor_hotel` 无 poi_id 却要「自动设定为每日固定起点」；4.1 `suggested_drop_off_coordinate` 带人工 `desc_zh`/`desc_en`；4.2 `walking_speed_factor: 1.0` 对应 3.1「加权系数设为 1.3」。
—— 影响：派生值/可覆写值无定义；人工数据无维护方与审核状态；酒店无可引用主键，次日回酒店终点无法表达。
—— 建议补全：POIMaster 增 `data_source`(enum: amap|tencent|baidu|manual_curated)、`source_poi_id`(string)、`verified_by`(string)、`verified_at`(timestamp)、`confidence`(enum: official|curated|crowd)；`anchor_hotel` 增 `hotel_poi_id`(string FK)、`coordinate_system`(string)。

**[严重度: 中] 分类体系缺失（Rule-04 的 #ClassicalGarden/#Temple 无落点）**
—— 依据：Rule-04「相同二级分类标签（如 #ClassicalGarden 或 #Temple）的 POI 计数 ≥ 3」；4.1 `"category": "Modern Skyline", "sub_category": "Riverwalk"`；3.1 Interests 枚举。
—— 影响：无枚举/字典/映射，规则无法统计；分类无法多语言化。
—— 建议补全：新增 `POICategory`(`category_code` PK、`parent_code`、`level`(1|2)、多语言 `names`) 与 `POITag`(多对多)；POIMaster 改 `category_code` + `tag_codes`(array<string>)。

**[严重度: 中] 字典不完整（示例独有的字段无类型定义）**
—— 依据：4.2 的 `activity_start_time`、`ordered_stops`、`stop_order`、`planned_dwell_minutes`、`day_index` 无类型/必填/取值定义；反向：3.1 的 Destination City / Duration / Interests 在 4.2 无对应字段。
—— 建议补全：TripInstance 增 `destination_city`(string, 一期 CN-SH)、`duration_days`(int 1-15)、`interests`(array<enum>)、`local_timezone`(string IANA)、`utc_offset_minutes`(int)；`days[]` 明确 `day_index`(int 从1)、`date`(本地日历日)、`ordered_stops`(有序数组)；stop 明确 `stop_order`(int 从1)、`planned_dwell_minutes`(int >0)。

---

## 三、类型与格式歧义

**[严重度: 阻断] 时间四种表达混用、无时区基准、示例自相矛盾**
—— 依据：`"timestamp": 1789728000`、`"activity_start_time": 1789733400`、`"date": "2026-10-12"`、`"target_arrival_time": "19:30"`、`"standard_opening_hours": "00:00 - 24:00"`；目标用户为海外游客但无 `local_timezone`。
—— 影响：跨类型比较不可比；UTC 日界错一天；实测 timestamp=2026-09-18T18:40+08:00 与 date=2026-10-12 相差 24 天；`+90min` 缓冲在 timestamp/activity_start_time 间成立（差值 5400s），反证 `date`、`target_arrival_time` 与之脱节。
—— 建议补全：统一 `*_at`(timestamp, 全文统一秒或毫秒) + `*_local`(ISO 8601 带偏移)；`target_arrival_time` → `target_arrival_at`(timestamp) + `target_arrival_local`(string)；`days[].date` 增加 `date_timezone`；新增"时间语义约定"小节。

**[严重度: 高] 单串营业时间无法表达多时段/午休/按星期差异**
—— 依据：`"standard_opening_hours": "00:00 - 24:00"`；3.2「Opening & Closure：标明常规营业时间及特殊闭馆规律（如 Closed on Mondays）」「Last Entry：明确截止入场时间（如 16:00 Last Entry）」。
—— 影响：无法表达"周二至周日 09:00–17:00、16:00 停止入场、周一闭馆（法定节假日除外）"；`last_entry_time: null` 无法区分"不适用"与"未知"；无预约制/限流字段（故宫、国博类场馆直接决定可行性）。
—— 建议补全：`opening_hours`(array<{days_of_week: array<int 1-7>, periods: array<{open:"HH:mm", close:"HH:mm", cross_midnight:boolean}>, seasonal_label: string|null}>)、`last_entry`({time, applies_to, date_from, date_to, note_en, note_zh})、`hours_uncertain`(boolean)、`reservation_required`(boolean)、`reservation_channel`(string)、`advance_booking_days`(int)、`daily_capacity_limited`(boolean)。

**[严重度: 阻断] `closure_days` 取值域未定义，无节假日/临时闭馆表达**
—— 依据：`"closure_days": []`；Rule-01「若与目标 POI 的 `closure_days` 集合匹配」；响应文案硬编码「is officially closed on Mondays.」；3.1「重点文博机构"周一闭馆"硬约束」。
—— 影响：硬阻断无法实现；四类缺口：元素类型未定、"法定节假日除外"无法表达、临时闭馆无字段、调休/顺延无处理。示例将 closure_days 为空的"外滩"与星期几文案绑死，暴露了不存在的取值约定。
—— 建议补全：拆 `weekly_closed_days`(array<int ISO 1-7>)、`holiday_exceptions`(array<{date, status: closed|open, name_en, name_zh}>)、`temporary_closures`(array<{date_from, date_to, reason_en, reason_zh, source, announced_at}>)；新增 `HolidayCalendar`(`date` PK、`region_code`、`holiday_name_en/zh`、`is_public_holiday`(boolean)、`is_adjusted_workday`(boolean))；增 `closure_data_version`、`closure_verified_at`。

**[严重度: 高] `light_up_schedule` 固定季节键，Rule-02 的"当前季节"无判定规则**
—— 依据：`"light_up_schedule": { "summer": "19:00 - 23:00", "winter": "18:00 - 22:00" }`；Rule-02「早于当前季节亮灯时间点 $T_{light}$」；3.2「19:00 - 22:00 (Summer)」。
—— 影响：季节判定规则未定义；无春秋过渡；年度公告变更无法表达；文档两处窗口不一致（19:00-23:00 vs 19:00-22:00）。
—— 建议补全：`light_up`({`required`:boolean, `windows`:array<{date_from:"MM-DD",date_to:"MM-DD",start:"HH:mm",end:"HH:mm",year:int|null,note_en,note_zh}>, `season_rule`(enum: fixed_dates|meteorological|official_notice), `verified_at`, `source`})。

**[严重度: 阻断] 坐标系未声明，转换责任未定义**
—— 依据：`"coordinate": { "lat": 31.2397, "lng": 121.4900 }`；1.3「基于主流成熟地图 API（高德/腾讯/百度 Web 服务）」；1.2「海外地图由于坐标偏移和公共交通数据脱节」；3.5「后端强制将其重映射」。
—— 影响：GCJ-02/BD-09/WGS84 混用造成 100–600m 偏差，直接毁掉"落客点纠偏"与"最后 300m 步行"；4 位小数（≈11m）精度是否足够未声明。
—— 建议补全：POIMaster 增 `coordinate_system`(enum: WGS84|GCJ-02|BD-09)、`coordinate_precision`(int, POI 入口点建议 ≥6)；全局约定"内部主数据统一 WGS84、入口点级精度、由 Route Adapter 单向转换"，所有落库坐标必须带 `coordinate_system` + `coord_source`(enum: gps|amap|tencent|baidu|manual)。

**[严重度: 中] `mode` 与费用/单位语义不完整**
—— 依据：`"mode": "transit"`、`"cost_cny": 4.0`；3.4「Taxi/Ride-hailing……预估费用区间、拥堵等级」「Walk/Bike……注明消耗步数」。
—— 建议补全：`mode`(enum: transit|taxi|walk|bike|drive)、`cost`({min,max,currency,per:person|vehicle})、`distance_meters`(int)、`steps_estimate`(int, 仅 walk)、`traffic_level`(enum: unknown|smooth|slow|congested|severe)、`computed`(boolean)、`computed_at`(timestamp)。

---

## 四、标识与关系

**[严重度: 阻断] 缺失实体清单**
—— 依据：第 2 章「User Profiles (偏好画像) / POI Master Data (含闭馆/亮灯) / Curated Stations (核心站台库)」；4.2 内嵌 `user_profile` 却无 `user_id`。
—— 建议补全（最小实体集）：`User`(`user_id` PK, `locale`, `created_at`)、`UserPreference`(`user_id` FK, party/pacing/interests/walking_speed_factor)、`TripInstance`(+`user_id`, `trip_version`, `status`(draft|active|archived), `created_at`, `updated_at`, `data_snapshot_version`)、`TripVersion`(`trip_id`+`version` 复合 PK, `snapshot_json`, `change_reason`)、`RouteSegment`、`CuratedStation`、`POICategory`/`POITag`、`HolidayCalendar`、`POISourceMapping`。

**[严重度: 高] 主外键与一对多/多对多无表达**
—— 依据：`ordered_stops[].poi_id` 无 FK 描述；Rule-04 需日内外同类计数（POI↔tag 多对多）；3.1「自动设定为每日固定起点……及每日最终收敛终点」但 `anchor_hotel` 无 poi 关联；`ordered_stops` 未声明同 POI 可否重复。
—— 建议补全：`TripStop`(`stop_id` PK, `trip_id`+`day_index`+`stop_order` 唯一, `poi_id` FK, `is_anchor`(boolean), `duplicate_of_stop_id`)；`hotel_poi_id`；POIMaster 增 `status`(enum: active|retired|merged) 与 `merged_into_poi_id`。

**[严重度: 高] 无数据版本与更新时间戳（全库 0 个 `updated_at`）**
—— 依据：4.1、4.2 均无 `created_at`/`updated_at`/`version`；3.6 却要求强缓存。
—— 建议补全：POIMaster 增 `data_version`(string)、`created_at`、`updated_at`、`verified_at`；TripInstance 增 `trip_version`(乐观锁)、`created_at`、`updated_at`；各规则子对象带 `source` + `verified_at`。

**[严重度: 高] 多语言仅 en/zh/pinyin 三件套，无日韩扩展方式**
—— 依据：`name_en`/`name_zh`/`name_pinyin`；`desc_zh`/`desc_en`（命名前缀不一致）；`anchor_hotel` 无拼音；`location_name: "Pudong Int'l Airport T2"` 单语自由文本；`name_pinyin: "wài tān"` 带声调。
—— 影响：`name_pinyin` 对 Sensō-ji/景福宫类失效；无转写标准（Hepburn/Revised Romanization）、无繁体承载位、检索无无声调归一化字段。
—— 建议补全：`names`({`zh-Hans`,`zh-Hant`,`en`,`ja`,`ko`})、`romanization`({`pinyin`(带声调展示),`pinyin_plain`(检索),`ja_romaji`,`ko_rr`})、`display_priority`(array<string>)、`search_aliases`(array<string>)；`desc_zh`/`desc_en` 并入同一命名规范。

---

## 五、持久化与一致性

**[严重度: 阻断] 第三方 `poi_id` 与内部 `poi_id` 映射责任未定义**
—— 依据：`"poi_id": "sh_poi_00042"`（内部风格，`sh_` 前缀无约定）；外部服务含「地图逆地理编码 (Reverse Geo)」；3.1「支持输入英文/拼音检索，反查确定经纬度」。
—— 建议补全：`POISourceMapping`(`internal_poi_id` FK, `provider` enum, `provider_poi_id`, `match_confidence`, `match_method`(enum: id|geo_name|manual), `verified_at`)；匹配优先级：ID 精确 → 名称+坐标 ≤50m → 人工；三方结果必须经 Route Adapter 归一化后落库。

**[严重度: 高] 离线包无快照版本与失效策略、降级不可表达**
—— 依据：3.6「LocalStorage / IndexedDB 进行本地强缓存」；NFR「≤ 5 MB……ServiceWorker」；NFR「自动降级返回点对点直线距离粗算」。
—— 建议补全：`OfflinePackage`(`package_id` PK, `trip_id` FK, `trip_version`, `poi_data_version`, `generated_at`, `expires_at`, `includes`(array<enum>), `size_bytes`, `checksum`)；`transit_from_previous` 增 `data_quality`(enum: live_api|cached|degraded_straight_line)、`degraded_reason`(string)；POIMaster 增 `cache_ttl_seconds`(int，按规则类型区分)。

**[严重度: 中] 无缓存键，"拖拽重算 ≤1.2s" 无支撑**
—— 依据：NFR「用户拖拽改变日程顺序后，微观路线重新计算与刷新响应耗时 ≤ 1.2 s」；3.3 需重跑 Rule-01~04。
—— 建议补全：`RouteSegment` 增 `cache_key`(hash of from/to/mode/depart_window/engine_version)、`expires_at`、`hit_source`(enum: cache|api)；服务层 `engine_version`(string) 随快照持久化。

---

## 六、三方依赖的契约风险

**[严重度: 阻断] 换乘预警与进出站口寄托在三方返回**
—— 依据：3.5「若三方 API 返回的换乘步行段 `walking_distance ≥ 200 m`」「Enter via: Entrance 2 (2号口)」「Exit via: Exit 7 (7号口)」「Take indoor escalators」「Estimated transfer time: 6-8 mins」。
—— 影响：换乘步行距离常需自行求和并区分站内/站外；进出站口编号通常不在返回中；"6-8 mins"区间与单值 `duration_seconds` 不兼容。
—— 建议补全：换乘语义落 CuratedStation + 与三方 `station_name`+`line` 映射；`transfer` 字段组（见第二节）；`walking_distance_m` 缺失时 `source="estimated"` 且不触发红色预警。

**[严重度: 高] 落客点纠偏寄托在"地图 API 的 `drop_off_locations`"**
—— 依据：3.5「后端强制将其重映射至地图 API 的 `drop_off_locations` 推荐停靠点」。
—— 建议补全：双轨制——优先三方可得的推荐上下车点（需实测），否则回退 POIMaster 人工维护的 `drop_off_locations`（带 `source`/`verified_at`/`confidence`）；"禁停违章区规避"记为人工规则而非 API 语义。

**[严重度: 高] 公共交通实时性寄托在"官方公共交通实时数据接口"**
—— 依据：第 2 章「- 官方公共交通实时数据接口」；3.5 全部微观解析。
—— 建议补全：数据层增 `realtime_available`(boolean)、`realtime_freshness_seconds`(int)、`schedule_type`(enum: realtime|static_timetable|cached)；降级链 realtime → static_timetable → 直线粗算。

**[严重度: 中] 费用与拥堵等级无缺失表达**
—— 依据：3.4「费用」「预估费用区间、拥堵等级」；`"cost_cny": 4.0`。
—— 建议补全：`cost` 结构化，缺失写 `null` + `cost_estimated`(boolean)；`traffic_level` 统一枚举 + `traffic_level_source_raw`(string)；Route Adapter 内维护各厂商枚举映射表。

**[严重度: 中] 示例 JSON 与规则/日历不自洽**
—— 依据：`timestamp` 与 `date` 相差 24 天；Rule-01 文案硬编码 Mondays 而示例 `closure_days: []`；`"standard_opening_hours": "00:00 - 24:00"` + `is_enclosed_attraction: false` 用于"外滩"。
—— 建议补全：修正为单一时间基准（`date`="2026-10-12" 与 timestamp 对齐，`target_arrival_time` 晚于 `activity_start_time`）；补两个示例 POI（一个 `weekly_closed_days:[1]`+`is_enclosed_attraction:true`+`last_entry` 有值；一个 `light_up.required:true` 且 `windows` 有 `date_from/date_to`）；声明"示例 JSON 为字段类型与取值域的规范性基准"。

---

## 七、需与三方地图服务核实的能力清单

1. 公交路径规划是否返回换乘段的独立步行距离字段（支撑 `walking_distance ≥ 200m` 预警）；若仅步骤级 `distance`，是否需自行求和、能否区分站内/站外换乘。
2. 是否返回轨道交通进出站口编号/名称及出口至站厅步行距离；若否，确认自建站台库的最小字段集。
3. 是否返回推荐上车点/下车点，是否存在等价于 `drop_off_locations` 的字段；其为"推荐"还是"禁停规避"，覆盖城市与 POI 类型范围。
4. 是否返回公交线路配色/简称（如 `Line 2 (Green)`）与行车方向名称（如"往浦东国际机场方向"）及其多语言形式。
5. 打车预估是否返回费用区间、是否分时段（高峰/夜间）与车型、单人/整车口径、是否含起步价与附加费。
6. 拥堵等级的返回形式（枚举/指数/时长膨胀系数/文本路况），枚举全集与含义，用于 `traffic_level` 映射。
7. 路况影响是否已体现在 `duration` 中（避免二次加权放大）。
8. 步行/骑行是否返回步数或可用于估算步数的距离。
9. 实时公交/地铁到站数据：覆盖城市、更新频率、企业资质与实名要求、日配额与 QPS、失败返回码语义。
10. 各服务入参/出参坐标系（GCJ-02/BD-09），是否提供官方转换能力，是否存在 `input/output_coordinate_type` 参数。
11. 逆地理编码粒度：是否返回"路口/门牌/建筑入口"级描述、POI 英文名与别名。
12. POI 检索是否返回稳定唯一 ID（可跨会话映射内部 `poi_id`），ID 是否随数据更新变化；POI 分类编码能否映射内部 `category_code`。
13. 配额与商用条款：日调用上限、并发上限、结果可否长期落库缓存（离线包依赖）。
14. 公交多语言：站名/线路名是否提供中英双语；若无，内部翻译与拼音生成的合规与准确性来源。

---

## 八、边界说明

- 本次仅审数据与架构严谨性，未评估 UI 交互与视觉规范。
- 第 5 章 NFR 仅在涉及数据层处（离线包版本、降级表达、缓存键）纳入。
- 原 DOCX 为只读审查，未做任何修改。
