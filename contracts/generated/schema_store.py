"""内联后的自包含 schema 与校验入口（生成物，请勿手改）。

用途：模块在自己的进程里校验请求/响应，不依赖仓库根目录的 contracts/schemas/
（模块被安装到 modules/<id>/ 后，仓库结构不保证存在）。

校验需要 jsonschema（可选依赖）：
    from contracts.generated.schema_store import validate
    errors = validate(payload, "route.schema.json")
"""

from __future__ import annotations

import json

_RAW = r'''{
  "poi.schema.json": {
    "title": "POIMaster",
    "type": "object",
    "required": [
      "poi_id",
      "names",
      "category",
      "coordinate",
      "operating_rules",
      "provenance"
    ],
    "additionalProperties": false,
    "properties": {
      "description_zh": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120,
        "description": "简短中文介绍，概述主要看点及游玩方式；可选以兼容旧数据，缺失时由页面提示简介待补充。"
      },
      "poi_id": {
        "type": "string",
        "pattern": "^[a-z]{2}_poi_[0-9]{5,8}$",
        "examples": [
          "sh_poi_00042"
        ]
      },
      "names": {
        "type": "object",
        "description": "多语言名称。PRD 只有 en/zh/pinyin 三件套，日语场景（Sensō-ji）会失效，故改为语言映射。",
        "required": [
          "zh-Hans",
          "en"
        ],
        "additionalProperties": false,
        "properties": {
          "zh-Hans": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "zh-Hant": {
            "type": "string",
            "maxLength": 120
          },
          "en": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200
          },
          "ja": {
            "type": "string",
            "maxLength": 200
          },
          "ko": {
            "type": "string",
            "maxLength": 200
          }
        },
        "x-changed": "拆分为语言映射"
      },
      "romanization": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "pinyin": {
            "type": "string",
            "description": "带声调，用于现场路牌比对展示",
            "examples": [
              "wài tān"
            ]
          },
          "pinyin_plain": {
            "type": "string",
            "description": "无声调，用于检索匹配",
            "examples": [
              "wai tan"
            ]
          },
          "ja_romaji": {
            "type": "string"
          },
          "ko_rr": {
            "type": "string"
          }
        },
        "required": [
          "pinyin",
          "pinyin_plain"
        ],
        "x-changed": "name_pinyin 拆为 pinyin / pinyin_plain，且为人工审核字段（多音字自动生成必错）"
      },
      "search_aliases": {
        "type": "array",
        "items": {
          "type": "string",
          "maxLength": 120
        },
        "maxItems": 20,
        "default": []
      },
      "category": {
        "type": "object",
        "description": "三级分类字典。PRD 只有自由字符串，Rule-04 因此无法统计。",
        "required": [
          "level1",
          "level2",
          "label_en",
          "label_zh"
        ],
        "additionalProperties": false,
        "properties": {
          "level1": {
            "type": "string",
            "enum": [
              "modern_skyline",
              "history_culture",
              "local_life",
              "nature",
              "transport_hub",
              "other"
            ]
          },
          "level2": {
            "type": "string",
            "examples": [
              "riverwalk",
              "classical_garden",
              "temple",
              "museum",
              "observation_deck",
              "wet_market"
            ]
          },
          "label_en": {
            "type": "string"
          },
          "label_zh": {
            "type": "string"
          }
        },
        "x-changed": "category/sub_category 由自由字符串改为受控三级字典"
      },
      "coordinate": {
        "$ref": "#/$defs/point"
      },
      "drop_off_locations": {
        "type": "array",
        "description": "PRD 的 suggested_drop_off_coordinate 单值改为数组，以表达多入口/多停靠点与来源优先级。",
        "maxItems": 10,
        "items": {
          "type": "object",
          "required": [
            "point",
            "desc_zh",
            "desc_en",
            "source",
            "priority"
          ],
          "additionalProperties": false,
          "properties": {
            "point": {
              "$ref": "#/$defs/point"
            },
            "desc_zh": {
              "type": "string",
              "examples": [
                "北京东路圆明园路口"
              ]
            },
            "desc_en": {
              "type": "string",
              "examples": [
                "Intersection of Beijing East Rd & Yuanmingyuan Rd"
              ]
            },
            "source": {
              "type": "string",
              "enum": [
                "amap",
                "tencent",
                "baidu",
                "curated",
                "manual",
                "degraded",
                "mock"
              ]
            },
            "priority": {
              "type": "integer",
              "minimum": 1,
              "description": "1 最高；人工(curated/manual) 优先于三方(api)"
            },
            "verified_at": {
              "type": "integer",
              "description": "UTC 秒"
            },
            "note_zh": {
              "type": "string",
              "examples": [
                "避开中山东一路全线禁停违章区"
              ]
            },
            "note_en": {
              "type": "string"
            }
          }
        },
        "default": [],
        "x-changed": "单值 → 数组（含来源与优先级）"
      },
      "operating_rules": {
        "type": "object",
        "required": [
          "opening_hours",
          "closure_data_status",
          "is_enclosed_attraction"
        ],
        "additionalProperties": false,
        "properties": {
          "opening_hours": {
            "type": "array",
            "description": "结构化时段。PRD 的自由字符串无法表达午休、按星期差异、旺季调整。",
            "minItems": 0,
            "items": {
              "type": "object",
              "required": [
                "open",
                "close"
              ],
              "additionalProperties": false,
              "properties": {
                "weekdays": {
                  "type": "array",
                  "items": {
                    "type": "integer",
                    "enum": [
                      1,
                      2,
                      3,
                      4,
                      5,
                      6,
                      7
                    ],
                    "labels": {
                      "1": "周一/Monday",
                      "2": "周二/Tuesday",
                      "3": "周三/Wednesday",
                      "4": "周四/Thursday",
                      "5": "周五/Friday",
                      "6": "周六/Saturday",
                      "7": "周日/Sunday"
                    }
                  },
                  "default": [
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7
                  ]
                },
                "date_from": {
                  "type": "string",
                  "pattern": "^\\d{2}-\\d{2}$",
                  "examples": [
                    "05-01"
                  ]
                },
                "date_to": {
                  "type": "string",
                  "pattern": "^\\d{2}-\\d{2}$",
                  "examples": [
                    "09-30"
                  ]
                },
                "open": {
                  "type": "string",
                  "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$"
                },
                "close": {
                  "type": "string",
                  "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                  "examples": [
                    "17:00"
                  ]
                },
                "close_next_day": {
                  "type": "boolean",
                  "default": false,
                  "description": "close 是否落在次日（如夜场 23:00-02:00）"
                }
              }
            },
            "x-changed": "standard_opening_hours 字符串 → 结构化时段数组"
          },
          "last_entry_time": {
            "type": [
              "string",
              "null"
            ],
            "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$"
          },
          "closure_data_status": {
            "type": "string",
            "enum": [
              "verified",
              "unverified",
              "unknown"
            ],
            "default": "unknown"
          },
          "closure_rules": {
            "type": "array",
            "maxItems": 50,
            "items": {
              "type": "object",
              "required": [
                "kind"
              ],
              "additionalProperties": false,
              "properties": {
                "kind": {
                  "type": "string",
                  "enum": [
                    "weekly",
                    "special_period",
                    "maintenance",
                    "holiday_exception_open",
                    "holiday_exception_closed"
                  ]
                },
                "weekday": {
                  "type": "integer",
                  "enum": [
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7
                  ],
                  "labels": {
                    "1": "周一/Monday",
                    "2": "周二/Tuesday",
                    "3": "周三/Wednesday",
                    "4": "周四/Thursday",
                    "5": "周五/Friday",
                    "6": "周六/Saturday",
                    "7": "周日/Sunday"
                  }
                },
                "date": {
                  "type": "string",
                  "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "date_from": {
                  "type": "string",
                  "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "date_to": {
                  "type": "string",
                  "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "reason_zh": {
                  "type": "string",
                  "examples": [
                    "春节假期闭馆"
                  ]
                },
                "reason_en": {
                  "type": "string",
                  "examples": [
                    "Closed during Spring Festival"
                  ]
                },
                "note_zh": {
                  "type": "string",
                  "examples": [
                    "逢法定节假日照常开放"
                  ]
                }
              }
            },
            "default": [],
            "x-changed": "closure_days: [] → closure_rules[]（支持周闭/特定期/修缮/节假日例外）"
          },
          "is_enclosed_attraction": {
            "type": "boolean",
            "default": false
          },
          "reservation_required": {
            "type": "boolean",
            "default": false,
            "x-changed": "新增"
          },
          "advance_booking_days": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0,
            "maximum": 90,
            "default": null
          },
          "light_up": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "required": [
              "required",
              "windows"
            ],
            "properties": {
              "required": {
                "type": "boolean",
                "default": false
              },
              "T_light_rule": {
                "type": "string",
                "enum": [
                  "window_start_minus_30",
                  "sunset",
                  "window_start"
                ],
                "default": "window_start_minus_30",
                "description": "T_light 的取点规则；Rule-02 依赖它。"
              },
              "windows": {
                "type": "array",
                "minItems": 0,
                "items": {
                  "type": "object",
                  "required": [
                    "date_from",
                    "date_to",
                    "start",
                    "close"
                  ],
                  "additionalProperties": false,
                  "properties": {
                    "date_from": {
                      "type": "string",
                      "pattern": "^\\d{2}-\\d{2}$",
                      "examples": [
                        "05-01"
                      ]
                    },
                    "date_to": {
                      "type": "string",
                      "pattern": "^\\d{2}-\\d{2}$",
                      "examples": [
                        "09-30"
                      ]
                    },
                    "label_zh": {
                      "type": "string",
                      "examples": [
                        "夏季"
                      ]
                    },
                    "label_en": {
                      "type": "string",
                      "examples": [
                        "Summer"
                      ]
                    },
                    "start": {
                      "type": "string",
                      "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                      "examples": [
                        "19:00"
                      ]
                    },
                    "close": {
                      "type": "string",
                      "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                      "examples": [
                        "23:00"
                      ]
                    }
                  }
                },
                "x-changed": "summer/winter 两键 → 带生效日期的窗口数组（解决跨季与 T_light）"
              }
            }
          },
          "dwell_time": {
            "type": "object",
            "required": [
              "kind"
            ],
            "additionalProperties": false,
            "properties": {
              "kind": {
                "type": "string",
                "enum": [
                  "point",
                  "range"
                ]
              },
              "minutes": {
                "type": "integer",
                "minimum": 15,
                "maximum": 720
              },
              "minutes_min": {
                "type": "integer",
                "minimum": 15,
                "maximum": 720
              },
              "minutes_max": {
                "type": "integer",
                "minimum": 15,
                "maximum": 720
              }
            },
            "x-changed": "suggested_dwell_minutes 单值 → 支持点值与区间"
          }
        }
      },
      "provider_refs": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "amap": {
            "type": "string"
          },
          "tencent": {
            "type": "string"
          },
          "baidu": {
            "type": "string"
          }
        },
        "x-changed": "新增"
      },
      "provenance": {
        "type": "object",
        "required": [
          "source",
          "updated_at"
        ],
        "additionalProperties": false,
        "properties": {
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "updated_at": {
            "type": "integer",
            "description": "UTC 秒"
          },
          "reviewed_by": {
            "type": "string"
          },
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "default": 1
          }
        },
        "x-changed": "新增（数据来源与可信度，PRD 全篇无数据来源设计）"
      },
      "tags": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "maxItems": 20,
        "default": []
      }
    },
    "$defs": {
      "point": {
        "type": "object",
        "required": [
          "lat",
          "lng",
          "crs"
        ],
        "additionalProperties": false,
        "properties": {
          "lat": {
            "type": "number",
            "minimum": -90,
            "maximum": 90
          },
          "lng": {
            "type": "number",
            "minimum": -180,
            "maximum": 180
          },
          "crs": {
            "type": "string",
            "enum": [
              "WGS84",
              "GCJ-02",
              "BD-09"
            ]
          },
          "precision_m": {
            "type": "number",
            "minimum": 0,
            "default": 50,
            "description": "入口点级精度（非几何中心）"
          }
        }
      }
    }
  },
  "trip.schema.json": {
    "title": "TripInstance",
    "type": "object",
    "required": [
      "trip_id",
      "version",
      "status",
      "user_profile",
      "anchor_arrival",
      "anchor_hotel",
      "days",
      "timezone",
      "created_at",
      "updated_at"
    ],
    "additionalProperties": false,
    "properties": {
      "budget": {
        "type": [
          "object",
          "null"
        ],
        "default": null,
        "description": "每人整趟行程预算；null 表示未设置。金额使用整数分。",
        "required": [
          "scope",
          "currency",
          "amount_cents"
        ],
        "additionalProperties": false,
        "properties": {
          "scope": {
            "type": "string",
            "const": "per_person"
          },
          "currency": {
            "type": "string",
            "const": "CNY"
          },
          "amount_cents": {
            "type": "integer",
            "minimum": 0,
            "maximum": 999999999999
          }
        }
      },
      "trip_id": {
        "type": "string",
        "pattern": "^trip_[0-9a-z]{6,32}$",
        "examples": [
          "trip_982341"
        ]
      },
      "user_id": {
        "type": [
          "string",
          "null"
        ],
        "x-changed": "新增"
      },
      "version": {
        "type": "integer",
        "minimum": 1,
        "x-changed": "新增"
      },
      "status": {
        "type": "string",
        "enum": [
          "draft",
          "confirmed",
          "in_progress",
          "completed",
          "archived"
        ]
      },
      "timezone": {
        "type": "string",
        "const": "Asia/Shanghai"
      },
      "created_at": {
        "type": "integer",
        "x-changed": "新增"
      },
      "updated_at": {
        "type": "integer",
        "x-changed": "新增"
      },
      "user_profile": {
        "type": "object",
        "required": [
          "party_composition",
          "pacing",
          "walking_speed_factor"
        ],
        "additionalProperties": false,
        "properties": {
          "party_composition": {
            "type": "string",
            "enum": [
              "solo",
              "couple",
              "family_kids",
              "senior"
            ]
          },
          "pacing": {
            "type": "string",
            "enum": [
              "relaxed",
              "balanced",
              "packed"
            ]
          },
          "interests": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": [
                "modern_skyline",
                "history_culture",
                "local_life",
                "nature"
              ]
            },
            "maxItems": 4,
            "default": []
          },
          "walking_speed_factor": {
            "type": "number",
            "minimum": 0.5,
            "maximum": 2.0,
            "default": 1.0
          },
          "party_walk_multiplier": {
            "type": "number",
            "minimum": 0.5,
            "maximum": 2.0,
            "default": 1.0,
            "x-changed": "新增（把 PRD 的 1.3 落到独立字段，避免与 walking_speed_factor 混用）"
          },
          "prefer_taxi": {
            "type": "boolean",
            "default": false
          }
        }
      },
      "anchor_arrival": {
        "type": "object",
        "required": [
          "arrival_at",
          "location_name",
          "coordinate",
          "activity_start_at"
        ],
        "additionalProperties": false,
        "properties": {
          "arrival_at": {
            "type": "integer",
            "description": "UTC 秒（PRD 的 timestamp，与 date 矛盾的元凶）",
            "x-changed": "timestamp → arrival_at"
          },
          "location_name": {
            "type": "string"
          },
          "coordinate": {
            "type": "object",
            "required": [
              "lat",
              "lng",
              "crs"
            ],
            "additionalProperties": false,
            "properties": {
              "lat": {
                "type": "number",
                "minimum": -90,
                "maximum": 90
              },
              "lng": {
                "type": "number",
                "minimum": -180,
                "maximum": 180
              },
              "crs": {
                "type": "string",
                "enum": [
                  "WGS84",
                  "GCJ-02",
                  "BD-09"
                ]
              },
              "precision_m": {
                "type": "number",
                "minimum": 0,
                "default": 50,
                "description": "入口点级精度（非几何中心）"
              }
            }
          },
          "activity_start_at": {
            "type": "integer",
            "description": "服务端派生 = arrival_at + 90min；客户端只读"
          },
          "border_buffer_minutes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 300,
            "default": 90
          }
        }
      },
      "anchor_departure": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "required": [
          "departure_at",
          "location_name",
          "coordinate",
          "hub_buffer_minutes"
        ],
        "properties": {
          "departure_at": {
            "type": "integer"
          },
          "location_name": {
            "type": "string"
          },
          "coordinate": {
            "type": "object",
            "required": [
              "lat",
              "lng",
              "crs"
            ],
            "additionalProperties": false,
            "properties": {
              "lat": {
                "type": "number",
                "minimum": -90,
                "maximum": 90
              },
              "lng": {
                "type": "number",
                "minimum": -180,
                "maximum": 180
              },
              "crs": {
                "type": "string",
                "enum": [
                  "WGS84",
                  "GCJ-02",
                  "BD-09"
                ]
              },
              "precision_m": {
                "type": "number",
                "minimum": 0,
                "default": 50,
                "description": "入口点级精度（非几何中心）"
              }
            }
          },
          "is_international": {
            "type": "boolean",
            "default": true
          },
          "hub_buffer_minutes": {
            "type": "integer",
            "minimum": 60,
            "maximum": 300,
            "default": 180
          }
        },
        "default": null,
        "x-changed": "新增"
      },
      "anchor_hotel": {
        "type": "object",
        "required": [
          "name_en",
          "name_zh",
          "coordinate"
        ],
        "additionalProperties": false,
        "properties": {
          "name_en": {
            "type": "string"
          },
          "name_zh": {
            "type": "string"
          },
          "name_pinyin": {
            "type": "string",
            "description": "PRD 的 anchor_hotel 连拼音都没有"
          },
          "coordinate": {
            "type": "object",
            "required": [
              "lat",
              "lng",
              "crs"
            ],
            "additionalProperties": false,
            "properties": {
              "lat": {
                "type": "number",
                "minimum": -90,
                "maximum": 90
              },
              "lng": {
                "type": "number",
                "minimum": -180,
                "maximum": 180
              },
              "crs": {
                "type": "string",
                "enum": [
                  "WGS84",
                  "GCJ-02",
                  "BD-09"
                ]
              },
              "precision_m": {
                "type": "number",
                "minimum": 0,
                "default": 50,
                "description": "入口点级精度（非几何中心）"
              }
            }
          },
          "poi_id": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "unassigned_pois": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "default": [],
        "x-changed": "新增"
      },
      "days": {
        "type": "array",
        "minItems": 1,
        "maxItems": 15,
        "items": {
          "type": "object",
          "required": [
            "day_index",
            "date",
            "day_status",
            "daily_start_local",
            "ordered_stops"
          ],
          "additionalProperties": false,
          "properties": {
            "day_index": {
              "type": "integer",
              "minimum": 1,
              "maximum": 15
            },
            "date": {
              "type": "string",
              "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
              "description": "上海本地日期"
            },
            "day_status": {
              "type": "string",
              "enum": [
                "empty",
                "arrival_only",
                "partial",
                "fulfilled",
                "locked"
              ]
            },
            "daily_start_local": {
              "type": "string",
              "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
              "default": "09:00",
              "x-changed": "新增（阻断项：缺它则 Day2..N 时序断链）"
            },
            "poi_cap": {
              "type": [
                "integer",
                "null"
              ],
              "default": null
            },
            "start_anchor": {
              "anyOf": [
                {
                  "$ref": "#/$defs/day_anchor"
                },
                {
                  "type": "null"
                }
              ],
              "default": null,
              "description": "当日起点；null 时首日用抵达口岸，其余用前一日终点。"
            },
            "end_anchor": {
              "anyOf": [
                {
                  "$ref": "#/$defs/day_anchor"
                },
                {
                  "type": "null"
                }
              ],
              "default": null,
              "description": "当日终点；null 时使用当前住宿，末日优先离境口岸。显式酒店终点成为后续默认住宿。"
            },
            "ordered_stops": {
              "type": "array",
              "minItems": 0,
              "maxItems": 12,
              "items": {
                "type": "object",
                "required": [
                  "stop_order",
                  "stop_type",
                  "planned_dwell_minutes"
                ],
                "additionalProperties": false,
                "properties": {
                  "stop_order": {
                    "type": "integer",
                    "minimum": 1
                  },
                  "stop_type": {
                    "type": "string",
                    "enum": [
                      "poi",
                      "hotel",
                      "arrival_anchor",
                      "departure_anchor"
                    ]
                  },
                  "poi_id": {
                    "type": [
                      "string",
                      "null"
                    ]
                  },
                  "locked": {
                    "type": "boolean",
                    "default": false
                  },
                  "arrival_at": {
                    "type": [
                      "integer",
                      "null"
                    ],
                    "description": "引擎推算，只读"
                  },
                  "departure_at": {
                    "type": [
                      "integer",
                      "null"
                    ],
                    "description": "引擎推算 = arrival_at + dwell"
                  },
                  "user_preferred_arrival_local": {
                    "type": [
                      "string",
                      "null"
                    ],
                    "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                    "x-changed": "target_arrival_time 拆为 arrival_at（引擎）与 user_preferred_arrival_local（用户）"
                  },
                  "planned_dwell_minutes": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 720
                  },
                  "transit_from_previous": {
                    "anyOf": [
                      {
                        "title": "RouteSegment",
                        "type": "object",
                        "required": [
                          "from",
                          "to",
                          "mode",
                          "distance_meters",
                          "duration_seconds",
                          "data_source",
                          "degraded_reason",
                          "fetched_at"
                        ],
                        "additionalProperties": false,
                        "properties": {
                          "from": {
                            "$ref": "#/$defs/endpoint_x"
                          },
                          "to": {
                            "$ref": "#/$defs/endpoint_x"
                          },
                          "mode": {
                            "type": "string",
                            "enum": [
                              "transit",
                              "taxi",
                              "walk",
                              "bike"
                            ]
                          },
                          "variants": {
                            "type": "array",
                            "items": {
                              "$ref": "#/$defs/variant_x"
                            },
                            "default": []
                          },
                          "distance_meters": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0,
                            "x-changed": "新增"
                          },
                          "duration_seconds": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0
                          },
                          "walking_distance_meters": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0,
                            "x-changed": "新增（3.4「步行总长」）"
                          },
                          "walking_duration_seconds": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0,
                            "x-changed": "新增"
                          },
                          "estimated_steps": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0,
                            "x-changed": "新增（3.4「注明消耗步数」，按 mappings.json/step_estimation 的步长假设）"
                          },
                          "transfer_count": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0
                          },
                          "has_long_transfer": {
                            "type": "boolean",
                            "default": false
                          },
                          "long_transfer_threshold_m": {
                            "type": "integer",
                            "default": 200
                          },
                          "transfer_overhead": {
                            "type": [
                              "object",
                              "null"
                            ],
                            "additionalProperties": false,
                            "required": [
                              "applies_to",
                              "factor"
                            ],
                            "properties": {
                              "applies_to": {
                                "type": "string",
                                "enum": [
                                  "walking_segment",
                                  "whole_transit",
                                  "none"
                                ],
                                "default": "walking_segment"
                              },
                              "factor": {
                                "type": "number",
                                "minimum": 1.0,
                                "maximum": 2.0,
                                "default": 1.3
                              },
                              "counts_in_timeline": {
                                "type": "boolean",
                                "default": true
                              }
                            },
                            "default": null,
                            "x-changed": "新增（幂等要求：用原值+系数，不改写值）"
                          },
                          "cost": {
                            "type": [
                              "object",
                              "null"
                            ],
                            "required": [
                              "min",
                              "max",
                              "currency"
                            ],
                            "additionalProperties": false,
                            "properties": {
                              "min": {
                                "type": "number",
                                "minimum": 0
                              },
                              "max": {
                                "type": "number",
                                "minimum": 0
                              },
                              "currency": {
                                "type": "string",
                                "enum": [
                                  "CNY"
                                ]
                              },
                              "display_currency": {
                                "type": "string",
                                "default": "CNY"
                              }
                            },
                            "x-changed": "cost_cny 单值 → 区间（3.4 要求「预估费用区间」）"
                          },
                          "congestion_level": {
                            "type": "string",
                            "enum": [
                              "unknown",
                              "low",
                              "medium",
                              "high",
                              "severe"
                            ]
                          },
                          "segments": {
                            "type": "array",
                            "items": {
                              "$ref": "#/$defs/segment_x"
                            },
                            "default": []
                          },
                          "drop_off": {
                            "type": [
                              "object",
                              "null"
                            ],
                            "required": [
                              "point",
                              "desc_zh",
                              "desc_en",
                              "source"
                            ],
                            "additionalProperties": false,
                            "properties": {
                              "point": {
                                "type": "object",
                                "required": [
                                  "lat",
                                  "lng",
                                  "crs"
                                ],
                                "additionalProperties": false,
                                "properties": {
                                  "lat": {
                                    "type": "number",
                                    "minimum": -90,
                                    "maximum": 90
                                  },
                                  "lng": {
                                    "type": "number",
                                    "minimum": -180,
                                    "maximum": 180
                                  },
                                  "crs": {
                                    "type": "string",
                                    "enum": [
                                      "WGS84",
                                      "GCJ-02",
                                      "BD-09"
                                    ]
                                  },
                                  "precision_m": {
                                    "type": "number",
                                    "minimum": 0,
                                    "default": 50,
                                    "description": "入口点级精度（非几何中心）"
                                  }
                                }
                              },
                              "desc_zh": {
                                "type": "string"
                              },
                              "desc_en": {
                                "type": "string"
                              },
                              "source": {
                                "type": "string",
                                "enum": [
                                  "amap",
                                  "tencent",
                                  "baidu",
                                  "curated",
                                  "manual",
                                  "degraded",
                                  "mock"
                                ]
                              },
                              "selected_from": {
                                "type": "string",
                                "enum": [
                                  "curated",
                                  "api",
                                  "poi_center_fallback"
                                ],
                                "default": "curated"
                              }
                            },
                            "default": null
                          },
                          "last_mile_walk_meters": {
                            "type": [
                              "integer",
                              "null"
                            ],
                            "minimum": 0,
                            "x-changed": "新增（3.5「步行段最后 300m」）"
                          },
                          "polyline": {
                            "type": [
                              "string",
                              "null"
                            ]
                          },
                          "crs": {
                            "type": "string",
                            "enum": [
                              "WGS84",
                              "GCJ-02",
                              "BD-09"
                            ]
                          },
                          "cache": {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                              "key": {
                                "type": "string"
                              },
                              "ttl_seconds": {
                                "type": "integer",
                                "default": 1800
                              },
                              "hit": {
                                "type": "boolean",
                                "default": false
                              }
                            }
                          },
                          "data_source": {
                            "type": "string",
                            "enum": [
                              "amap",
                              "tencent",
                              "baidu",
                              "curated",
                              "manual",
                              "degraded",
                              "mock"
                            ]
                          },
                          "degraded_reason": {
                            "type": "string",
                            "enum": [
                              "none",
                              "timeout",
                              "rate_limited",
                              "no_route",
                              "unsupported_city",
                              "offline",
                              "partial_data"
                            ]
                          },
                          "degraded_notice_key": {
                            "type": [
                              "string",
                              "null"
                            ],
                            "default": null
                          },
                          "partial": {
                            "type": "boolean",
                            "default": false
                          },
                          "fetched_at": {
                            "type": "integer",
                            "description": "UTC 秒"
                          }
                        }
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "rule_notices": {
                    "type": "array",
                    "items": {
                      "$ref": "#/$defs/notice"
                    },
                    "default": [],
                    "x-changed": "新增（规则结果需要落库，尤其 Proceed anyway 确认）"
                  },
                  "stop_id": {
                    "type": "string",
                    "description": "稳定停靠点标识；排序、移除、跨天移动使用"
                  },
                  "name_zh": {
                    "type": "string"
                  },
                  "name_en": {
                    "type": "string"
                  },
                  "name_pinyin": {
                    "type": "string"
                  },
                  "coordinate": {
                    "type": "object",
                    "required": [
                      "lat",
                      "lng",
                      "crs"
                    ],
                    "additionalProperties": false,
                    "properties": {
                      "lat": {
                        "type": "number",
                        "minimum": -90,
                        "maximum": 90
                      },
                      "lng": {
                        "type": "number",
                        "minimum": -180,
                        "maximum": 180
                      },
                      "crs": {
                        "type": "string",
                        "enum": [
                          "WGS84",
                          "GCJ-02",
                          "BD-09"
                        ]
                      },
                      "precision_m": {
                        "type": "number",
                        "minimum": 0,
                        "default": 50,
                        "description": "入口点级精度（非几何中心）"
                      }
                    }
                  },
                  "hotel_stay_kind": {
                    "type": "string",
                    "enum": [
                      "rest",
                      "overnight"
                    ],
                    "description": "酒店停靠用途：rest 为途中休息，不改变后续住宿；overnight 为过夜或换酒店。旧数据缺字段沿用过夜继承。"
                  }
                },
                "allOf": [
                  {
                    "if": {
                      "required": [
                        "hotel_stay_kind"
                      ]
                    },
                    "then": {
                      "required": [
                        "stop_type"
                      ],
                      "properties": {
                        "stop_type": {
                          "const": "hotel"
                        }
                      }
                    }
                  }
                ]
              }
            },
            "is_arrival_day": {
              "type": "boolean",
              "description": "服务端按抵达日期派生，独立于 day_status"
            },
            "end_transit": {
              "anyOf": [
                {
                  "title": "RouteSegment",
                  "type": "object",
                  "required": [
                    "from",
                    "to",
                    "mode",
                    "distance_meters",
                    "duration_seconds",
                    "data_source",
                    "degraded_reason",
                    "fetched_at"
                  ],
                  "additionalProperties": false,
                  "properties": {
                    "from": {
                      "$ref": "#/$defs/endpoint_x"
                    },
                    "to": {
                      "$ref": "#/$defs/endpoint_x"
                    },
                    "mode": {
                      "type": "string",
                      "enum": [
                        "transit",
                        "taxi",
                        "walk",
                        "bike"
                      ]
                    },
                    "variants": {
                      "type": "array",
                      "items": {
                        "$ref": "#/$defs/variant_x"
                      },
                      "default": []
                    },
                    "distance_meters": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0,
                      "x-changed": "新增"
                    },
                    "duration_seconds": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0
                    },
                    "walking_distance_meters": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0,
                      "x-changed": "新增（3.4「步行总长」）"
                    },
                    "walking_duration_seconds": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0,
                      "x-changed": "新增"
                    },
                    "estimated_steps": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0,
                      "x-changed": "新增（3.4「注明消耗步数」，按 mappings.json/step_estimation 的步长假设）"
                    },
                    "transfer_count": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0
                    },
                    "has_long_transfer": {
                      "type": "boolean",
                      "default": false
                    },
                    "long_transfer_threshold_m": {
                      "type": "integer",
                      "default": 200
                    },
                    "transfer_overhead": {
                      "type": [
                        "object",
                        "null"
                      ],
                      "additionalProperties": false,
                      "required": [
                        "applies_to",
                        "factor"
                      ],
                      "properties": {
                        "applies_to": {
                          "type": "string",
                          "enum": [
                            "walking_segment",
                            "whole_transit",
                            "none"
                          ],
                          "default": "walking_segment"
                        },
                        "factor": {
                          "type": "number",
                          "minimum": 1.0,
                          "maximum": 2.0,
                          "default": 1.3
                        },
                        "counts_in_timeline": {
                          "type": "boolean",
                          "default": true
                        }
                      },
                      "default": null,
                      "x-changed": "新增（幂等要求：用原值+系数，不改写值）"
                    },
                    "cost": {
                      "type": [
                        "object",
                        "null"
                      ],
                      "required": [
                        "min",
                        "max",
                        "currency"
                      ],
                      "additionalProperties": false,
                      "properties": {
                        "min": {
                          "type": "number",
                          "minimum": 0
                        },
                        "max": {
                          "type": "number",
                          "minimum": 0
                        },
                        "currency": {
                          "type": "string",
                          "enum": [
                            "CNY"
                          ]
                        },
                        "display_currency": {
                          "type": "string",
                          "default": "CNY"
                        }
                      },
                      "x-changed": "cost_cny 单值 → 区间（3.4 要求「预估费用区间」）"
                    },
                    "congestion_level": {
                      "type": "string",
                      "enum": [
                        "unknown",
                        "low",
                        "medium",
                        "high",
                        "severe"
                      ]
                    },
                    "segments": {
                      "type": "array",
                      "items": {
                        "$ref": "#/$defs/segment_x"
                      },
                      "default": []
                    },
                    "drop_off": {
                      "type": [
                        "object",
                        "null"
                      ],
                      "required": [
                        "point",
                        "desc_zh",
                        "desc_en",
                        "source"
                      ],
                      "additionalProperties": false,
                      "properties": {
                        "point": {
                          "type": "object",
                          "required": [
                            "lat",
                            "lng",
                            "crs"
                          ],
                          "additionalProperties": false,
                          "properties": {
                            "lat": {
                              "type": "number",
                              "minimum": -90,
                              "maximum": 90
                            },
                            "lng": {
                              "type": "number",
                              "minimum": -180,
                              "maximum": 180
                            },
                            "crs": {
                              "type": "string",
                              "enum": [
                                "WGS84",
                                "GCJ-02",
                                "BD-09"
                              ]
                            },
                            "precision_m": {
                              "type": "number",
                              "minimum": 0,
                              "default": 50,
                              "description": "入口点级精度（非几何中心）"
                            }
                          }
                        },
                        "desc_zh": {
                          "type": "string"
                        },
                        "desc_en": {
                          "type": "string"
                        },
                        "source": {
                          "type": "string",
                          "enum": [
                            "amap",
                            "tencent",
                            "baidu",
                            "curated",
                            "manual",
                            "degraded",
                            "mock"
                          ]
                        },
                        "selected_from": {
                          "type": "string",
                          "enum": [
                            "curated",
                            "api",
                            "poi_center_fallback"
                          ],
                          "default": "curated"
                        }
                      },
                      "default": null
                    },
                    "last_mile_walk_meters": {
                      "type": [
                        "integer",
                        "null"
                      ],
                      "minimum": 0,
                      "x-changed": "新增（3.5「步行段最后 300m」）"
                    },
                    "polyline": {
                      "type": [
                        "string",
                        "null"
                      ]
                    },
                    "crs": {
                      "type": "string",
                      "enum": [
                        "WGS84",
                        "GCJ-02",
                        "BD-09"
                      ]
                    },
                    "cache": {
                      "type": "object",
                      "additionalProperties": false,
                      "properties": {
                        "key": {
                          "type": "string"
                        },
                        "ttl_seconds": {
                          "type": "integer",
                          "default": 1800
                        },
                        "hit": {
                          "type": "boolean",
                          "default": false
                        }
                      }
                    },
                    "data_source": {
                      "type": "string",
                      "enum": [
                        "amap",
                        "tencent",
                        "baidu",
                        "curated",
                        "manual",
                        "degraded",
                        "mock"
                      ]
                    },
                    "degraded_reason": {
                      "type": "string",
                      "enum": [
                        "none",
                        "timeout",
                        "rate_limited",
                        "no_route",
                        "unsupported_city",
                        "offline",
                        "partial_data"
                      ]
                    },
                    "degraded_notice_key": {
                      "type": [
                        "string",
                        "null"
                      ],
                      "default": null
                    },
                    "partial": {
                      "type": "boolean",
                      "default": false
                    },
                    "fetched_at": {
                      "type": "integer",
                      "description": "UTC 秒"
                    }
                  }
                },
                {
                  "type": "null"
                }
              ]
            }
          }
        }
      },
      "revision_history": {
        "type": "array",
        "maxItems": 200,
        "items": {
          "type": "object",
          "required": [
            "version",
            "changed_at",
            "operation"
          ],
          "additionalProperties": false,
          "properties": {
            "version": {
              "type": "integer"
            },
            "changed_at": {
              "type": "integer"
            },
            "operation": {
              "type": "string",
              "enum": [
                "create",
                "add_stop",
                "remove_stop",
                "reorder",
                "move_to_evening",
                "change_day",
                "change_anchor",
                "confirm_conflict",
                "unlock_day",
                "update_config"
              ]
            },
            "target": {
              "type": "string"
            }
          }
        },
        "default": [],
        "x-changed": "新增（PRD 无撤销/回滚/审计能力）"
      },
      "resolved_day_points": {
        "type": "object",
        "additionalProperties": true,
        "description": "服务端只读派生每日起终点快照，不持久化"
      },
      "default_day_points": {
        "type": "object",
        "additionalProperties": true,
        "description": "服务端只读派生每日起终点快照，不持久化"
      },
      "cost_inputs": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "properties": {
          "intercity_cents": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0,
            "maximum": 999999999999
          },
          "meal_daily_cents": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0,
            "maximum": 999999999999
          },
          "extras_cents": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0,
            "maximum": 999999999999
          },
          "travelers": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 1,
            "maximum": 100
          },
          "lodging_rooms": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 1,
            "maximum": 100,
            "description": "自动住宿估算的房间数；未填写按1间参考估算。"
          },
          "taxi_vehicles": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 1,
            "maximum": 100
          },
          "contingency_percent": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100
          },
          "itinerary_key": {
            "type": "string",
            "maxLength": 128
          },
          "ticket_cents": {
            "type": "object",
            "maxProperties": 240,
            "additionalProperties": {
              "type": [
                "integer",
                "null"
              ],
              "minimum": 0,
              "maximum": 999999999999
            }
          },
          "meal_overrides": {
            "type": "object",
            "maxProperties": 240,
            "additionalProperties": {
              "type": [
                "integer",
                "null"
              ],
              "minimum": 0,
              "maximum": 999999999999
            }
          },
          "lodging_nights": {
            "type": [
              "array",
              "null"
            ],
            "maxItems": 60,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": [
                "date",
                "hotel_name",
                "rooms",
                "room_price_cents"
              ],
              "properties": {
                "date": {
                  "type": "string",
                  "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "hotel_name": {
                  "type": "string",
                  "maxLength": 160
                },
                "rooms": {
                  "type": [
                    "integer",
                    "null"
                  ],
                  "minimum": 1,
                  "maximum": 100
                },
                "room_price_cents": {
                  "type": [
                    "integer",
                    "null"
                  ],
                  "minimum": 0,
                  "maximum": 999999999999
                }
              }
            }
          }
        }
      },
      "budget_assessment": {
        "type": "object",
        "readOnly": true,
        "description": "动态费用评估，不保存到行程文件；缺失费用不视为免费。"
      }
    },
    "$defs": {
      "day_anchor": {
        "type": "object",
        "required": [
          "type",
          "name_zh",
          "name_en",
          "coordinate"
        ],
        "additionalProperties": false,
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "poi",
              "hotel",
              "arrival_anchor",
              "departure_anchor"
            ]
          },
          "name_zh": {
            "type": "string",
            "minLength": 1
          },
          "name_en": {
            "type": "string",
            "minLength": 1
          },
          "name_pinyin": {
            "type": "string"
          },
          "poi_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "coordinate": {
            "type": "object",
            "required": [
              "lat",
              "lng",
              "crs"
            ],
            "additionalProperties": false,
            "properties": {
              "lat": {
                "type": "number",
                "minimum": -90,
                "maximum": 90
              },
              "lng": {
                "type": "number",
                "minimum": -180,
                "maximum": 180
              },
              "crs": {
                "type": "string",
                "enum": [
                  "WGS84",
                  "GCJ-02",
                  "BD-09"
                ]
              },
              "precision_m": {
                "type": "number",
                "minimum": 0,
                "default": 50,
                "description": "入口点级精度（非几何中心）"
              }
            }
          }
        }
      },
      "notice": {
        "type": "object",
        "required": [
          "rule_id",
          "severity",
          "outcome",
          "channel",
          "raised_at"
        ],
        "additionalProperties": false,
        "properties": {
          "rule_id": {
            "type": "string",
            "enum": [
              "rule_01_closure",
              "rule_02_lightup",
              "rule_03_spread",
              "rule_04_homogeneous"
            ]
          },
          "severity": {
            "type": "string",
            "enum": [
              "hard",
              "soft_warning",
              "soft_hint"
            ]
          },
          "outcome": {
            "type": "string",
            "enum": [
              "pending",
              "confirmed_proceed",
              "rejected",
              "auto_dismissed",
              "expired_on_reorder"
            ]
          },
          "channel": {
            "type": "string",
            "enum": [
              "modal_confirm",
              "toast",
              "inline_bubble",
              "list_banner",
              "card_badge",
              "pin_badge"
            ]
          },
          "message_key": {
            "type": "string",
            "description": "对应 mappings.json/notice_templates 的键，不存最终文案（便于多语言）"
          },
          "message_args": {
            "type": "object",
            "additionalProperties": true,
            "default": {}
          },
          "confirmed_at": {
            "type": [
              "integer",
              "null"
            ],
            "default": null
          },
          "raised_at": {
            "type": "integer"
          },
          "expires_on_reorder": {
            "type": "boolean",
            "default": true
          }
        }
      },
      "endpoint": {
        "type": "object",
        "required": [
          "type"
        ],
        "additionalProperties": false,
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "poi",
              "hotel",
              "arrival_anchor",
              "departure_anchor"
            ]
          },
          "stop_id": {
            "type": "string",
            "description": "实际停靠点稳定标识；每日隐式起终点可省略"
          },
          "poi_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_zh": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_en": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "variant": {
        "type": "object",
        "required": [
          "mode",
          "duration_seconds",
          "data_source"
        ],
        "additionalProperties": false,
        "properties": {
          "mode": {
            "type": "string",
            "enum": [
              "transit",
              "taxi",
              "walk",
              "bike"
            ]
          },
          "duration_seconds": {
            "type": [
              "integer",
              "null"
            ]
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "cost": {
            "type": [
              "object",
              "null"
            ]
          },
          "congestion_level": {
            "type": "string",
            "enum": [
              "unknown",
              "low",
              "medium",
              "high",
              "severe"
            ]
          },
          "transfer_count": {
            "type": [
              "integer",
              "null"
            ]
          },
          "walking_distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "estimated_steps": {
            "type": [
              "integer",
              "null"
            ]
          },
          "highlight": {
            "type": "boolean",
            "default": false
          },
          "data_source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "is_default_tab": {
            "type": "boolean",
            "default": false
          }
        }
      },
      "segment": {
        "type": "object",
        "required": [
          "kind",
          "duration_seconds"
        ],
        "additionalProperties": false,
        "properties": {
          "kind": {
            "type": "string",
            "enum": [
              "walk",
              "ride",
              "transfer"
            ]
          },
          "duration_seconds": {
            "type": "integer",
            "minimum": 0
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "line": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "code": {
                "type": "string",
                "examples": [
                  "2"
                ]
              },
              "name_en": {
                "type": "string",
                "examples": [
                  "Line 2 (Green)"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "2 号线"
                ]
              },
              "color_hex": {
                "type": "string",
                "pattern": "^#[0-9A-Fa-f]{6}$",
                "examples": [
                  "#00A650"
                ]
              }
            }
          },
          "direction": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "name_en": {
                "type": "string",
                "examples": [
                  "Towards Pudong Int'l Airport"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "往浦东国际机场方向"
                ]
              },
              "terminal_station_id": {
                "type": [
                  "string",
                  "null"
                ]
              }
            }
          },
          "board": {
            "$ref": "#/$defs/access_point_x"
          },
          "alight": {
            "$ref": "#/$defs/access_point_x"
          },
          "stops": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0
          },
          "transfer": {
            "type": [
              "object",
              "null"
            ],
            "required": [
              "walking_distance_meters",
              "source"
            ],
            "additionalProperties": false,
            "properties": {
              "walking_distance_meters": {
                "type": [
                  "integer",
                  "null"
                ]
              },
              "duration_min_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "duration_max_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "is_in_station": {
                "type": "boolean",
                "default": true
              },
              "note_en": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "Take indoor escalators"
                ]
              },
              "note_zh": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "建议走站内扶梯"
                ]
              },
              "vertical_gap_note_zh": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "is_barrier_free": {
                "type": [
                  "boolean",
                  "null"
                ]
              },
              "source": {
                "type": "string",
                "enum": [
                  "amap",
                  "tencent",
                  "baidu",
                  "curated",
                  "manual",
                  "degraded",
                  "mock"
                ]
              }
            }
          },
          "walk_note_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Walk 350m East along the pedestrian mall to reach The Bund."
            ]
          },
          "walk_note_zh": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "access_point": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "properties": {
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路"
            ]
          },
          "station_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "East Nanjing Rd"
            ]
          },
          "access_no": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2",
              "7"
            ]
          },
          "access_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2号口"
            ]
          },
          "access_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Entrance 2"
            ]
          },
          "landmark_desc_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路步行街方向"
            ]
          },
          "landmark_desc_en": {
            "type": [
              "string",
              "null"
            ]
          },
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          }
        }
      },
      "endpoint_x": {
        "type": "object",
        "required": [
          "type"
        ],
        "additionalProperties": false,
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "poi",
              "hotel",
              "arrival_anchor",
              "departure_anchor"
            ]
          },
          "stop_id": {
            "type": "string",
            "description": "实际停靠点稳定标识；每日隐式起终点可省略"
          },
          "poi_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_zh": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_en": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "variant_x": {
        "type": "object",
        "required": [
          "mode",
          "duration_seconds",
          "data_source"
        ],
        "additionalProperties": false,
        "properties": {
          "mode": {
            "type": "string",
            "enum": [
              "transit",
              "taxi",
              "walk",
              "bike"
            ]
          },
          "duration_seconds": {
            "type": [
              "integer",
              "null"
            ]
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "cost": {
            "type": [
              "object",
              "null"
            ]
          },
          "congestion_level": {
            "type": "string",
            "enum": [
              "unknown",
              "low",
              "medium",
              "high",
              "severe"
            ]
          },
          "transfer_count": {
            "type": [
              "integer",
              "null"
            ]
          },
          "walking_distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "estimated_steps": {
            "type": [
              "integer",
              "null"
            ]
          },
          "highlight": {
            "type": "boolean",
            "default": false
          },
          "data_source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "is_default_tab": {
            "type": "boolean",
            "default": false
          }
        }
      },
      "segment_x": {
        "type": "object",
        "required": [
          "kind",
          "duration_seconds"
        ],
        "additionalProperties": false,
        "properties": {
          "kind": {
            "type": "string",
            "enum": [
              "walk",
              "ride",
              "transfer"
            ]
          },
          "duration_seconds": {
            "type": "integer",
            "minimum": 0
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "line": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "code": {
                "type": "string",
                "examples": [
                  "2"
                ]
              },
              "name_en": {
                "type": "string",
                "examples": [
                  "Line 2 (Green)"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "2 号线"
                ]
              },
              "color_hex": {
                "type": "string",
                "pattern": "^#[0-9A-Fa-f]{6}$",
                "examples": [
                  "#00A650"
                ]
              }
            }
          },
          "direction": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "name_en": {
                "type": "string",
                "examples": [
                  "Towards Pudong Int'l Airport"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "往浦东国际机场方向"
                ]
              },
              "terminal_station_id": {
                "type": [
                  "string",
                  "null"
                ]
              }
            }
          },
          "board": {
            "$ref": "#/$defs/access_point_x"
          },
          "alight": {
            "$ref": "#/$defs/access_point_x"
          },
          "stops": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0
          },
          "transfer": {
            "type": [
              "object",
              "null"
            ],
            "required": [
              "walking_distance_meters",
              "source"
            ],
            "additionalProperties": false,
            "properties": {
              "walking_distance_meters": {
                "type": [
                  "integer",
                  "null"
                ]
              },
              "duration_min_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "duration_max_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "is_in_station": {
                "type": "boolean",
                "default": true
              },
              "note_en": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "Take indoor escalators"
                ]
              },
              "note_zh": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "建议走站内扶梯"
                ]
              },
              "vertical_gap_note_zh": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "is_barrier_free": {
                "type": [
                  "boolean",
                  "null"
                ]
              },
              "source": {
                "type": "string",
                "enum": [
                  "amap",
                  "tencent",
                  "baidu",
                  "curated",
                  "manual",
                  "degraded",
                  "mock"
                ]
              }
            }
          },
          "walk_note_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Walk 350m East along the pedestrian mall to reach The Bund."
            ]
          },
          "walk_note_zh": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "access_point_x": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "properties": {
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路"
            ]
          },
          "station_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "East Nanjing Rd"
            ]
          },
          "access_no": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2",
              "7"
            ]
          },
          "access_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2号口"
            ]
          },
          "access_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Entrance 2"
            ]
          },
          "landmark_desc_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路步行街方向"
            ]
          },
          "landmark_desc_en": {
            "type": [
              "string",
              "null"
            ]
          },
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          }
        }
      }
    }
  },
  "route.schema.json": {
    "title": "RouteSegment",
    "type": "object",
    "required": [
      "from",
      "to",
      "mode",
      "distance_meters",
      "duration_seconds",
      "data_source",
      "degraded_reason",
      "fetched_at"
    ],
    "additionalProperties": false,
    "properties": {
      "from": {
        "$ref": "#/$defs/endpoint"
      },
      "to": {
        "$ref": "#/$defs/endpoint"
      },
      "mode": {
        "type": "string",
        "enum": [
          "transit",
          "taxi",
          "walk",
          "bike"
        ]
      },
      "variants": {
        "type": "array",
        "items": {
          "$ref": "#/$defs/variant"
        },
        "default": []
      },
      "distance_meters": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0,
        "x-changed": "新增"
      },
      "duration_seconds": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0
      },
      "walking_distance_meters": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0,
        "x-changed": "新增（3.4「步行总长」）"
      },
      "walking_duration_seconds": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0,
        "x-changed": "新增"
      },
      "estimated_steps": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0,
        "x-changed": "新增（3.4「注明消耗步数」，按 mappings.json/step_estimation 的步长假设）"
      },
      "transfer_count": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0
      },
      "has_long_transfer": {
        "type": "boolean",
        "default": false
      },
      "long_transfer_threshold_m": {
        "type": "integer",
        "default": 200
      },
      "transfer_overhead": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "required": [
          "applies_to",
          "factor"
        ],
        "properties": {
          "applies_to": {
            "type": "string",
            "enum": [
              "walking_segment",
              "whole_transit",
              "none"
            ],
            "default": "walking_segment"
          },
          "factor": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 2.0,
            "default": 1.3
          },
          "counts_in_timeline": {
            "type": "boolean",
            "default": true
          }
        },
        "default": null,
        "x-changed": "新增（幂等要求：用原值+系数，不改写值）"
      },
      "cost": {
        "type": [
          "object",
          "null"
        ],
        "required": [
          "min",
          "max",
          "currency"
        ],
        "additionalProperties": false,
        "properties": {
          "min": {
            "type": "number",
            "minimum": 0
          },
          "max": {
            "type": "number",
            "minimum": 0
          },
          "currency": {
            "type": "string",
            "enum": [
              "CNY"
            ]
          },
          "display_currency": {
            "type": "string",
            "default": "CNY"
          }
        },
        "x-changed": "cost_cny 单值 → 区间（3.4 要求「预估费用区间」）"
      },
      "congestion_level": {
        "type": "string",
        "enum": [
          "unknown",
          "low",
          "medium",
          "high",
          "severe"
        ]
      },
      "segments": {
        "type": "array",
        "items": {
          "$ref": "#/$defs/segment"
        },
        "default": []
      },
      "drop_off": {
        "type": [
          "object",
          "null"
        ],
        "required": [
          "point",
          "desc_zh",
          "desc_en",
          "source"
        ],
        "additionalProperties": false,
        "properties": {
          "point": {
            "type": "object",
            "required": [
              "lat",
              "lng",
              "crs"
            ],
            "additionalProperties": false,
            "properties": {
              "lat": {
                "type": "number",
                "minimum": -90,
                "maximum": 90
              },
              "lng": {
                "type": "number",
                "minimum": -180,
                "maximum": 180
              },
              "crs": {
                "type": "string",
                "enum": [
                  "WGS84",
                  "GCJ-02",
                  "BD-09"
                ]
              },
              "precision_m": {
                "type": "number",
                "minimum": 0,
                "default": 50,
                "description": "入口点级精度（非几何中心）"
              }
            }
          },
          "desc_zh": {
            "type": "string"
          },
          "desc_en": {
            "type": "string"
          },
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "selected_from": {
            "type": "string",
            "enum": [
              "curated",
              "api",
              "poi_center_fallback"
            ],
            "default": "curated"
          }
        },
        "default": null
      },
      "last_mile_walk_meters": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0,
        "x-changed": "新增（3.5「步行段最后 300m」）"
      },
      "polyline": {
        "type": [
          "string",
          "null"
        ]
      },
      "crs": {
        "type": "string",
        "enum": [
          "WGS84",
          "GCJ-02",
          "BD-09"
        ]
      },
      "cache": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "key": {
            "type": "string"
          },
          "ttl_seconds": {
            "type": "integer",
            "default": 1800
          },
          "hit": {
            "type": "boolean",
            "default": false
          }
        }
      },
      "data_source": {
        "type": "string",
        "enum": [
          "amap",
          "tencent",
          "baidu",
          "curated",
          "manual",
          "degraded",
          "mock"
        ]
      },
      "degraded_reason": {
        "type": "string",
        "enum": [
          "none",
          "timeout",
          "rate_limited",
          "no_route",
          "unsupported_city",
          "offline",
          "partial_data"
        ]
      },
      "degraded_notice_key": {
        "type": [
          "string",
          "null"
        ],
        "default": null
      },
      "partial": {
        "type": "boolean",
        "default": false
      },
      "fetched_at": {
        "type": "integer",
        "description": "UTC 秒"
      }
    },
    "$defs": {
      "endpoint": {
        "type": "object",
        "required": [
          "type"
        ],
        "additionalProperties": false,
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "poi",
              "hotel",
              "arrival_anchor",
              "departure_anchor"
            ]
          },
          "stop_id": {
            "type": "string",
            "description": "实际停靠点稳定标识；每日隐式起终点可省略"
          },
          "poi_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_zh": {
            "type": [
              "string",
              "null"
            ]
          },
          "name_en": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "variant": {
        "type": "object",
        "required": [
          "mode",
          "duration_seconds",
          "data_source"
        ],
        "additionalProperties": false,
        "properties": {
          "mode": {
            "type": "string",
            "enum": [
              "transit",
              "taxi",
              "walk",
              "bike"
            ]
          },
          "duration_seconds": {
            "type": [
              "integer",
              "null"
            ]
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "cost": {
            "type": [
              "object",
              "null"
            ]
          },
          "congestion_level": {
            "type": "string",
            "enum": [
              "unknown",
              "low",
              "medium",
              "high",
              "severe"
            ]
          },
          "transfer_count": {
            "type": [
              "integer",
              "null"
            ]
          },
          "walking_distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "estimated_steps": {
            "type": [
              "integer",
              "null"
            ]
          },
          "highlight": {
            "type": "boolean",
            "default": false
          },
          "data_source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "is_default_tab": {
            "type": "boolean",
            "default": false
          }
        }
      },
      "segment": {
        "type": "object",
        "required": [
          "kind",
          "duration_seconds"
        ],
        "additionalProperties": false,
        "properties": {
          "kind": {
            "type": "string",
            "enum": [
              "walk",
              "ride",
              "transfer"
            ]
          },
          "duration_seconds": {
            "type": "integer",
            "minimum": 0
          },
          "distance_meters": {
            "type": [
              "integer",
              "null"
            ]
          },
          "line": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "code": {
                "type": "string",
                "examples": [
                  "2"
                ]
              },
              "name_en": {
                "type": "string",
                "examples": [
                  "Line 2 (Green)"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "2 号线"
                ]
              },
              "color_hex": {
                "type": "string",
                "pattern": "^#[0-9A-Fa-f]{6}$",
                "examples": [
                  "#00A650"
                ]
              }
            }
          },
          "direction": {
            "type": [
              "object",
              "null"
            ],
            "additionalProperties": false,
            "properties": {
              "name_en": {
                "type": "string",
                "examples": [
                  "Towards Pudong Int'l Airport"
                ]
              },
              "name_zh": {
                "type": "string",
                "examples": [
                  "往浦东国际机场方向"
                ]
              },
              "terminal_station_id": {
                "type": [
                  "string",
                  "null"
                ]
              }
            }
          },
          "board": {
            "$ref": "#/$defs/access_point"
          },
          "alight": {
            "$ref": "#/$defs/access_point"
          },
          "stops": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 0
          },
          "transfer": {
            "type": [
              "object",
              "null"
            ],
            "required": [
              "walking_distance_meters",
              "source"
            ],
            "additionalProperties": false,
            "properties": {
              "walking_distance_meters": {
                "type": [
                  "integer",
                  "null"
                ]
              },
              "duration_min_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "duration_max_minutes": {
                "type": [
                  "number",
                  "null"
                ]
              },
              "is_in_station": {
                "type": "boolean",
                "default": true
              },
              "note_en": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "Take indoor escalators"
                ]
              },
              "note_zh": {
                "type": [
                  "string",
                  "null"
                ],
                "examples": [
                  "建议走站内扶梯"
                ]
              },
              "vertical_gap_note_zh": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "is_barrier_free": {
                "type": [
                  "boolean",
                  "null"
                ]
              },
              "source": {
                "type": "string",
                "enum": [
                  "amap",
                  "tencent",
                  "baidu",
                  "curated",
                  "manual",
                  "degraded",
                  "mock"
                ]
              }
            }
          },
          "walk_note_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Walk 350m East along the pedestrian mall to reach The Bund."
            ]
          },
          "walk_note_zh": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      },
      "access_point": {
        "type": [
          "object",
          "null"
        ],
        "additionalProperties": false,
        "properties": {
          "station_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "station_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路"
            ]
          },
          "station_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "East Nanjing Rd"
            ]
          },
          "access_no": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2",
              "7"
            ]
          },
          "access_name_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "2号口"
            ]
          },
          "access_name_en": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "Entrance 2"
            ]
          },
          "landmark_desc_zh": {
            "type": [
              "string",
              "null"
            ],
            "examples": [
              "南京东路步行街方向"
            ]
          },
          "landmark_desc_en": {
            "type": [
              "string",
              "null"
            ]
          },
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          }
        }
      }
    }
  },
  "station.schema.json": {
    "title": "CuratedStation",
    "type": "object",
    "required": [
      "station_id",
      "names",
      "lines",
      "access_points",
      "provenance"
    ],
    "additionalProperties": false,
    "properties": {
      "station_id": {
        "type": "string",
        "pattern": "^[a-z]{2}_stn_[0-9]{4,8}$",
        "examples": [
          "sh_stn_00107"
        ]
      },
      "names": {
        "type": "object",
        "required": [
          "zh-Hans",
          "en"
        ],
        "additionalProperties": false,
        "properties": {
          "zh-Hans": {
            "type": "string",
            "examples": [
              "中山公园"
            ]
          },
          "zh-Hant": {
            "type": "string"
          },
          "en": {
            "type": "string",
            "examples": [
              "Zhongshan Park"
            ]
          },
          "ja": {
            "type": "string"
          },
          "ko": {
            "type": "string"
          }
        }
      },
      "romanization": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "pinyin": {
            "type": "string",
            "examples": [
              "zhōng shān gōng yuán"
            ]
          },
          "pinyin_plain": {
            "type": "string",
            "examples": [
              "zhongshan gongyuan"
            ]
          }
        }
      },
      "coordinate": {
        "type": "object",
        "required": [
          "lat",
          "lng",
          "crs"
        ],
        "additionalProperties": false,
        "properties": {
          "lat": {
            "type": "number",
            "minimum": -90,
            "maximum": 90
          },
          "lng": {
            "type": "number",
            "minimum": -180,
            "maximum": 180
          },
          "crs": {
            "type": "string",
            "enum": [
              "WGS84",
              "GCJ-02",
              "BD-09"
            ]
          },
          "precision_m": {
            "type": "number",
            "minimum": 0,
            "default": 50,
            "description": "入口点级精度（非几何中心）"
          }
        }
      },
      "station_group_id": {
        "type": [
          "string",
          "null"
        ]
      },
      "is_transfer_hub": {
        "type": "boolean",
        "default": false
      },
      "vertical_complexity": {
        "type": "string",
        "enum": [
          "flat",
          "multi_level",
          "deep_multi_level"
        ],
        "default": "flat"
      },
      "lines": {
        "type": "array",
        "minItems": 1,
        "items": {
          "type": "object",
          "required": [
            "code",
            "name_en",
            "name_zh"
          ],
          "additionalProperties": false,
          "properties": {
            "code": {
              "type": "string",
              "examples": [
                "2"
              ]
            },
            "name_en": {
              "type": "string",
              "examples": [
                "Line 2 (Green)"
              ]
            },
            "name_zh": {
              "type": "string",
              "examples": [
                "2 号线"
              ]
            },
            "color_hex": {
              "type": "string",
              "pattern": "^#[0-9A-Fa-f]{6}$",
              "examples": [
                "#00A650"
              ]
            },
            "directions": {
              "type": "array",
              "items": {
                "type": "object",
                "required": [
                  "name_en",
                  "name_zh"
                ],
                "additionalProperties": false,
                "properties": {
                  "name_en": {
                    "type": "string",
                    "examples": [
                      "Towards Pudong Int'l Airport"
                    ]
                  },
                  "name_zh": {
                    "type": "string",
                    "examples": [
                      "往浦东国际机场方向"
                    ]
                  },
                  "terminal_station_id": {
                    "type": [
                      "string",
                      "null"
                    ]
                  }
                }
              },
              "default": []
            }
          }
        }
      },
      "access_points": {
        "type": "array",
        "description": "进出站口。这是「Enter via: Entrance 2 (2号口)」的唯一数据来源，三方 API 通常不返回。",
        "items": {
          "type": "object",
          "required": [
            "access_no",
            "kind",
            "name_zh",
            "name_en"
          ],
          "additionalProperties": false,
          "properties": {
            "access_no": {
              "type": "string",
              "examples": [
                "2",
                "7",
                "A"
              ]
            },
            "kind": {
              "type": "string",
              "enum": [
                "entrance",
                "exit",
                "both"
              ]
            },
            "name_zh": {
              "type": "string",
              "examples": [
                "2号口"
              ]
            },
            "name_en": {
              "type": "string",
              "examples": [
                "Entrance 2"
              ]
            },
            "coordinate": {
              "type": "object",
              "required": [
                "lat",
                "lng",
                "crs"
              ],
              "additionalProperties": false,
              "properties": {
                "lat": {
                  "type": "number",
                  "minimum": -90,
                  "maximum": 90
                },
                "lng": {
                  "type": "number",
                  "minimum": -180,
                  "maximum": 180
                },
                "crs": {
                  "type": "string",
                  "enum": [
                    "WGS84",
                    "GCJ-02",
                    "BD-09"
                  ]
                },
                "precision_m": {
                  "type": "number",
                  "minimum": 0,
                  "default": 50,
                  "description": "入口点级精度（非几何中心）"
                }
              }
            },
            "landmark_desc_zh": {
              "type": "string",
              "examples": [
                "南京东路步行街方向"
              ]
            },
            "landmark_desc_en": {
              "type": "string",
              "examples": [
                "Towards Nanjing Road Pedestrian Street"
              ]
            },
            "is_barrier_free": {
              "type": [
                "boolean",
                "null"
              ]
            },
            "has_escalator": {
              "type": [
                "boolean",
                "null"
              ]
            },
            "is_open": {
              "type": [
                "boolean",
                "null"
              ]
            }
          }
        },
        "default": []
      },
      "interior_transfers": {
        "type": "array",
        "description": "站内换乘。支撑「Long Transfer Warning: Walking distance ~320m / 6-8 mins / Take indoor escalators」。",
        "items": {
          "type": "object",
          "required": [
            "from_line_code",
            "to_line_code",
            "walking_distance_meters",
            "minutes_min",
            "minutes_max"
          ],
          "additionalProperties": false,
          "properties": {
            "from_line_code": {
              "type": "string"
            },
            "to_line_code": {
              "type": "string"
            },
            "walking_distance_meters": {
              "type": "integer",
              "minimum": 0,
              "examples": [
                320
              ]
            },
            "minutes_min": {
              "type": "number",
              "minimum": 0,
              "examples": [
                6
              ]
            },
            "minutes_max": {
              "type": "number",
              "minimum": 0,
              "examples": [
                8
              ]
            },
            "is_in_station": {
              "type": "boolean",
              "default": true
            },
            "note_zh": {
              "type": [
                "string",
                "null"
              ],
              "examples": [
                "建议走站内扶梯"
              ]
            },
            "note_en": {
              "type": [
                "string",
                "null"
              ],
              "examples": [
                "Take indoor escalators"
              ]
            },
            "vertical_gap_note_zh": {
              "type": [
                "string",
                "null"
              ]
            },
            "is_barrier_free": {
              "type": [
                "boolean",
                "null"
              ]
            }
          }
        },
        "default": []
      },
      "coverage": {
        "type": "object",
        "required": [
          "tier",
          "completeness"
        ],
        "additionalProperties": false,
        "properties": {
          "tier": {
            "type": "string",
            "enum": [
              "core_hub",
              "major",
              "standard"
            ],
            "default": "standard"
          },
          "completeness": {
            "type": "string",
            "enum": [
              "full",
              "partial",
              "access_points_only",
              "none"
            ],
            "default": "partial"
          }
        },
        "x-changed": "新增"
      },
      "provenance": {
        "type": "object",
        "required": [
          "source",
          "updated_at"
        ],
        "additionalProperties": false,
        "properties": {
          "source": {
            "type": "string",
            "enum": [
              "amap",
              "tencent",
              "baidu",
              "curated",
              "manual",
              "degraded",
              "mock"
            ]
          },
          "updated_at": {
            "type": "integer"
          },
          "reviewed_by": {
            "type": "string"
          },
          "field_verified_at": {
            "type": "object",
            "additionalProperties": {
              "type": "integer"
            }
          }
        }
      }
    },
    "$defs": {}
  },
  "api.schema.json": {
    "version": "0.1.0-draft",
    "base": "/api/v1",
    "auth": {
      "scheme": "Bearer JWT",
      "rules": [
        "所有端点必须鉴权（PRD 无鉴权设计，裸 trip_id 可被遍历）",
        "trip 资源必须校验 trip.user_id == token.sub，否则 403",
        "地图三方 key 一律不下发客户端；所有三方调用经服务端代理"
      ]
    },
    "endpoints": [
      {
        "id": "create_trip",
        "method": "POST",
        "path": "/trips",
        "purpose": "模块一：创建行程骨架（面板①提交）",
        "request_schema": "trip.schema.json#/properties/user_profile + anchors + budget? + cost_inputs?",
        "response_schema": "trip.schema.json",
        "notes": "服务端生成 trip_id/version/created_at，并按 duration 初始化 days[]（day_status=empty，daily_start_local 默认 09:00）"
      },
      {
        "id": "get_trip",
        "method": "GET",
        "path": "/trips/{trip_id}",
        "response_schema": "trip.schema.json",
        "notes": "离线包生成也走此端点（客户端本地固化）；动态返回只读 budget_assessment，人均费用来自 cost_inputs 及已选交通，缺失费用不当作 0。"
      },
      {
        "id": "patch_trip_config",
        "method": "PATCH",
        "path": "/trips/{trip_id}",
        "request_schema": "trip.schema.json#/properties/user_profile | anchor_* | budget | cost_inputs | days[].daily_start_local | days[].start_anchor | days[].end_anchor | days[].end_transit",
        "notes": "改偏好/锚点/每日起点/预算/费用；带 If-Match: version，冲突返回 VERSION_CONFLICT。cost_inputs 为完整费用设置，null 清空；只改预算或费用保留交通。end_transit 保存当天最后一区段，改点位或重排后失效。"
      },
      {
        "id": "list_pois",
        "method": "GET",
        "path": "/pois",
        "query": {
          "city": "shanghai",
          "interests": "modern_skyline,nature",
          "bbox": "minLng,minLat,maxLng,maxLat",
          "category_level1": "history_culture",
          "limit": "≤200",
          "cursor": "分页游标"
        },
        "response_schema": "poi.schema.json[]",
        "notes": "模块二：排序权重按 mappings.json#/interests_weight 计算，服务端排序"
      },
      {
        "id": "get_poi",
        "method": "GET",
        "path": "/pois/{poi_id}",
        "response_schema": "poi.schema.json",
        "notes": "模块二详情抽屉：4 行展示的字段→文案→空值降级见 mappings.json#/drawer_field_map"
      },
      {
        "id": "add_stop",
        "method": "POST",
        "path": "/trips/{trip_id}/days/{day_index}/stops",
        "request_schema": {
          "poi_id": "string（景点必填）",
          "stop_order": "integer?",
          "user_preferred_arrival_local": "HH:mm?",
          "force": "boolean（Rule-01 用户已确认时置 true，需带 conflict_confirm_token）",
          "stop_type": "poi | hotel | arrival_anchor | departure_anchor，默认 poi",
          "anchor": "trip.schema.json#/$defs/day_anchor?（住宿/口岸；省略使用行程配置）",
          "planned_dwell_minutes": "integer 0..720?（住宿可表示睡眠时长）"
        },
        "response_schema": {
          "trip": "trip.schema.json",
          "notices": "trip.schema.json#/$defs/notice[]"
        },
        "notes": "触发 rules.json 的 add_stop 事件；命中 Rule-01 且未确认时返回 RULE_HARD_CONFLICT + conflict_confirm_token"
      },
      {
        "id": "reorder_stops",
        "method": "PUT",
        "path": "/trips/{trip_id}/days/{day_index}/stops",
        "request_schema": {
          "stop_order": [
            "stop_id 有序数组（兼容无歧义的旧 poi_id 数组）"
          ],
          "locked_ids": [
            "string"
          ]
        },
        "response_schema": {
          "trip": "trip.schema.json",
          "notices": "notice[]",
          "recomputed_segments": "route.schema.json[]"
        },
        "notes": "拖拽排序。**重算范围与调用预算见 mappings.json#/cache_keys.call_budget**；locked 的点不得被自动移动"
      },
      {
        "id": "remove_stop",
        "method": "DELETE",
        "path": "/trips/{trip_id}/days/{day_index}/stops/{stop_id}",
        "notes": "以稳定 stop_id 删除单个停靠点；兼容只匹配一个停靠点的旧 poi_id；同时清理该点产生的 notice"
      },
      {
        "id": "evaluate_rules",
        "method": "POST",
        "path": "/trips/{trip_id}/rules:evaluate",
        "request_schema": {
          "day_index": "integer?",
          "trigger": "rules.json#/execution_model/trigger_events"
        },
        "response_schema": {
          "notices": "notice[]",
          "evaluated_rules": [
            "rule_id"
          ],
          "skipped_rules": [
            {
              "rule_id": "string",
              "reason": "missing_data|no_match|locked"
            }
          ]
        },
        "notes": "纯求值，不落库。用于前端本地重算与联调（skipped_rules 让缺失数据可见）"
      },
      {
        "id": "confirm_conflict",
        "method": "POST",
        "path": "/trips/{trip_id}/conflicts/{notice_id}/confirm",
        "request_schema": {
          "decision": "proceed_anyway|reject"
        },
        "notes": "落库 notice.outcome 与 confirmed_at；改期后按 expires_on_reorder 失效"
      },
      {
        "id": "compute_routes",
        "method": "POST",
        "path": "/trips/{trip_id}/days/{day_index}/routes:compute",
        "request_schema": {
          "modes": [
            "transit",
            "taxi",
            "walk"
          ],
          "prefetch": "boolean"
        },
        "response_schema": "route.schema.json[]",
        "notes": "模块四。服务端做缓存/并发/降级；返回 degraded_reason 时 HTTP 仍为 200（见 errors.json DEGRADED_RESULT）"
      },
      {
        "id": "get_station",
        "method": "GET",
        "path": "/stations/{station_id}",
        "response_schema": "station.schema.json",
        "notes": "3.5 微观增强的进出站口/换乘数据来源；coverage.completeness=none 时前端整体降级"
      },
      {
        "id": "export_offline_package",
        "method": "POST",
        "path": "/trips/{trip_id}/offline-package",
        "response_schema": {
          "package_version": "string",
          "trip_version": "integer",
          "generated_at": "UTC秒",
          "payload": "按 mappings.json#/offline_package.must_include 裁剪"
        },
        "notes": "模块五。体积 ≤5MB；含问路卡模板键而非最终文案（多语言）"
      },
      {
        "id": "health",
        "method": "GET",
        "path": "/health",
        "response_schema": {
          "ok": "boolean",
          "upstreams": {
            "amap": "up|degraded|down",
            "tencent": "…",
            "baidu": "…"
          }
        },
        "notes": "降级率与三方时延的监控入口（PRD 无埋点设计）"
      },
      {
        "id": "preview_trip",
        "method": "POST",
        "path": "/trips:preview",
        "purpose": "校验创建输入并返回只读骨架，不保存行程",
        "request_schema": "同 create_trip",
        "response_schema": "trip.schema.json"
      },
      {
        "id": "generate_recommendations",
        "method": "POST",
        "path": "/recommendations:generate",
        "purpose": "独立推荐模块生成指定空白游玩日的只读方案",
        "request_schema": "recommendation.schema.json#/$defs/generate_request",
        "response_schema": "recommendation.schema.json",
        "notes": "恰好提供 trip_id 或 setup；选中日期不重复，不改已安排日期，交通时间仅为规划估算。"
      },
      {
        "id": "create_recommended_trip",
        "method": "POST",
        "path": "/trips:recommended",
        "purpose": "校验整个推荐方案并原子创建行程",
        "request_schema": "recommendation.schema.json#/$defs/create_request",
        "response_schema": "trip.schema.json",
        "notes": "不先落盘空骨架；任何 POI 或日期不合法时整体失败。"
      },
      {
        "id": "apply_recommendations",
        "method": "POST",
        "path": "/trips/{trip_id}/recommendations:apply",
        "purpose": "原子填充现有行程的空白日期",
        "request_schema": "recommendation.schema.json#/$defs/apply_request",
        "response_schema": "trip.schema.json",
        "notes": "必须携带 If-Match，重新核对版本与目标日为空；一次递增版本，只读推荐理由不持久化。"
      }
    ],
    "cross_cutting": {
      "pagination": {
        "style": "cursor",
        "default_limit": 50,
        "max_limit": 200
      },
      "rate_limit": {
        "per_user_per_hour": 60,
        "concurrent_sessions": 8,
        "headers": [
          "X-RateLimit-Limit",
          "X-RateLimit-Remaining",
          "Retry-After"
        ]
      },
      "timeouts": {
        "client_connect_ms": 1000,
        "client_read_ms": 2000,
        "retry": {
          "max": 2,
          "backoff_ms": [
            300,
            800
          ],
          "retry_on": [
            "UPSTREAM_TIMEOUT",
            "UPSTREAM_RATE_LIMITED（仅非 429）"
          ]
        }
      },
      "circuit_breaker": {
        "error_rate_threshold": 0.5,
        "window_seconds": 30,
        "open_seconds": 5
      },
      "observability": {
        "required_events": [
          "route_compute",
          "rule_triggered",
          "degraded",
          "cache_hit",
          "offline_package_written"
        ],
        "alert": "降级率 5 分钟 >10% 触发告警"
      }
    },
    "$defs": {}
  },
  "recommendation.schema.json": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "plan",
      "days",
      "skipped_days",
      "warnings",
      "trip_id",
      "trip_version"
    ],
    "properties": {
      "plan": {
        "$ref": "#/$defs/plan"
      },
      "days": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "day_index",
            "date",
            "stops"
          ],
          "properties": {
            "day_index": {
              "type": "integer",
              "minimum": 1,
              "maximum": 15
            },
            "date": {
              "type": "string",
              "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
            },
            "stops": {
              "type": "array",
              "items": {
                "$ref": "#/$defs/detail_stop"
              },
              "maxItems": 6
            }
          }
        },
        "maxItems": 15
      },
      "skipped_days": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "day_index",
            "reason"
          ],
          "properties": {
            "day_index": {
              "type": "integer",
              "minimum": 1,
              "maximum": 15
            },
            "reason": {
              "type": "string"
            }
          }
        },
        "maxItems": 15
      },
      "warnings": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "trip_id": {
        "type": [
          "string",
          "null"
        ]
      },
      "trip_version": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 1
      }
    },
    "title": "Recommendation",
    "description": "只读推荐输出；估算信息与推荐理由不写入冻结行程字段。",
    "$defs": {
      "stop": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "poi_id",
          "planned_dwell_minutes"
        ],
        "properties": {
          "poi_id": {
            "type": "string",
            "pattern": "^[a-z]{2}_poi_[0-9]{5,8}$"
          },
          "planned_dwell_minutes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 720
          }
        }
      },
      "plan_day": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "day_index",
          "stops"
        ],
        "properties": {
          "day_index": {
            "type": "integer",
            "minimum": 1,
            "maximum": 15
          },
          "stops": {
            "type": "array",
            "items": {
              "$ref": "#/$defs/stop"
            },
            "maxItems": 6
          }
        }
      },
      "plan": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "days"
        ],
        "properties": {
          "days": {
            "type": "array",
            "items": {
              "$ref": "#/$defs/plan_day"
            },
            "maxItems": 15
          }
        }
      },
      "detail_stop": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "poi_id",
          "name_zh",
          "planned_dwell_minutes",
          "reasons",
          "warnings"
        ],
        "properties": {
          "poi_id": {
            "type": "string",
            "pattern": "^[a-z]{2}_poi_[0-9]{5,8}$"
          },
          "name_zh": {
            "type": "string"
          },
          "planned_dwell_minutes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 720
          },
          "reasons": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "warnings": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "estimated_arrival_local": {
            "type": "string",
            "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"
          },
          "estimated_departure_local": {
            "type": "string",
            "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"
          }
        }
      },
      "setup": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "user_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "user_profile": {
            "type": "object"
          },
          "duration_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 15
          },
          "start_date": {
            "type": "string",
            "format": "date"
          },
          "daily_start_local": {
            "type": "string",
            "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"
          },
          "anchor_arrival": {
            "type": "object"
          },
          "anchor_hotel": {
            "type": "object"
          },
          "anchor_departure": {
            "type": [
              "object",
              "null"
            ]
          },
          "budget": {
            "type": [
              "object",
              "null"
            ]
          },
          "cost_inputs": {
            "type": "object"
          }
        },
        "required": [
          "user_profile",
          "duration_days",
          "anchor_arrival",
          "anchor_hotel"
        ],
        "description": "沿用 POST /trips 的创建输入；完整业务约束由 trip_engine 校验。"
      },
      "generate_request": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "day_indices"
        ],
        "properties": {
          "trip_id": {
            "type": "string",
            "minLength": 1
          },
          "setup": {
            "$ref": "#/$defs/setup"
          },
          "day_indices": {
            "type": "array",
            "items": {
              "type": "integer",
              "minimum": 1,
              "maximum": 15
            },
            "minItems": 1,
            "maxItems": 15,
            "uniqueItems": true
          }
        },
        "oneOf": [
          {
            "required": [
              "trip_id"
            ],
            "not": {
              "required": [
                "setup"
              ]
            }
          },
          {
            "required": [
              "setup"
            ],
            "not": {
              "required": [
                "trip_id"
              ]
            }
          }
        ]
      },
      "create_request": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "setup",
          "plan"
        ],
        "properties": {
          "setup": {
            "$ref": "#/$defs/setup"
          },
          "plan": {
            "$ref": "#/$defs/plan"
          }
        }
      },
      "apply_request": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "plan"
        ],
        "properties": {
          "plan": {
            "$ref": "#/$defs/plan"
          }
        }
      }
    }
  }
}'''

SCHEMAS = json.loads(_RAW)


def get(schema_name: str) -> dict:
    """取内联后的 schema（自包含，可直接交给标准校验器）。"""
    return SCHEMAS[schema_name]


def validate(instance, schema_name: str) -> list:
    """返回错误列表（空表示通过）。未安装 jsonschema 时抛 RuntimeError。"""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("校验需要 jsonschema：pip install jsonschema") from exc
    validator = Draft202012Validator(SCHEMAS[schema_name])
    return sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))


def is_valid(instance, schema_name: str) -> bool:
    return not validate(instance, schema_name)
