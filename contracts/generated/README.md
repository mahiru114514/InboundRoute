# 字段表（自动生成）

> 所有 *_at 为 UTC 秒；date 为 Asia/Shanghai 日期；*_local 为同日时刻。见 contracts/TIME_BASELINE.md
>
> 本文件由 contracts/scripts/generate.py 从 schemas/*.schema.json 生成，请勿手改。

## POIMaster（`schemas/poi.schema.json`）

| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `description_zh` | string | 否 |  |  | 简短中文介绍，概述主要看点及游玩方式；可选以兼容旧数据，缺失时由页面提示简介待补充。 |
| `poi_id` | string | 是 |  | ^[a-z]{2}_poi_[0-9]{5,8}$ | 内部 ID，稳定不变；三方映射见 provider_refs。 |
| `names` | object | 是 |  |  | 多语言名称。PRD 只有 en/zh/pinyin 三件套，日语场景（Sensō-ji）会失效，故改为语言映射。 |
| `names.zh-Hans` | string | 是 |  |  |  |
| `names.zh-Hant` | string | 否 |  |  |  |
| `names.en` | string | 是 |  |  |  |
| `names.ja` | string | 否 |  |  |  |
| `names.ko` | string | 否 |  |  |  |
| `romanization` | object | 否 |  |  | PRD 的 name_pinyin 带声调（wài tān）无法用于检索匹配，故拆为两套。 |
| `romanization.pinyin` | string | 是 |  |  | 带声调，用于现场路牌比对展示 |
| `romanization.pinyin_plain` | string | 是 |  |  | 无声调，用于检索匹配 |
| `romanization.ja_romaji` | string | 否 |  |  |  |
| `romanization.ko_rr` | string | 否 |  |  |  |
| `search_aliases` | array | 否 | [] |  |  |
| `category` | object | 是 |  |  | 三级分类字典。PRD 只有自由字符串，Rule-04 因此无法统计。 |
| `category.level1` | string | 是 |  | modern_skyline, history_culture, local_life, nature, transport_hub, other |  |
| `category.level2` | string | 是 |  |  | 受 mappings.json 的 category_taxonomy 约束，枚举值以该文件为准（Rule-04 按此计数）。 |
| `category.label_en` | string | 是 |  |  |  |
| `category.label_zh` | string | 是 |  |  |  |
| `coordinate` |  | 是 |  |  |  |
| `drop_off_locations` | array | 否 | [] |  | PRD 的 suggested_drop_off_coordinate 单值改为数组，以表达多入口/多停靠点与来源优先级。 |
| `drop_off_locations[].point` |  | 是 |  |  |  |
| `drop_off_locations[].desc_zh` | string | 是 |  |  |  |
| `drop_off_locations[].desc_en` | string | 是 |  |  |  |
| `drop_off_locations[].source` |  | 是 |  |  |  |
| `drop_off_locations[].priority` | integer | 是 |  |  | 1 最高；人工(curated/manual) 优先于三方(api) |
| `drop_off_locations[].verified_at` | integer | 否 |  |  | UTC 秒 |
| `drop_off_locations[].note_zh` | string | 否 |  |  |  |
| `drop_off_locations[].note_en` | string | 否 |  |  |  |
| `operating_rules` | object | 是 |  |  |  |
| `operating_rules.opening_hours` | array | 是 |  |  | 结构化时段。PRD 的自由字符串无法表达午休、按星期差异、旺季调整。 |
| `operating_rules.opening_hours[].weekdays` | array | 否 | [1, 2, 3, 4, 5, 6, 7] |  |  |
| `operating_rules.opening_hours[].date_from` | string | 否 |  | ^\d{2}-\d{2}$ |  |
| `operating_rules.opening_hours[].date_to` | string | 否 |  | ^\d{2}-\d{2}$ |  |
| `operating_rules.opening_hours[].open` | string | 是 |  | ^([01]\d|2[0-3]):[0-5]\d$ |  |
| `operating_rules.opening_hours[].close` | string | 是 |  | ^([01]\d|2[0-3]):[0-5]\d$ |  |
| `operating_rules.opening_hours[].close_next_day` | boolean | 否 | false |  | close 是否落在次日（如夜场 23:00-02:00） |
| `operating_rules.last_entry_time` | string / null | 否 |  | ^([01]\d|2[0-3]):[0-5]\d$ | 为 null 表示未采集；展示层按 mappings.json 的 null_policy 处理（PRD 承诺展示却给了 null）。 |
| `operating_rules.closure_data_status` | string | 是 | "unknown" | verified, unverified, unknown | PRD 的 closure_days: [] 无法区分「不闭馆」和「未采集」，故显式加此字段。unknown 时 Rule-01 不得静默放行。 |
| `operating_rules.closure_rules` | array | 否 | [] |  |  |
| `operating_rules.closure_rules[].kind` |  | 是 |  |  |  |
| `operating_rules.closure_rules[].weekday` |  | 否 |  |  |  |
| `operating_rules.closure_rules[].date` | string | 否 |  | ^\d{4}-\d{2}-\d{2}$ |  |
| `operating_rules.closure_rules[].date_from` | string | 否 |  | ^\d{4}-\d{2}-\d{2}$ |  |
| `operating_rules.closure_rules[].date_to` | string | 否 |  | ^\d{4}-\d{2}-\d{2}$ |  |
| `operating_rules.closure_rules[].reason_zh` | string | 否 |  |  |  |
| `operating_rules.closure_rules[].reason_en` | string | 否 |  |  |  |
| `operating_rules.closure_rules[].note_zh` | string | 否 |  |  |  |
| `operating_rules.is_enclosed_attraction` | boolean | 是 | false |  | 人工标注字段：有围合检票边界（博物馆/园林）为 true，开放式街区为 false。维护方=数据运营。 |
| `operating_rules.reservation_required` | boolean | 否 | false |  | PRD 完全缺失。故宫/国博类预约制直接决定行程可行性。 |
| `operating_rules.advance_booking_days` | integer / null | 否 | null |  |  |
| `operating_rules.light_up` | object / null | 否 |  |  | PRD 的 light_up_required + light_up_schedule{summer,winter} 无法推出 T_light（区间不是点，且季节切分未定义）。 |
| `operating_rules.light_up.required` | boolean | 是 | false |  |  |
| `operating_rules.light_up.T_light_rule` | string | 否 | "window_start_minus_30" | window_start_minus_30, sunset, window_start | T_light 的取点规则；Rule-02 依赖它。 |
| `operating_rules.light_up.windows` | array | 是 |  |  |  |
| `operating_rules.light_up.windows[].date_from` | string | 是 |  | ^\d{2}-\d{2}$ |  |
| `operating_rules.light_up.windows[].date_to` | string | 是 |  | ^\d{2}-\d{2}$ |  |
| `operating_rules.light_up.windows[].label_zh` | string | 否 |  |  |  |
| `operating_rules.light_up.windows[].label_en` | string | 否 |  |  |  |
| `operating_rules.light_up.windows[].start` | string | 是 |  | ^([01]\d|2[0-3]):[0-5]\d$ |  |
| `operating_rules.light_up.windows[].close` | string | 是 |  | ^([01]\d|2[0-3]):[0-5]\d$ |  |
| `operating_rules.dwell_time` | object | 否 |  |  | PRD 展示区间（1.5-2 Hours）但字段是单值 90 分钟，故显式表达 kind。 |
| `operating_rules.dwell_time.kind` |  | 是 |  |  |  |
| `operating_rules.dwell_time.minutes` | integer | 否 |  |  |  |
| `operating_rules.dwell_time.minutes_min` | integer | 否 |  |  |  |
| `operating_rules.dwell_time.minutes_max` | integer | 否 |  |  |  |
| `provider_refs` | object | 否 |  |  | 缺此映射会无法把三方返回的 POI 关联回内部主数据。 |
| `provider_refs.amap` | string | 否 |  |  |  |
| `provider_refs.tencent` | string | 否 |  |  |  |
| `provider_refs.baidu` | string | 否 |  |  |  |
| `provenance` | object | 是 |  |  |  |
| `provenance.source` |  | 是 |  |  |  |
| `provenance.updated_at` | integer | 是 |  |  | UTC 秒 |
| `provenance.reviewed_by` | string | 否 |  |  |  |
| `provenance.confidence` | number | 否 | 1 |  |  |
| `tags` | array | 否 | [] |  |  |

## TripInstance（`schemas/trip.schema.json`）

| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `budget` | object / null | 否 | null |  | 每人整趟行程预算；null 表示未设置。金额使用整数分。 |
| `budget.scope` | string | 是 |  |  |  |
| `budget.currency` | string | 是 |  |  |  |
| `budget.amount_cents` | integer | 是 |  |  |  |
| `trip_id` | string | 是 |  | ^trip_[0-9a-z]{6,32}$ |  |
| `user_id` | string / null | 否 |  |  | PRD 内嵌 user_profile 但无 user_id，无法做鉴权与越权校验。 |
| `version` | integer | 是 |  |  | 乐观锁 + 离线包过期判定，PRD 缺失。 |
| `status` |  | 是 |  |  |  |
| `timezone` | string | 是 |  |  |  |
| `created_at` | integer | 是 |  |  |  |
| `updated_at` | integer | 是 |  |  |  |
| `user_profile` | object | 是 |  |  |  |
| `user_profile.party_composition` |  | 是 |  |  |  |
| `user_profile.pacing` |  | 是 |  |  |  |
| `user_profile.interests` | array | 否 | [] |  |  |
| `user_profile.walking_speed_factor` | number | 是 | 1.0 |  | 最终生效系数 = walking_speed_factor × party_walk_multiplier（见 mappings.json/weighting）。 |
| `user_profile.party_walk_multiplier` | number | 否 | 1.0 |  | 由 party_composition 派生：family_kids/senior → 1.3，其余 1.0。PRD 只写了「1.3」没说作用对象与叠加方式。 |
| `user_profile.prefer_taxi` | boolean | 否 | false |  | family_kids/senior 时为 true，对应「优先推荐打车模式」。 |
| `anchor_arrival` | object | 是 |  |  |  |
| `anchor_arrival.arrival_at` | integer | 是 |  |  | UTC 秒（PRD 的 timestamp，与 date 矛盾的元凶） |
| `anchor_arrival.location_name` | string | 是 |  |  |  |
| `anchor_arrival.coordinate` |  | 是 |  |  |  |
| `anchor_arrival.activity_start_at` | integer | 是 |  |  | 服务端派生 = arrival_at + 90min；客户端只读 |
| `anchor_arrival.border_buffer_minutes` | integer | 否 | 90 |  |  |
| `anchor_departure` | object / null | 否 | null |  | PRD 缺离境锚点，导致 Day N 最后一段（酒店→机场）无法推演。 |
| `anchor_departure.departure_at` | integer | 是 |  |  |  |
| `anchor_departure.location_name` | string | 是 |  |  |  |
| `anchor_departure.coordinate` |  | 是 |  |  |  |
| `anchor_departure.is_international` | boolean | 否 | true |  |  |
| `anchor_departure.hub_buffer_minutes` | integer | 是 | 180 |  |  |
| `anchor_hotel` | object | 是 |  |  |  |
| `anchor_hotel.name_en` | string | 是 |  |  |  |
| `anchor_hotel.name_zh` | string | 是 |  |  |  |
| `anchor_hotel.name_pinyin` | string | 否 |  |  | PRD 的 anchor_hotel 连拼音都没有 |
| `anchor_hotel.coordinate` |  | 是 |  |  |  |
| `anchor_hotel.poi_id` | string / null | 否 |  |  |  |
| `unassigned_pois` | array | 否 | [] |  | PRD 选了 N 天却只选 M 个点时无「未装载」表示。 |
| `days` | array | 是 |  |  |  |
| `days[].day_index` | integer | 是 |  |  |  |
| `days[].date` | string | 是 |  | ^\d{4}-\d{2}-\d{2}$ | 上海本地日期 |
| `days[].day_status` |  | 是 |  |  |  |
| `days[].daily_start_local` | string | 是 | "09:00" | ^([01]\d|2[0-3]):[0-5]\d$ | 每日独立出发时刻；Day 1 取配置时刻与 anchor_arrival.activity_start_at 的较晚值。 |
| `days[].poi_cap` | integer / null | 否 | null |  | 由 pacing 派生：relaxed=2 / balanced=4 / packed=6 |
| `days[].start_anchor` |  | 否 | null |  | 当日起点；null 时首日用抵达口岸，其余用前一日终点。 |
| `days[].end_anchor` |  | 否 | null |  | 当日终点；null 时使用当前住宿，末日优先离境口岸。显式酒店终点成为后续默认住宿。 |
| `days[].ordered_stops` | array | 是 |  |  |  |
| `days[].ordered_stops[].stop_order` | integer | 是 |  |  |  |
| `days[].ordered_stops[].stop_type` |  | 是 |  |  |  |
| `days[].ordered_stops[].poi_id` | string / null | 否 |  |  |  |
| `days[].ordered_stops[].locked` | boolean | 否 | false |  | 用户手动固定的点，Rule-02 的 Move to Evening 不得移动它。 |
| `days[].ordered_stops[].arrival_at` | integer / null | 否 |  |  | 引擎推算，只读 |
| `days[].ordered_stops[].departure_at` | integer / null | 否 |  |  | 引擎推算 = arrival_at + dwell |
| `days[].ordered_stops[].user_preferred_arrival_local` | string / null | 否 |  | ^([01]\d|2[0-3]):[0-5]\d$ | 用户意愿时刻。与引擎的 arrival_at 并存，不得互相覆盖（PRD 的 target_arrival_time 语义未定义）。 |
| `days[].ordered_stops[].planned_dwell_minutes` | integer | 是 |  |  |  |
| `days[].ordered_stops[].transit_from_previous` |  | 否 |  |  |  |
| `days[].ordered_stops[].rule_notices` | array | 否 | [] |  |  |
| `days[].ordered_stops[].stop_id` | string | 否 |  |  | 稳定停靠点标识；排序、移除、跨天移动使用 |
| `days[].ordered_stops[].name_zh` | string | 否 |  |  |  |
| `days[].ordered_stops[].name_en` | string | 否 |  |  |  |
| `days[].ordered_stops[].name_pinyin` | string | 否 |  |  |  |
| `days[].ordered_stops[].coordinate` |  | 否 |  |  |  |
| `days[].ordered_stops[].hotel_stay_kind` | string | 否 |  | rest, overnight | 酒店停靠用途：rest 为途中休息，不改变后续住宿；overnight 为过夜或换酒店。旧数据缺字段沿用过夜继承。 |
| `days[].is_arrival_day` | boolean | 否 |  |  | 服务端按抵达日期派生，独立于 day_status |
| `days[].end_transit` |  | 否 |  |  |  |
| `revision_history` | array | 否 | [] |  |  |
| `revision_history[].version` | integer | 是 |  |  |  |
| `revision_history[].changed_at` | integer | 是 |  |  |  |
| `revision_history[].operation` | string | 是 |  | create, add_stop, remove_stop, reorder, move_to_evening, change_day, change_anchor, confirm_conflict, unlock_day, update_config |  |
| `revision_history[].target` | string | 否 |  |  |  |
| `resolved_day_points` | object | 否 |  |  | 服务端只读派生每日起终点快照，不持久化 |
| `default_day_points` | object | 否 |  |  | 服务端只读派生每日起终点快照，不持久化 |
| `cost_inputs` | object / null | 否 |  |  |  |
| `cost_inputs.intercity_cents` | integer / null | 否 |  |  |  |
| `cost_inputs.meal_daily_cents` | integer / null | 否 |  |  |  |
| `cost_inputs.extras_cents` | integer / null | 否 |  |  |  |
| `cost_inputs.travelers` | integer / null | 否 |  |  |  |
| `cost_inputs.lodging_rooms` | integer / null | 否 |  |  | 自动住宿估算的房间数；未填写按1间参考估算。 |
| `cost_inputs.taxi_vehicles` | integer / null | 否 |  |  |  |
| `cost_inputs.contingency_percent` | integer | 否 |  |  |  |
| `cost_inputs.itinerary_key` | string | 否 |  |  |  |
| `cost_inputs.ticket_cents` | object | 否 |  |  |  |
| `cost_inputs.meal_overrides` | object | 否 |  |  |  |
| `cost_inputs.lodging_nights` | array / null | 否 |  |  |  |
| `cost_inputs.lodging_nights[].date` | string | 是 |  | ^\d{4}-\d{2}-\d{2}$ |  |
| `cost_inputs.lodging_nights[].hotel_name` | string | 是 |  |  |  |
| `cost_inputs.lodging_nights[].rooms` | integer / null | 是 |  |  |  |
| `cost_inputs.lodging_nights[].room_price_cents` | integer / null | 是 |  |  |  |
| `budget_assessment` | object | 否 |  |  | 动态费用评估，不保存到行程文件；缺失费用不视为免费。 |

## RouteSegment（`schemas/route.schema.json`）

| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `from` |  | 是 |  |  |  |
| `to` |  | 是 |  |  |  |
| `mode` |  | 是 |  |  |  |
| `variants` | array | 否 | [] |  | 3.4 要求「同时展示三组」——三模态统一放在 variants 里，避免客户端为每种模式各写一套结构。 |
| `distance_meters` | integer / null | 是 |  |  | 3.4「距离 ≤3km 高亮」的判定依据，PRD 缺失。 |
| `duration_seconds` | integer / null | 是 |  |  |  |
| `walking_distance_meters` | integer / null | 否 |  |  |  |
| `walking_duration_seconds` | integer / null | 否 |  |  |  |
| `estimated_steps` | integer / null | 否 |  |  |  |
| `transfer_count` | integer / null | 否 |  |  |  |
| `has_long_transfer` | boolean | 否 | false |  | 派生布尔，保留原始值以便展示 「~X meters」。 |
| `long_transfer_threshold_m` | integer | 否 | 200 |  |  |
| `transfer_overhead` | object / null | 否 | null |  | 3.5 的「基础步行耗时上浮 30%」：只存系数不存改写后的值，保证多次重算幂等。 |
| `transfer_overhead.applies_to` | string | 是 | "walking_segment" | walking_segment, whole_transit, none |  |
| `transfer_overhead.factor` | number | 是 | 1.3 |  |  |
| `transfer_overhead.counts_in_timeline` | boolean | 否 | true |  | 是否计入时序推演；PRD 未定义会导致两套时间。 |
| `cost` | object / null | 否 |  |  |  |
| `cost.min` | number | 是 |  |  |  |
| `cost.max` | number | 是 |  |  |  |
| `cost.currency` |  | 是 | "CNY" |  |  |
| `cost.display_currency` | string | 否 | "CNY" |  | 海外用户展示币种，换算口径见 mappings.json/currency_display |
| `congestion_level` |  | 否 | "unknown" |  |  |
| `segments` | array | 否 | [] |  | 3.5 微观解析：进站→途中→换乘→出站→最后 300m。 |
| `drop_off` | object / null | 否 | null |  | 3.5 打车下客点纠偏结果。source 用于区分「人工录入」与「三方推荐」。 |
| `drop_off.point` |  | 是 |  |  |  |
| `drop_off.desc_zh` | string | 是 |  |  |  |
| `drop_off.desc_en` | string | 是 |  |  |  |
| `drop_off.source` |  | 是 |  |  |  |
| `drop_off.selected_from` | string | 否 | "curated" | curated, api, poi_center_fallback |  |
| `last_mile_walk_meters` | integer / null | 否 |  |  |  |
| `polyline` | string / null | 否 |  |  | lng,lat;lng,lat 格式折线；坐标系由 crs 声明。不完整轨迹为 null。 |
| `crs` |  | 否 | "WGS84" |  |  |
| `cache` | object | 否 |  |  |  |
| `cache.key` | string | 否 |  |  | 建议 geohash7:geohash7:mode，见 mappings.json/cache_keys |
| `cache.ttl_seconds` | integer | 否 | 1800 |  |  |
| `cache.hit` | boolean | 否 | false |  |  |
| `data_source` |  | 是 |  |  |  |
| `degraded_reason` |  | 是 |  |  |  |
| `degraded_notice_key` | string / null | 否 | null |  | 降级文案键；直线粗算时为 'degraded.direct_orientation' |
| `partial` | boolean | 否 | false |  | 部分成功语义：哪些字段为 null 必须能被前端识别 |
| `fetched_at` | integer | 是 |  |  | UTC 秒 |

## CuratedStation（`schemas/station.schema.json`）

| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `station_id` | string | 是 |  | ^[a-z]{2}_stn_[0-9]{4,8}$ |  |
| `names` | object | 是 |  |  |  |
| `names.zh-Hans` | string | 是 |  |  |  |
| `names.zh-Hant` | string | 否 |  |  |  |
| `names.en` | string | 是 |  |  |  |
| `names.ja` | string | 否 |  |  |  |
| `names.ko` | string | 否 |  |  |  |
| `romanization` | object | 否 |  |  |  |
| `romanization.pinyin` | string | 否 |  |  |  |
| `romanization.pinyin_plain` | string | 否 |  |  |  |
| `coordinate` |  | 否 |  |  |  |
| `station_group_id` | string / null | 否 |  |  | 同站不同线（换乘站群）归组，避免把「中山公园 2 号线」与「中山公园 3 号线」当成两个车站。 |
| `is_transfer_hub` | boolean | 否 | false |  |  |
| `vertical_complexity` | string | 否 | "flat" | flat, multi_level, deep_multi_level | 对应 1.2 痛点「枢纽站立体高差大」。 |
| `lines` | array | 是 |  |  |  |
| `lines[].code` | string | 是 |  |  |  |
| `lines[].name_en` | string | 是 |  |  |  |
| `lines[].name_zh` | string | 是 |  |  |  |
| `lines[].color_hex` | string | 否 |  | ^#[0-9A-Fa-f]{6}$ |  |
| `lines[].directions` | array | 否 | [] |  |  |
| `lines[].directions[].name_en` | string | 是 |  |  |  |
| `lines[].directions[].name_zh` | string | 是 |  |  |  |
| `lines[].directions[].terminal_station_id` | string / null | 否 |  |  |  |
| `access_points` | array | 是 | [] |  | 进出站口。这是「Enter via: Entrance 2 (2号口)」的唯一数据来源，三方 API 通常不返回。 |
| `access_points[].access_no` | string | 是 |  |  |  |
| `access_points[].kind` | string | 是 |  | entrance, exit, both |  |
| `access_points[].name_zh` | string | 是 |  |  |  |
| `access_points[].name_en` | string | 是 |  |  |  |
| `access_points[].coordinate` |  | 否 |  |  |  |
| `access_points[].landmark_desc_zh` | string | 否 |  |  |  |
| `access_points[].landmark_desc_en` | string | 否 |  |  |  |
| `access_points[].is_barrier_free` | boolean / null | 否 |  |  |  |
| `access_points[].has_escalator` | boolean / null | 否 |  |  |  |
| `access_points[].is_open` | boolean / null | 否 |  |  | 临时关闭的出口；null=未知 |
| `interior_transfers` | array | 否 | [] |  | 站内换乘。支撑「Long Transfer Warning: Walking distance ~320m / 6-8 mins / Take indoor escalators」。 |
| `interior_transfers[].from_line_code` | string | 是 |  |  |  |
| `interior_transfers[].to_line_code` | string | 是 |  |  |  |
| `interior_transfers[].walking_distance_meters` | integer | 是 |  |  |  |
| `interior_transfers[].minutes_min` | number | 是 |  |  |  |
| `interior_transfers[].minutes_max` | number | 是 |  |  |  |
| `interior_transfers[].is_in_station` | boolean | 否 | true |  |  |
| `interior_transfers[].note_zh` | string / null | 否 |  |  |  |
| `interior_transfers[].note_en` | string / null | 否 |  |  |  |
| `interior_transfers[].vertical_gap_note_zh` | string / null | 否 |  |  |  |
| `interior_transfers[].is_barrier_free` | boolean / null | 否 |  |  |  |
| `coverage` | object | 否 |  |  | PRD 未定义覆盖范围；没有它就无法回答「库里没有这个站怎么办」。 |
| `coverage.tier` | string | 是 | "standard" | core_hub, major, standard |  |
| `coverage.completeness` | string | 是 | "partial" | full, partial, access_points_only, none | 决定前端能展示到哪一层；none 时 3.5 的微观增强整体降级为纯文本。 |
| `provenance` | object | 是 |  |  |  |
| `provenance.source` |  | 是 |  |  |  |
| `provenance.updated_at` | integer | 是 |  |  |  |
| `provenance.reviewed_by` | string | 否 |  |  |  |
| `provenance.field_verified_at` | object | 否 |  |  |  |

## Recommendation（`schemas/recommendation.schema.json`）

| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `plan` |  | 是 |  |  |  |
| `days` | array | 是 |  |  |  |
| `days[].day_index` | integer | 是 |  |  |  |
| `days[].date` | string | 是 |  | ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ |  |
| `days[].stops` | array | 是 |  |  |  |
| `skipped_days` | array | 是 |  |  |  |
| `skipped_days[].day_index` | integer | 是 |  |  |  |
| `skipped_days[].reason` | string | 是 |  |  |  |
| `warnings` | array | 是 |  |  |  |
| `trip_id` | string / null | 是 |  |  |  |
| `trip_version` | integer / null | 是 |  |  |  |

