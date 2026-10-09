// 本文件由 contracts/scripts/generate.py 从 schemas/*.schema.json 生成，请勿手改。
// 所有 *_at 为 UTC 秒；date 为 Asia/Shanghai 日期；*_local 为同日时刻。见 contracts/TIME_BASELINE.md

// 枚举唯一取值域：需要使用枚举值时从这里取，不要在业务代码里硬编码字符串。

export type PartyComposition = "solo" | "couple" | "family_kids" | "senior";
export const PARTY_COMPOSITION = ["solo", "couple", "family_kids", "senior"] as const;

export type Pacing = "relaxed" | "balanced" | "packed";
export const PACING = ["relaxed", "balanced", "packed"] as const;

export type Interest = "modern_skyline" | "history_culture" | "local_life" | "nature";
export const INTEREST = ["modern_skyline", "history_culture", "local_life", "nature"] as const;

export type DayStatus = "empty" | "arrival_only" | "partial" | "fulfilled" | "locked";
export const DAY_STATUS = ["empty", "arrival_only", "partial", "fulfilled", "locked"] as const;

export type StopType = "poi" | "hotel" | "arrival_anchor" | "departure_anchor";
export const STOP_TYPE = ["poi", "hotel", "arrival_anchor", "departure_anchor"] as const;

export type TransitMode = "transit" | "taxi" | "walk" | "bike";
export const TRANSIT_MODE = ["transit", "taxi", "walk", "bike"] as const;

export type SegmentKind = "walk" | "ride" | "transfer";
export const SEGMENT_KIND = ["walk", "ride", "transfer"] as const;

export type CongestionLevel = "unknown" | "low" | "medium" | "high" | "severe";
export const CONGESTION_LEVEL = ["unknown", "low", "medium", "high", "severe"] as const;

export type DataSource = "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
export const DATA_SOURCE = ["amap", "tencent", "baidu", "curated", "manual", "degraded", "mock"] as const;

export type DegradedReason = "none" | "timeout" | "rate_limited" | "no_route" | "unsupported_city" | "offline" | "partial_data";
export const DEGRADED_REASON = ["none", "timeout", "rate_limited", "no_route", "unsupported_city", "offline", "partial_data"] as const;

export type ClosureKind = "weekly" | "special_period" | "maintenance" | "holiday_exception_open" | "holiday_exception_closed";
export const CLOSURE_KIND = ["weekly", "special_period", "maintenance", "holiday_exception_open", "holiday_exception_closed"] as const;

export type RuleId = "rule_01_closure" | "rule_02_lightup" | "rule_03_spread" | "rule_04_homogeneous";
export const RULE_ID = ["rule_01_closure", "rule_02_lightup", "rule_03_spread", "rule_04_homogeneous"] as const;

export type RuleSeverity = "hard" | "soft_warning" | "soft_hint";
export const RULE_SEVERITY = ["hard", "soft_warning", "soft_hint"] as const;

export type RuleOutcome = "pending" | "confirmed_proceed" | "rejected" | "auto_dismissed" | "expired_on_reorder";
export const RULE_OUTCOME = ["pending", "confirmed_proceed", "rejected", "auto_dismissed", "expired_on_reorder"] as const;

export type NoticeChannel = "modal_confirm" | "toast" | "inline_bubble" | "list_banner" | "card_badge" | "pin_badge";
export const NOTICE_CHANNEL = ["modal_confirm", "toast", "inline_bubble", "list_banner", "card_badge", "pin_badge"] as const;

export type PinState = "default" | "added_current_day_unselected" | "added_other_day" | "selected_current_day" | "added_conflict_warned";
export const PIN_STATE = ["default", "added_current_day_unselected", "added_other_day", "selected_current_day", "added_conflict_warned"] as const;

export type AskCardNode = "station_entrance" | "transfer" | "station_exit" | "drop_off" | "poi_arrival";
export const ASK_CARD_NODE = ["station_entrance", "transfer", "station_exit", "drop_off", "poi_arrival"] as const;

export type DwellTimeKind = "point" | "range";
export const DWELL_TIME_KIND = ["point", "range"] as const;

export type CoordinateSystem = "WGS84" | "GCJ-02" | "BD-09";
export const COORDINATE_SYSTEM = ["WGS84", "GCJ-02", "BD-09"] as const;

export type Currency = "CNY";
export const CURRENCY = ["CNY"] as const;

export type TripStatus = "draft" | "confirmed" | "in_progress" | "completed" | "archived";
export const TRIP_STATUS = ["draft", "confirmed", "in_progress", "completed", "archived"] as const;

export interface Point {
  lat: number;
  lng: number;
  crs: "WGS84" | "GCJ-02" | "BD-09";
  precision_m?: number;
}

export interface Poi {
  description_zh?: string;
  poi_id: string;
  names: {
    zh-Hans: string;
    zh-Hant?: string;
    en: string;
    ja?: string;
    ko?: string;
  };
  romanization?: {
    pinyin: string;
    pinyin_plain: string;
    ja_romaji?: string;
    ko_rr?: string;
  };
  search_aliases?: string[];
  category: {
    level1: "modern_skyline" | "history_culture" | "local_life" | "nature" | "transport_hub" | "other";
    level2: string;
    label_en: string;
    label_zh: string;
  };
  coordinate: Point;
  drop_off_locations?: {
    point: Point;
    desc_zh: string;
    desc_en: string;
    source: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
    priority: number;
    verified_at?: number;
    note_zh?: string;
    note_en?: string;
  }[];
  operating_rules: {
    opening_hours: {
    weekdays?: 1 | 2 | 3 | 4 | 5 | 6 | 7[];
    date_from?: string;
    date_to?: string;
    open: string;
    close: string;
    close_next_day?: boolean;
  }[];
    last_entry_time?: string | null;
    closure_data_status: "verified" | "unverified" | "unknown";
    closure_rules?: {
    kind: "weekly" | "special_period" | "maintenance" | "holiday_exception_open" | "holiday_exception_closed";
    weekday?: 1 | 2 | 3 | 4 | 5 | 6 | 7;
    date?: string;
    date_from?: string;
    date_to?: string;
    reason_zh?: string;
    reason_en?: string;
    note_zh?: string;
  }[];
    is_enclosed_attraction: boolean;
    reservation_required?: boolean;
    advance_booking_days?: number | null;
    light_up?: Record<string, unknown> | null;
    dwell_time?: {
    kind: "point" | "range";
    minutes?: number;
    minutes_min?: number;
    minutes_max?: number;
  };
  };
  provider_refs?: {
    amap?: string;
    tencent?: string;
    baidu?: string;
  };
  provenance: {
    source: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
    updated_at: number;
    reviewed_by?: string;
    confidence?: number;
  };
  tags?: string[];
}

export interface DayAnchor {
  type: "poi" | "hotel" | "arrival_anchor" | "departure_anchor";
  name_zh: string;
  name_en: string;
  name_pinyin?: string;
  poi_id?: string | null;
  coordinate: Point;
}

export interface Notice {
  rule_id: "rule_01_closure" | "rule_02_lightup" | "rule_03_spread" | "rule_04_homogeneous";
  severity: "hard" | "soft_warning" | "soft_hint";
  outcome: "pending" | "confirmed_proceed" | "rejected" | "auto_dismissed" | "expired_on_reorder";
  channel: "modal_confirm" | "toast" | "inline_bubble" | "list_banner" | "card_badge" | "pin_badge";
  message_key?: string;
  message_args?: Record<string, unknown>;
  confirmed_at?: number | null;
  raised_at: number;
  expires_on_reorder?: boolean;
}

export interface Trip {
  budget?: Record<string, unknown> | null;
  trip_id: string;
  user_id?: string | null;
  version: number;
  status: "draft" | "confirmed" | "in_progress" | "completed" | "archived";
  timezone: "Asia/Shanghai";
  created_at: number;
  updated_at: number;
  user_profile: {
    party_composition: "solo" | "couple" | "family_kids" | "senior";
    pacing: "relaxed" | "balanced" | "packed";
    interests?: "modern_skyline" | "history_culture" | "local_life" | "nature"[];
    walking_speed_factor: number;
    party_walk_multiplier?: number;
    prefer_taxi?: boolean;
  };
  anchor_arrival: {
    arrival_at: number;
    location_name: string;
    coordinate: Point;
    activity_start_at: number;
    border_buffer_minutes?: number;
  };
  anchor_departure?: Record<string, unknown> | null;
  anchor_hotel: {
    name_en: string;
    name_zh: string;
    name_pinyin?: string;
    coordinate: Point;
    poi_id?: string | null;
  };
  unassigned_pois?: string[];
  days: {
    day_index: number;
    date: string;
    day_status: "empty" | "arrival_only" | "partial" | "fulfilled" | "locked";
    daily_start_local: string;
    poi_cap?: number | null;
    start_anchor?: DayAnchor | null;
    end_anchor?: DayAnchor | null;
    ordered_stops: {
    stop_order: number;
    stop_type: "poi" | "hotel" | "arrival_anchor" | "departure_anchor";
    poi_id?: string | null;
    locked?: boolean;
    arrival_at?: number | null;
    departure_at?: number | null;
    user_preferred_arrival_local?: string | null;
    planned_dwell_minutes: number;
    transit_from_previous?: Route | null;
    rule_notices?: Notice[];
    stop_id?: string;
    name_zh?: string;
    name_en?: string;
    name_pinyin?: string;
    coordinate?: Point;
    hotel_stay_kind?: "rest" | "overnight";
  }[];
    is_arrival_day?: boolean;
    end_transit?: Route | null;
  }[];
  revision_history?: {
    version: number;
    changed_at: number;
    operation: "create" | "add_stop" | "remove_stop" | "reorder" | "move_to_evening" | "change_day" | "change_anchor" | "confirm_conflict" | "unlock_day" | "update_config";
    target?: string;
  }[];
  resolved_day_points?: Record<string, unknown>;
  default_day_points?: Record<string, unknown>;
  cost_inputs?: Record<string, unknown> | null;
  budget_assessment?: Record<string, unknown>;
}

export interface Endpoint {
  type: "poi" | "hotel" | "arrival_anchor" | "departure_anchor";
  stop_id?: string;
  poi_id?: string | null;
  station_id?: string | null;
  name_zh?: string | null;
  name_en?: string | null;
}

export interface Variant {
  mode: "transit" | "taxi" | "walk" | "bike";
  duration_seconds: number | null;
  distance_meters?: number | null;
  cost?: Record<string, unknown> | null;
  congestion_level?: "unknown" | "low" | "medium" | "high" | "severe";
  transfer_count?: number | null;
  walking_distance_meters?: number | null;
  estimated_steps?: number | null;
  highlight?: boolean;
  data_source: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
  is_default_tab?: boolean;
}

export interface Segment {
  kind: "walk" | "ride" | "transfer";
  duration_seconds: number;
  distance_meters?: number | null;
  line?: Record<string, unknown> | null;
  direction?: Record<string, unknown> | null;
  board?: AccessPoint;
  alight?: AccessPoint;
  stops?: number | null;
  transfer?: Record<string, unknown> | null;
  walk_note_en?: string | null;
  walk_note_zh?: string | null;
}

export interface AccessPoint {
  station_id?: string | null;
  station_name_zh?: string | null;
  station_name_en?: string | null;
  access_no?: string | null;
  access_name_zh?: string | null;
  access_name_en?: string | null;
  landmark_desc_zh?: string | null;
  landmark_desc_en?: string | null;
  source?: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
}

export interface Route {
  from: Endpoint;
  to: Endpoint;
  mode: "transit" | "taxi" | "walk" | "bike";
  variants?: Variant[];
  distance_meters: number | null;
  duration_seconds: number | null;
  walking_distance_meters?: number | null;
  walking_duration_seconds?: number | null;
  estimated_steps?: number | null;
  transfer_count?: number | null;
  has_long_transfer?: boolean;
  long_transfer_threshold_m?: number;
  transfer_overhead?: Record<string, unknown> | null;
  cost?: Record<string, unknown> | null;
  congestion_level?: "unknown" | "low" | "medium" | "high" | "severe";
  segments?: Segment[];
  drop_off?: Record<string, unknown> | null;
  last_mile_walk_meters?: number | null;
  polyline?: string | null;
  crs?: "WGS84" | "GCJ-02" | "BD-09";
  cache?: {
    key?: string;
    ttl_seconds?: number;
    hit?: boolean;
  };
  data_source: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
  degraded_reason: "none" | "timeout" | "rate_limited" | "no_route" | "unsupported_city" | "offline" | "partial_data";
  degraded_notice_key?: string | null;
  partial?: boolean;
  fetched_at: number;
}

export interface Station {
  station_id: string;
  names: {
    zh-Hans: string;
    zh-Hant?: string;
    en: string;
    ja?: string;
    ko?: string;
  };
  romanization?: {
    pinyin?: string;
    pinyin_plain?: string;
  };
  coordinate?: Point;
  station_group_id?: string | null;
  is_transfer_hub?: boolean;
  vertical_complexity?: "flat" | "multi_level" | "deep_multi_level";
  lines: {
    code: string;
    name_en: string;
    name_zh: string;
    color_hex?: string;
    directions?: {
    name_en: string;
    name_zh: string;
    terminal_station_id?: string | null;
  }[];
  }[];
  access_points: {
    access_no: string;
    kind: "entrance" | "exit" | "both";
    name_zh: string;
    name_en: string;
    coordinate?: Point;
    landmark_desc_zh?: string;
    landmark_desc_en?: string;
    is_barrier_free?: boolean | null;
    has_escalator?: boolean | null;
    is_open?: boolean | null;
  }[];
  interior_transfers?: {
    from_line_code: string;
    to_line_code: string;
    walking_distance_meters: number;
    minutes_min: number;
    minutes_max: number;
    is_in_station?: boolean;
    note_zh?: string | null;
    note_en?: string | null;
    vertical_gap_note_zh?: string | null;
    is_barrier_free?: boolean | null;
  }[];
  coverage?: {
    tier: "core_hub" | "major" | "standard";
    completeness: "full" | "partial" | "access_points_only" | "none";
  };
  provenance: {
    source: "amap" | "tencent" | "baidu" | "curated" | "manual" | "degraded" | "mock";
    updated_at: number;
    reviewed_by?: string;
    field_verified_at?: Record<string, unknown>;
  };
}

export interface Stop {
  poi_id: string;
  planned_dwell_minutes: number;
}

export interface PlanDay {
  day_index: number;
  stops: Stop[];
}

export interface Plan {
  days: PlanDay[];
}

export interface DetailStop {
  poi_id: string;
  name_zh: string;
  planned_dwell_minutes: number;
  reasons: string[];
  warnings: string[];
  estimated_arrival_local?: string;
  estimated_departure_local?: string;
}

export interface Setup {
  user_id?: string | null;
  user_profile: Record<string, unknown>;
  duration_days: number;
  start_date?: string;
  daily_start_local?: string;
  anchor_arrival: Record<string, unknown>;
  anchor_hotel: Record<string, unknown>;
  anchor_departure?: Record<string, unknown> | null;
  budget?: Record<string, unknown> | null;
  cost_inputs?: Record<string, unknown>;
}

export interface GenerateRequest {
  trip_id?: string;
  setup?: Setup;
  day_indices: number[];
}

export interface CreateRequest {
  setup: Setup;
  plan: Plan;
}

export interface ApplyRequest {
  plan: Plan;
}

export interface Recommendation {
  plan: Plan;
  days: {
    day_index: number;
    date: string;
    stops: DetailStop[];
  }[];
  skipped_days: {
    day_index: number;
    reason: string;
  }[];
  warnings: string[];
  trip_id: string | null;
  trip_version: number | null;
}

