# InboundRoute PRD 第 3 章「核心功能模块规格」及第 4 章实体定义 —— 完整性与可实现性评审

审查对象：`新建 DOCX 文档.docx`（V1.0.0-Release，文档状态自称「研发就绪（Ready for Dev）」）
审查范围：第 3 章五个模块（行程初始设定引擎 / 地图互动选点与 POI 详情层 / 多日行程调度与冲突引擎 / 微观门到门交通路线规划 / 现场求助与离线辅助），以及第 4 章 `POIMaster`、`TripInstance` 中与之相关的字段。

---

## 一、最关键问题摘要（5 条）

**1. 时间基准不闭合：Day 1 的日期与时间戳自相矛盾，且全篇没有时区定义——Rule-01 闭馆日校验在实现层无法可靠成立。**
`TripInstance.days[0].date` 写死为 `"2026-10-12"`（周一），而 `anchor_arrival.timestamp` = `1789728000` 换算为 UTC 2026-09-18 10:40（周五），与 `"2026-10-12"` 相差 24 天；同时该字段用 Unix 秒级整数、`days[].date` 用 `"2026-10-12"` 字符串、`stop.target_arrival_time` 用 `"19:30"` 裸时刻字符串，三种时间类型混用却无时区/单位/格式说明。Rule-01 的判定完全依赖「`$Date(Day_n)` 对应的星期」，时区偏移一天即会让周一闭馆的馆被放行。

**2. 多日时序推演缺一个必需输入：每日起点时刻。**
字段表只定义了「Accommodation …… 自动设定为每日固定起点（除 Day 1 首站由 Arrival Anchor 承接外）及每日最终收敛终点」，`TripInstance` 里却没有任何 `daily_start_time` / `hotel_depart_time` 字段。Day 1 有权重规则 `T_start = T_arrival + 90 min`，Day 2..N 没有任何起始时刻来源，而 Rule-02 的「系统计算该节点预期抵达时间早于……亮灯时间点」和 `target_arrival_time` 都建立在逐点时间轴之上——时间轴在 Day 2 直接断链。

**3. 规则集的流程图与规则清单不是同一套，且完全没有裁决顺序。**
3.3 顶部流程图只有三个框：`[规则 1: 闭馆日强阻断校验]`、`[规则 2: 地理跨度离散度计算]`、`[规则 3: 亮灯时序优化建议]`；而正文规则清单是 `Rule-01 闭馆日强冲突`、`Rule-02 亮灯时序自适应优化`、`Rule-03 地理跨度预警`、`Rule-04 同质化文化审美疲劳提示`。流程图与正文的编号错位，且 `Rule-03`、`Rule-04` 在流程图中不存在。多规则同时命中时谁先提示、谁被覆盖、用户忽略警告后是否重新入队，均无定义。

**4. 数据缺失时全部落入未定义行为，且存在正例中的直接矛盾。**
`"closure_days": []` 无法区分「不闭馆」与「闭馆数据未采集」；`"last_entry_time": null` 与抽屉要求展示的 `Last Entry： 明确截止入场时间（如 16:00 Last Entry）` 直接冲突；Rule-02 依赖的「当前季节亮灯时间点 $T_{light}$」在实体里只有 `light_up_schedule: {summer, winter}` 两个区间，没有点、也没有「summer/winter 对应哪些日期」的映射。`suggested_dwell_minutes` 是单值 `90`，而展示层承诺 `Suggested Dwell Time： 建议游览耗时（如 1.5 - 2 Hours）`。

**5. 交互层完全没有撤销、回滚与重算触发定义，只有一条无法验收的性能指标。**
NFR 要求「用户拖拽改变日程顺序后，微观路线重新计算与刷新响应耗时 ≤ 1.2 s」，但 3.2/3.3 未定义：拖拽以什么时机触发重算（落点即算 / 松手后防抖）、第三方地图 API 失败时前台展示什么、Rule-02 的 `[Move to Evening]` 一键调整重算失败后如何回滚。全文无 `undo`、无版本号、无历史栈字段。

---

## 二、按模块的问题清单

### 模块一：行程初始设定引擎（3.1 字段与业务逻辑规范）

`[严重度: 阻断] Pacing 档位区间不闭合并与「点位上限」语义冲突 —— 依据：Pacing / Pace 约束条件「对应单日建议游览点位上限：Relaxed ≤ 2；Balanced ≤ 4；Packed ≥ 5」 —— 影响：「Packed ≥ 5」是下界而非上界，且它与 Relaxed/Balanced 的「上限」逻辑不对称，无法据此实现任何校验；同时 3.1 只说「建议游览点位上限」，未定义超过上限时是拦截、警告还是自动挤压停留时长。上限失效会连带使 Rule-04 的计数阈值 `≥ 3` 失去意义 —— 建议补全：改为 `Relaxed 1-2 / Balanced 3-4 / Packed 5-6`（或仅给上限），并明确「超上限」的判定时机（加入时/重排后）与响应（软警告文案、是否可忽略、是否计入冲突计数）。`

`[严重度: 阻断] Party Composition 的 1.3 加权系数作用对象与叠加规则未定义 —— 依据：Party Composition 联动规则「选择 Family (Kids) 或 Senior 时，步行动线时间加权系数设为 1.3，优先推荐打车模式」，TripInstance 另有 `"walking_speed_factor": 1.0` —— 影响：1.3 是乘在「步行段耗时」还是「整个移动区间耗时」上未说明；`walking_speed_factor` 与 1.3 是相乘、取大还是后者覆盖前者未说明；Senior 与 Family(Kids) 同时选中（控件为「胶囊单选」故不可同时，但 `walking_speed_factor` 是独立可写字段）时以谁为准未说明。「优先推荐打车模式」的落地方式（调整 3.4 三组数据的默认 Tab、排序还是直接隐藏 Transit）也没有定义 —— 建议补全：给出系数作用的字段路径（如仅作用于 `transit_from_previous.duration_seconds` 中的步行子段）、叠加公式、有效区间（如 0.5–2.0），以及「优先推荐」的具体阈值和默认展开项。`

`[严重度: 阻断] Arrival Anchor 的跨零点与跨天行为未定义 —— 依据：Arrival Anchor 联动规则「固定为 Day 1 的起点 P0。自动计算：有效活动起始时间点 T_start = T_arrival + 90 min（预留出关与交通缓冲）」 —— 影响：当 `T_arrival` 为 23:30 时 `T_start` 落到次日 01:00，此时「Day 1 的起点」是否顺延到 Day 2、Day 1 是否退化为空日程、以及酒店锚点是否仍强制作为首日终点，全部没有定义。红眼航班是入境自由行的常见场景，属高频边界 —— 建议补全：明确 T_start 跨零点时的三条裁决（Day 1 是否保留、是否允许 Day 1 为空、Day 1 的终点锚点是否仍为酒店），并给 `T_start` 落点超出当日可用时段（如凌晨）时的降级文案。`

`[严重度: 高] Duration 与 POI 未装载的兜底缺失 —— 依据：Duration (Days)「必填，范围 1 ~ 15 天」及其联动规则「初始化对应数量的每日日程容器（Day 1 ... Day N）」 —— 影响：如果用户选了 15 天却只选出 6 个 POI（或 Interests 选填为空导致推荐列表为空，见下条），系统没有任何「未装载天数」的表示：`TripInstance.days` 无 `day_status`，也无「待排点池 / unassigned POIs」容器，无法表达「这些 POI 还没排」 —— 建议补全：在 `TripInstance` 增加未分配点集合与 `days[].day_status`（如 empty / partial / fulfilled / locked），并定义空日程日的界面与是否允许保存行程。`

`[严重度: 高] Interests 选填为空时的排序权重未定义 —— 依据：Interests「选填：Modern Skyline, History & Culture, Local Life, Nature」，联动规则「控制地图首次载入时，右侧/底层推荐 POI 列表的排序权重分值」 —— 影响：未给出权重分值的计算方式（命中一个标签加多少分、多标签是否累加、`category`/`sub_category` 如何映射到这四个标签），也未定义「未选择任何 Interests」时的默认排序，导致「首次载入推荐列表」这一步无法实现 —— 建议补全：给出权重公式（如命中数 × 权重 + 热度分）、`category`→`Interests` 的映射表、以及空选择时的默认排序策略。`

`[严重度: 中] Arrival Anchor 与 activity_start_time 的字段语义重复 —— 依据：`anchor_arrival` 同时含 `"timestamp": 1789728000` 与 `"activity_start_time": 1789733400`，而字段表规则写的是「T_start = T_arrival + 90 min」 —— 影响：`T_arrival` 指哪一个不确定；若是 `timestamp`，则 `activity_start_time` 是可由公式推导的冗余字段，写入权与冲突时的优先级（客户端算还是服务端算、谁覆盖谁）未定义。样例恰好是 `1789733400 − 1789728000 = 5400 秒`，说明示例按公式填写，但工程上没有约束 —— 建议补全：明确唯一权威字段、推导侧、以及二者不一致时的处理。`

`[严重度: 中] 用户侧无「离开锚点」，Day N 无收尾约束 —— 依据：字段表仅定义 Arrival Anchor 与 Accommodation；3.4 起止序列写作「P0 → P1 → P2 … → Photel」 —— 影响：出境航班/高铁日的最后一段（酒店 → 机场/车站）无锚点、无「提前 N 小时抵达枢纽」缓冲规则，Day N 的时间轴无法推演，也无法给出「今日必须几点从最后一个景点出发」的提示 —— 建议补全：增加 Departure Anchor（日期 + 时刻 + 口岸 POI + 国际/国内航班缓冲分钟），并把 Photel 之后的 `P_{hotel} → P_departure` 纳入序列定义。`

`[严重度: 中] 锚点图钉的可修改性未定义 —— 依据：3.2 常驻图层基准「常驻锚点图钉：到达口岸（飞机/高铁图标）、酒店位置（床位图标），视觉不可被用户误删」 —— 影响：只保证了「不可误删」，没定义如何「改」——用户发现酒店订错了或口岸选错时，是回到初始化页、长按重选，还是只能重建行程；以及修改酒店后已装载的多日日程是否清空 —— 建议补全：明确锚点的编辑入口、编辑后对 `days[].ordered_stops` 的处理策略（保留并重算 / 提示清空 / 保留并要求用户确认）。`

### 模块二：地图互动选点与 POI 详情层（3.2 交互与展现规范）

`[严重度: 阻断] POI 图钉状态机不闭合：已加入当日但未选中的状态缺失 —— 依据：POI 动态图钉状态机仅三态「Default」「Added-Other-Day：已加入其他天……右上角显示角标（如 D2）」「Selected-Current-Day：当前工作日选中，高亮主体色彩，显示当日游览序号（如 1, 2, 3）」 —— 影响：一个已加入「当前浏览天数」但未被点击选中的图钉，既不是 Default（已加入）、也不是 Added-Other-Day（不是其他天）、也未必是 Selected-Current-Day（未选中）——这是最常见的中态，却无定义，前端无法渲染，测试无法枚举用例。同时缺「冲突态」（Rule-01 用户选择 Proceed anyway 后「卡片打上红底警告标签」，但图钉角标是否同步变红未定义）与「被拦截态」 —— 建议补全：给出状态全集与迁移表，至少补 `Added-Current-Day-Unselected`、`Added-Conflict-Warned`，并定义每个状态的角标/灰度/序号显隐规则，以及状态迁移的触发事件清单（Add / Remove / Drag / Move to Evening / Proceed anyway / 切换浏览日）。`

`[严重度: 高] 同一 POI 出现在多天时的角标规则缺失 —— 依据：Added-Other-Day 定义为「已加入其他天，灰度弱化显示，右上角显示角标（如 D2）」 —— 影响：示例只给了单角标 `D2`。若同一 POI 同时存在于 D2 与 D5，是显示 `D2`、`D2/D5` 还是 `D2+1`？是否允许同一点重复装载（Rule-01 的文案「Proceed anyway」也暗示可能重复进入）未定义 —— 建议补全：明确是否允许多日重复装载；若允许，给出多角标的展示与点击行为（如点击列出所有天并跳转）。`

`[严重度: 高] 详情抽屉的营业时间/截止入场/亮灯时间没有到字段的映射与空值降级 —— 依据：运营约束数据卡要求展示「Opening & Closure： 标明常规营业时间及特殊闭馆规律（如 Closed on Mondays）」「Last Entry： 明确截止入场时间（如 16:00 Last Entry）」「Light-up Hours（夜景/亮灯专属）： 针对具备夜景特性的 POI，显示季节性亮灯窗口（如 19:00 - 22:00 (Summer)）」「Suggested Dwell Time： 建议游览耗时（如 1.5 - 2 Hours）」；而 `POIMaster` 对应字段为 `"standard_opening_hours": "00:00 - 24:00"`、`"last_entry_time": null`、`"light_up_schedule": {"summer": "19:00 - 23:00", "winter": "18:00 - 22:00"}`、`"suggested_dwell_minutes": 90` —— 影响：四处不一致——① `closure_days` 是集合而展示文案是自然语言 `Closed on Mondays`，二者转换规则未给；② `last_entry_time` 为 `null` 时该行是否整行隐藏未定义；③ `standard_opening_hours` 为 `"00:00 - 24:00"` 这种 24 小时串时展示什么、与 `light_up_schedule` 是否合并展示未定义；④ 展示是区间（`1.5 - 2 Hours`）而字段是单值 `90`，区间从何而来未定义 —— 建议补全：为四行各给「字段 → 文案模板 → 空值降级」三列映射表，并统一停留时长的单值/区间表示。`

`[严重度: 中] Add to Day [X] 的冲突判定范围与「已加入后改期」的行为未定义 —— 依据：操作触发项「底部常驻按钮：Add to Day [X]。若当前选择日期与闭馆日冲突，按钮呈现黄色警示态，点击弹出确认二次阻断对话框」 —— 影响：判定只提「闭馆日冲突」，未提及 `last_entry_time`、营业时段、`light_up_required`（Rule-02 属软约束，是否在此处也提示未定义）；更重要的是：用户确认 Proceed anyway 把 POI 加入 Day X 之后，若又把它拖到 Day Y（或把 Day X 整体挪动日期），是否重新执行 Rule-01 校验、红色警示标签是否自动清除，均未定义 —— 建议补全：明确按钮态判定的规则集合；明确「改期/改日」触发全量重校验，并定义历史确认（Proceed anyway）是否随改期失效。`

`[严重度: 低] 三行标头的拼音来源与多音字处理未定义 —— 依据：三行标头展示「Line 1 (大字英文)：The Bund」「Line 2 (带声调拼音)：wài tān」「Line 3 (中文规范汉字)：外滩」，`POIMaster` 中 `"name_pinyin": "wài tān"` —— 影响：`name_pinyin` 是人工维护还是自动生成未说明；长安（cháng ān / zhǎng ān）、厦门（xià mén / shà mén）这类多音字地名一旦自动生成带调拼音就会出错，而本模块的产品卖点正是「与现场实际安装的汉字+拼音路牌直观匹配」 —— 建议补全：规定 `name_pinyin` 为人工审核字段（不从 `name_zh` 自动推导），并定义缺失时的降级（隐藏 Line 2 而非显示错误拼音）。`

### 模块三：多日行程调度与冲突引擎（3.3 规则引擎设计）

`[严重度: 阻断] 流程图与规则清单编号错位，Rule-03/Rule-04 未进入执行链 —— 依据：3.3 流程图含「[规则 1: 闭馆日强阻断校验]」「[规则 2: 地理跨度离散度计算]」「[规则 3: 亮灯时序优化建议]」，正文清单为「Rule-01: 闭馆日强冲突（Hard Constraint）」「Rule-02: 亮灯时序自适应优化（Soft Constraint）」「Rule-03: 地理跨度预警（Geographic Spread Warning）」「Rule-04: 同质化文化审美疲劳提示（Soft Tag Alert）」 —— 影响：流程图的「规则 2」对应正文 `Rule-03`、流程图的「规则 3」对应正文 `Rule-02`；`Rule-03` 与 `Rule-04` 在流程图中完全没有节点。开发按流程图实现会漏掉两条规则，按正文实现则无从确定各规则的执行次序与短路条件（流程图的「否」「正常」「需优化」三分支隐含了短路语义，但 Rule-02 的「需优化/不需优化」并不构成继续执行的条件） —— 建议补全：重画一张与正文 Rule-01…Rule-04 编号一致的单向流程，为每条规则标明触发条件、是否为硬阻断、命中后是否继续执行后续规则、以及多条命中时的提示承载方式（Toast / 气泡 / Banner / 卡片标签能否叠加）。`

`[严重度: 阻断] 多规则同时命中的裁决顺序未定义，且存在前后依赖的循环 —— 依据：Rule-02 逻辑「若加入的 POI 具有 light_up_required = true 属性，且系统计算该节点预期抵达时间早于当前季节亮灯时间点 T_light」；Rule-02 响应「提供快捷交互操作：[Move to Evening]，一键将其排序调整至晚餐后或该日末位」；Rule-03 逻辑「计算相邻两点直线球面距离 Dist(P_i, P_{i+1})，若 Dist > 25 km 且该城市为高密度主城区」 —— 影响：① 规则顺序决定结论——先把点追加到当日末位再算跨度、与先提示跨度再让用户调整，会得到完全不同的提示；② `Rule-02` 依赖「预期抵达时间」，而抵达时间依赖当日排序，`[Move to Evening]` 又改变排序并可能重新触发 `Rule-03`（末位点与新邻点跨度）和 `Rule-04`（若移到晚间后同类计数变化），形成「排序 → 时间 → 规则 → 排序」的循环，文档未定义是单次前向传播还是迭代至收敛（迭代次数上限、不收敛时的取舍） —— 建议补全：定义固定执行顺序（建议 Rule-01 硬阻断 → 其余软规则并行求值 → 汇总后一次性渲染），说明软规则不改变排序、仅由用户显式操作改变，并给出重算的收敛策略与最大迭代次数。`

`[严重度: 阻断] $T_{light}$（季节亮灯时间点）在实体中不存在，跨季日期无判定依据 —— 依据：Rule-02 引用「当前季节亮灯时间点 T_light」，而 `POIMaster.operating_rules.light_up_schedule` 只有 `"summer": "19:00 - 23:00"`、`"winter": "18:00 - 22:00"` 两个区间；Rule-02 的响应文案为「Recommended after {T_light} for the best illuminated view.」 —— 影响：区间不是点，`T_light` 到底取区间起点、日落时刻还是固定常量没有定义；`summer` / `winter` 的日期切分（是否等同于节气、是否按月份、南北半球无关但中国南北差异大）未定义；9 月/10 月这类既非典型夏也非典型冬的行程取哪一档未定义；且若 `light_up_schedule` 缺季节键（数据缺失）时的降级行为未定义 —— 建议补全：增加 `light_up_schedule` 的季节生效日期区间（如 `{from: "05-01", to: "09-30"}`）与取点规则（如取起点减 30 分钟），明确无数据时不触发 Rule-02。`

`[严重度: 高] Rule-01「实体围合检票边界」的判定字段只有 `is_enclosed_attraction`，其赋值口径与后果未定义 —— 依据：Rule-01 逻辑「检查 $Date(Day_n)$ 对应的星期，若与目标 POI 的 closure_days 集合匹配，且该 POI 具备实体围合检票边界（非开放式街区）」；`POIMaster` 中对应字段为 `"is_enclosed_attraction": false`、`"closure_days": []` —— 影响：`is_enclosed_attraction` 是人工标注还是自动推导未说明；两者组合出的矩阵（围合+闭馆 / 开放+闭馆 / 围合+无闭馆数据）后果只定义了第一种；「开放式街区」遇 `closure_days` 命中时是完全放过还是降为软提示未定义 —— 建议补全：给出判定真值表（含空数据行），并明确 `is_enclosed_attraction` 的维护方与审核流程。`

`[严重度: 高] closure_days 的数据格式、时间范围语义与「特殊闭馆」表达力不足 —— 依据：`"closure_days": []` 无任何格式说明；抽屉要求展示「特殊闭馆规律（如 Closed on Mondays）」；1.2 痛点写「重点文博机构"周一闭馆"硬约束」 —— 影响：数组元素是整数 0-6、`MON` 还是中文「周一」未定义，且「0 代表周日还是周一」直接决定 Rule-01 判定对错；无法表达中国特有的三类闭馆：法定节假日期间闭馆（如春节、国庆的具体日期段）、临时闭馆/修缮、以及「周一闭馆但逢法定节假日照常开放」的例外 —— 这些恰好是 Rule-01 文案里「officially closed on Mondays」最容易误报的场景 —— 建议补全：定义为结构化对象，至少含 `{weekday: 1, exception_dates: [...], open_exception_dates: [...], special_closures: [{from, to, reason_zh, reason_en}], data_source, updated_at}`，并明确空数组的两种语义（无闭馆 / 未采集）区分方式。`

`[严重度: 高] Rule-03 的两个输入条件都不可实现 —— 依据：Rule-03 逻辑「计算相邻两点直线球面距离 Dist(P_i, P_{i+1})，若 Dist > 25 km 且该城市为高密度主城区」 —— 影响：① 「该城市为高密度主城区」没有任何数据依据——`POIMaster` 无 `city`、无 `district`、无城区/郊区标识，Destination City 联动规则只说「限制地图底图中心点坐标与 POI 搜索边界范围」，无法推出「是否主城区」；② 用「直线球面距离」做 25 km 阈值判定与产品自身「物理交通换乘盲区」「地理尺度失真」的定位相悖——上海浦东机场到人民广场直线约 30 km、实际轨道 1 小时以上，而黄浦江两岸直线 1 km 却要过江，直线距离既会漏报也会误报，且验证不了「Consider moving this spot to another day to save travel time」这句建议是否成立 —— 建议补全：明确阈值是按直线距离还是按路线时长（如「相邻两点直线距离 > 25 km 且预估交通耗时 > 60 分钟」双条件），补 `city` / `district` / `is_core_urban` 字段与城市级阈值配置表（25 km 目前只对上海成立，其他城市需参数化）。`

`[严重度: 高] Rule-04 的分类体系在实体里不存在 —— 依据：Rule-04 逻辑「单日行程容器内，若相同二级分类标签（如 #ClassicalGarden 或 #Temple）的 POI 计数 ≥ 3」 —— 影响：`POIMaster` 中 `"category": "Modern Skyline"`、`"sub_category": "Riverwalk"`，示例里根本没有 `ClassicalGarden` / `Temple`，而 3.1 的 Interests 枚举是 `Modern Skyline, History & Culture, Local Life, Nature`——`sub_category` 的取值域（枚举表）与 `category`/`Interests` 的映射关系缺失，Rule-04 无法统计；此外 Banner 文案写死「You have 3 similar historical sites today.」但阈值是 `≥ 3`，出现 5 个同类时文案为「5 similar」还是仍为「3」未定义；`sub_category` 为空时的兜底也未定义 —— 建议补全：给出完整的三级分类字典（含中英标签）、`category`↔`sub_category`↔`Interests` 的映射表、文案插值规则与空分类时的跳过逻辑。`

`[严重度: 中] Rule-02 只覆盖「到得太早」，不覆盖「到得太晚错过亮灯」 —— 依据：Rule-02 逻辑「且系统计算该节点预期抵达时间早于当前季节亮灯时间点 T_light」 —— 影响：若用户把外滩排在 23:30 之后（`light_up_schedule.summer` 上界为 `23:00`），到达时已过亮灯窗口，系统不做任何提示；反之 `"standard_opening_hours": "00:00 - 24:00"` 的开放式 POI 也不会因深夜到达被拦截。这与「规则与时空信息差……缺乏前置自动拦截机制」的产品痛点设定不一致 —— 建议补全：增加对称规则（抵达时间晚于亮灯区间结束时间时提示「今日亮灯窗口已结束，建议改期」），并明确以到达时间还是离开时间为判定基准。`

`[严重度: 中] Rule-01 的硬约束措辞与流程图的「可忽略」语义冲突 —— 依据：流程图「[规则 1: 闭馆日强阻断校验] ──── 是 ───➔ [Toast 拦截并标红卡片]」，Rule-01 响应「拦截操作，弹出 Alert：……Proceed anyway？ 若用户确认，卡片打上红底警告标签」，而 3.3 标题把 Rule-01 标为「（Hard Constraint）」 —— 影响：「强阻断/硬约束」在实现上到底是不允许加入、还是允许加入但打标，两处描述给出了不同强度的语义；测试无法判定「是否必须不可加入」 —— 建议补全：统一术语（建议改为「强冲突/需二次确认」），并明确硬约束的边界：是否存在任何条件下 Add 必须被拒绝（例如已确认的行程禁止加入闭馆 POI）。`

### 模块四：微观门到门交通路线规划（3.4 / 3.5）

`[严重度: 阻断] TripInstance 缺少距离字段，3.4 与 3.5 的展示项无数据来源 —— 依据：3.4「Transit（公共交通）： 最优方案耗时、费用、换乘次数、步行总长」「Walk/Bike（步行/骑行）： 距离 ≤ 3 km 时高亮展示，注明消耗步数」；而 `transit_from_previous` 只有 `"mode": "transit"`、`"duration_seconds": 1800`、`"cost_cny": 4.0`、`"transfer_count": 0`、`"has_long_transfer": false` —— 影响：① 无总距离字段，「距离 ≤ 3 km 时高亮」无法判定；② 无步行距离字段，「步行总长」无法展示；③ 「注明消耗步数」需要步长与步速假设，文档未给（`walking_speed_factor` 只有系数没有基准步速）；④ 「换乘步行段 walking_distance ≥ 200 m」（3.5）也无对应字段（`has_long_transfer` 是布尔结果，不是原始值） —— 建议补全：`transit_from_previous` 至少补 `distance_meters`、`walking_distance_meters`、`walking_duration_seconds`、`estimated_steps`、`polyline`、`departure_time`、`segments[]`（含线路、方向、进出站口、换乘步行距离）。`

`[严重度: 高] 时间戳单位/时区、坐标系统、坐标系混用均未定义 —— 依据：`"timestamp": 1789728000`（裸整数，无单位说明）、`"target_arrival_time": "19:30"`（裸时刻）、`coordinate: { "lat": 31.2397, "lng": 121.4900 }`（无坐标系说明）；技术边界为「高德/腾讯/百度 Web 服务」 —— 影响：① 1789728000 是秒还是毫秒、是 UTC 还是本地未说明（见摘要第 1 条，样例与 `days[0].date` 相差 24 天）；② 高德/腾讯用 GCJ-02、百度用 BD-09、GPS 用 WGS-84，`coordinate` 未标坐标系，混用会产生数百米级偏移；③ Rule-03 的 25 km 阈值与 3.5「步行段最后 300m」「Walk 350m East」这类米级指引对坐标偏移极其敏感，而产品痛点之一正是「海外地图由于坐标偏移和公共交通数据脱节」，自身却未定义坐标基准；④ `"cost_cny": 4.0` 只有人民币单值，与 3.4 要求的「预估费用区间」和多币种展示不匹配 —— 建议补全：在实体层显式声明 `crs: "GCJ-02"`、`tz: "Asia/Shanghai"`、`timestamp_unit: "s"`，给出费用区间字段（`cost_min_cny` / `cost_max_cny`）与展示货币换算口径。`

`[严重度: 高] 3.5 的微观数据增强所需字段，第三方 API 并不返回，缺「数据来源 + 缺失降级」定义 —— 依据：3.5 示例要求渲染「Line 2 (Green) 往 浦东国际机场方向 (Towards Pudong Int'l Airport)」「Enter via: Entrance 2 (2号口)」「Exit via: Exit 7 (7号口)」「Target Direction: Towards Nanjing Road Pedestrian Street (南京东路步行街方向)」「>>> Estimated transfer time: 6-8 mins. Take indoor escalators.」，文档自述为「针对 API 返回的标准 JSON 结构做以下清洗与规则补强」 —— 影响：进出站口编号、站台方向、站内换乘步行距离、室内扶梯/无障碍提示，均不在常规 Direction API 的公交返回中，需要架构图中提到的 `Curated Stations (核心站台库)` 支撑，但该库的字段、覆盖范围、维护方式、以及「库里没有这个站」时的降级渲染均未定义——实际结果是海外用户最需要的「2 号口 / Exit 7」在大部分站点会缺失 —— 建议补全：定义 Curated Stations 的字段模型与覆盖率要求（如仅覆盖核心城市 Top N 站点），并给出逐项缺失时的降级模板（缺失即隐藏该行，而不是显示占位或错误出口）。`

`[严重度: 高] 长距离换乘 30% 上浮的作用对象与幂等性未定义 —— 依据：3.5「若三方 API 返回的换乘步行段 walking_distance ≥ 200 m：自动在换乘卡片标注红色时钟角标，并在基础步行耗时上上浮 30% 呈现，明确打印：Long Transfer: ~X meters」 —— 影响：① 200 m 阈值与示例「Walking distance ~320m」一致，但示例同时给出「Estimated transfer time: 6-8 mins」——上浮后的值如何与 API 的基础耗时合成、30% 是乘在换乘步行段还是整段公交耗时上未定义；② 该上浮是否参与 Rule-02/Rule-03 的时序计算（即「预期抵达时间」是否已经含 30%）未定义，会导致同一行程出现两套时间；③ 若同一区间被多次重算，30% 是否会被重复叠加（缺少幂等标记）未定义 —— 建议补全：明确上浮的作用字段、是否计入时间轴推演、以及用原始值+系数而非改写值存储（保证幂等）。`

`[严重度: 中] 打车下客点纠偏的覆盖范围、失败行为与数据维护未定义 —— 依据：3.5「打车下客点（Drop-off Correction）： 针对大型景点，终点座标严禁使用景区几何中心点，后端强制将其重映射至地图 API 的 drop_off_locations 推荐停靠点（如外滩对应"圆明园路/北京东路路口"，避开中山东一路全线禁停违章区）」，`POIMaster` 中字段为 `"suggested_drop_off_coordinate": {...}` —— 影响：① 「针对大型景点」的判定阈值未给（按面积？按 `category`？）；② 该字段是 POI 实体的可选字段还是必填字段未说明，为 `null` 时是回落到 `coordinate` 还是拒绝给出打车方案未定义；③ 文档描述为「重映射至地图 API 的 drop_off_locations 推荐停靠点」，但实体里又是人工录入的 `suggested_drop_off_coordinate`（且带中英描述），两者优先级与冲突处理未定义；④ 兜底后用户看到的终点与 POI 位置不一致时，界面如何同时表达「下客点」与「景点入口」以及最后一段步行指引未定义 —— 建议补全：明确该字段的必填性与采集流程、优先级（人工 > API）、以及无效/缺失时的降级文案与「最后一段步行」的渲染规则。`

`[严重度: 中] 3.4 与 3.5 的调用次数与缓存策略缺失，与 NFR 的 1.2 s 指标不可调和 —— 依据：3.4「针对每个移动区间，同时展示三组横向切换数据」；NFR「用户拖拽改变日程顺序后，微观路线重新计算与刷新响应耗时 ≤ 1.2 s」 —— 影响：「同时展示三组」意味着每个区间至少 3 次第三方调用（Transit / 打车 / 步行骑行，且打车还分「预估费用区间、拥堵等级」可能需多次），一次拖拽会失效多个区间的缓存，未定义预取、结果缓存键、批量请求与限流配额；1.2 s 在无缓存与 API 限流下不可达 —— 建议补全：给出调用编排策略（哪些模式先取、是否懒加载非当前 Tab 的模式）、缓存键与 TTL、以及 API 限流触达时的排队/降级顺序。`

### 模块五：现场求助与离线辅助（3.6 / 3.7）

`[严重度: 阻断] 离线折叠单缺时间轴锚点，离线态无法推演每日时序 —— 依据：3.6「交互： 在无网络/弱网络环境下，顶部常驻提示 "Offline Mode"，允许用户离线折叠查看全天路线时序」，并自述「客户端采用 LocalStorage / IndexedDB 进行本地强缓存」 —— 影响：结合摘要第 2 条（无每日起点时刻），「全天路线时序」在 Day 2..N 无法生成；另外「路线时序」是否包含具体时刻、这些时刻是生成时快照还是离线时重算，未定义；若为快照，则用户在离线前最后一次改动后是否已刷新缓存也没有定义 —— 建议补全：明确离线包中固化的时序为「生成时刻快照 + 版本号」，并补每日起点时刻字段（这一点必须先在模块一解决）。`

`[严重度: 高] 离线包的内容范围、过期与失效策略未定义 —— 依据：3.6「技术实现： 客户端采用 LocalStorage / IndexedDB 进行本地强缓存」；NFR「单一完整行程离线文本及元数据包体积控制在 ≤ 5 MB（不含高清底图瓦片），支持通过 ServiceWorker 进行缓存」 —— 影响：未定义缓存哪些实体（是否含 `POIMaster` 的 `closure_days` / `light_up_schedule` / `suggested_drop_off_coordinate`、是否含 Curated Stations 的进出站口）、缓存有效期、POI 数据变更后的重新校验时机、以及用户在离线态做增删改后与在线态的一致性合并策略。产品承诺「允许用户离线折叠查看全天路线时序」，但若离线包缺进出站口数据，3.7 问路卡会退化为空 —— 建议补全：列出离线包的字段清单（明确必须包含站名/线号/进出站口，否则 3.7 不成立）、TTL、写冲突合并规则与「离线数据可能过期」的提示文案。`

`[严重度: 高] 问路卡的数据来源与生成规则未定义 —— 依据：3.7 触发机制「路线指引流中的每个核心节点（进站口、换乘处、出站口、最终落客点）旁边均设有一个醒目的 [Ask for Help / 问路卡] 悬浮按钮」；展示效果示例「请问去往 / 2 号线地铁站台怎么走？ / (Excuse me, which way is Line 2 platform?) / [Show Target Direction: Towards Pudong Int'l Airport]」 —— 影响：未定义每个节点类型的问路中文文案模板（示例只给了「去往地铁站台」一种，出站口、换乘处、落客点分别问什么没有模板）、`{Target Direction}` 的取值来源（是线路终点方向还是 POI 名）、以及当线路方向缺失（`Towards Pudong Int'l Airport` 这类信息来自 API 的 `direction` 字段，可能缺失）时问路卡显示什么 —— 建议补全：按节点类型给出中英双语模板表、占位符取值规则，以及占位符缺失时的降级文案（宁可只问「请问 2 号线怎么走」，也不要显示空方向）。`

`[严重度: 中] 问路卡的横竖屏与多模态可访问性未定义 —— 依据：3.7「点击后应用强制横屏或弹出高对比度模态弹窗（白底纯黑大字，字号 ≥ 32pt）」 —— 影响：「强制横屏」与「弹出模态弹窗」是两种互斥的实现，文档用「或」并列，未给出选定条件（平台差异？设备方向？）；同时未定义关闭路径（示例图有 `[X Close]` 但未说明是否支持返回键/手势）、是否允许截图/锁屏常亮（现场举着手机给路人看，熄屏是高频场景） —— 建议补全：确定单一实现（建议模态弹窗+内容横排），并明确关闭方式、防熄屏、以及是否持久化用户上次选择。`

`[严重度: 中] 离线/降级态的提示互斥关系未定义 —— 依据：3.6「顶部常驻提示 "Offline Mode"」；NFR 容错与降级「若三方地图 API 发生网络超时或限流，系统必须能够自动降级返回点对点直线距离粗算，并明确提示："Detailed public transit schedule temporarily unavailable. Showing direct orientation."」 —— 影响：两条提示可能同时出现（客户端离线 → 必然触发服务不可用降级），未定义提示的优先级、堆叠方式，以及降级后 3.4 的三组对比卡、3.5 的换乘预警、3.7 的问路卡按钮是否仍展示（直线距离粗算下「进站口/出站口」节点并不存在，问路卡应挂在哪里未定义） —— 建议补全：给出「在线完整 / 在线降级 / 离线」三态下的界面差异矩阵，明确各模块元素的显隐与提示文案优先级。`

### 第 4 章实体定义中的字段级问题（与上述模块相关）

`[严重度: 阻断] 必填/选填、取值范围、默认值、单位在实体定义中整体缺失 —— 依据：4.1 / 4.2 均为纯 JSON 示例（`POIMaster`、`TripInstance`），无字段表、无类型声明 —— 影响：`closure_days`、`standard_opening_hours`、`last_entry_time`、`is_enclosed_attraction`、`light_up_required`、`light_up_schedule`、`suggested_dwell_minutes`、`suggested_drop_off_coordinate`、`walking_speed_factor`、`target_arrival_time`、`planned_dwell_minutes`、`transit_from_previous.*` 无一标注是否必填、取值域、默认值与单位。「文档状态：研发就绪（Ready for Dev）」与实体层无字段规格之间存在明显落差 —— 建议补全：为两个实体各补一张字段表（字段名 / 类型 / 必填 / 取值域或枚举 / 默认值 / 单位 / 示例 / 关联规则 / 数据来源），并标注哪些字段来自第三方 API、哪些为人工维护。`

`[严重度: 高] 营业时间与亮灯时间用自由字符串表达，无解析规范 —— 依据：`"standard_opening_hours": "00:00 - 24:00"`、`"light_up_schedule": { "summer": "19:00 - 23:00", "winter": "18:00 - 22:00" }`、展示示例「19:00 - 22:00 (Summer)」 —— 影响：无法表达中国景区常见的复杂营业时段——分时段（如 `09:00-12:00, 13:30-17:00` 含午休）、按星期不同（如周一 09:00-12:00）、尾票/停止入场早于闭馆（`16:00 Last Entry` vs `17:00 Close`）、`24:00` 与 `00:00` 的跨零点表示、以及「(Summer)」括号语法本身。Rule-01/Rule-02 与 `[Add to Day X]` 的校验都需要对时间区间做机器判定 —— 建议补全：改为结构化时段数组（`[{days:[1,2,3,4,5], open:"09:00", close:"17:00"}, {date_range:["05-01","09-30"], open:"09:00", close:"18:30"}]`），并规定 `last_entry_time` 与 `close` 的关系。`

`[严重度: 高] `days[].ordered_stops[]` 缺关键字段与一致性约束 —— 依据：样例 stop 仅含 `"stop_order": 1`、`"poi_id"`、`"target_arrival_time": "19:30"`、`"planned_dwell_minutes": 90`、`"transit_from_previous"` —— 影响：① 无「离开时间」或「结束时间」，无法表达停留后的时序；② `target_arrival_time` 是用户指定的「希望到达」还是引擎推算的「预计到达」未定义，若为前者，则与 Rule-02 的「系统计算该节点预期抵达时间」冲突（两个来源不同的到达时间）；③ 无 `stop_type`，无法区分「POI」「酒店锚点」「口岸锚点」，而路线计算序列 `P0 → P1 → … → Photel` 需要它们混排；④ `transit_from_previous` 对首站 `P0` 的语义未定义（示例中首站带 `transit_from_previous.duration_seconds = 1800`，那么 Day 1 首站的上一段是从口岸起算还是从酒店起算）；⑤ 无 `locked` / `user_pinned` 标记，Rule-02 的 `[Move to Evening]` 与拖拽对用户手动固定顺序的点是否可移动未定义 —— 建议补全：增加 `arrival_time`（引擎推算）与 `user_preferred_arrival`（用户意愿）双字段并定义优先级、增加 `departure_time`、`stop_type`、`locked`，并明确 `transit_from_previous` 在首站的语义。`

`[严重度: 高] 行程级状态、版本与撤销能力在实体层完全缺失 —— 依据：`TripInstance` 顶层只有 `"trip_id"`、`"user_profile"`、`"anchor_arrival"`、`"anchor_hotel"`、`"days"` —— 影响：无法支撑任何形式的撤销/回滚/审计：无 `version`、无 `updated_at`、无 `status`（草稿/已确认/进行中）、无变更历史或操作日志、无 `last_confirmed_conflicts`（Rule-01 的 `Proceed anyway` 是一次性确认还是持续有效，需要落库）。同时 3.6 的离线缓存也需要 `version` 才能判断本地副本是否过期 —— 建议补全：增加 `version`、`status`、`updated_at`、`revision_history[]`（或服务端操作日志）与每条冲突确认记录 `{poi_id, day_index, rule_id, confirmed_at}`。`

---

## 三、需要产品方确认的问题清单

1. **时间基准**：`anchor_arrival.timestamp = 1789728000` 与 `days[0].date = "2026-10-12"` 相差 24 天，是示例笔误还是引擎允许两者不一致？若一致，以哪个为准？
2. **时区**：`timestamp` / `activity_start_time` / `target_arrival_time` 全部按哪个时区解释（Asia/Shanghai 本地时还是 UTC）？用户手机时区与目的地不一致时以哪个为准？是否需要同时存本地时与 UTC？
3. **每日起点**：Day 2..N 每天从酒店出发的具体时刻由谁决定——用户输入、按 Pacing 默认值（如 Relaxed 09:30 / Packed 08:00）、还是反向由第一个 POI 的营业时间倒推？是否会新增 `daily_start_time` 字段？
4. **离开锚点**：本期是否支持录入出境航班/高铁（Departure Anchor）？若不支持，最后一天如何给出「必须几点离开景点」的倒推提示？
5. **Arrival Anchor 跨零点**：`T_arrival` 在 22:30–23:59 之间时，`T_start = T_arrival + 90 min` 落入次日，Day 1 是保留为空、顺延到 Day 2，还是提示用户调整抵达时刻？
6. **`closure_days` 规范**：数组元素是整数（0–6）还是字符串？0 代表周日还是周一？如何表达「周一闭馆但法定节假日照常开放」以及春节/国庆的临时闭馆段？`[]` 是「不闭馆」还是「未知」？
7. **闭馆数据来源与覆盖率**：`closure_days` / `is_enclosed_attraction` 是人工录入还是外采？一期覆盖多少个 POI、覆盖哪些城市？未覆盖的 POI 是否有「数据待核实」标识？
8. **`standard_opening_hours` 表达力**：`"00:00 - 24:00"` 这一格式能否表达分时段（含午休）、按星期不同、季节性调整？是否改为结构化时段数组？`last_entry_time` 与闭馆时间的关系（是否 `last_entry < close`）如何校验？
9. **`last_entry_time` 为 `null` 时**，详情抽屉的 `Last Entry` 行是隐藏、显示「—」还是显示「以现场公告为准」？`Rule-01` 是否也需校验 `last_entry_time`（到达时间晚于截止入场时是否拦截）？
10. **`T_light` 定义**：`summer` / `winter` 各对应哪些日期区间？`T_light` 取亮灯区间的起点、日落时刻，还是固定常量？季节键缺失时 Rule-02 是静默跳过还是提示数据缺失？
11. **Rule-02 是否要覆盖「到得太晚」**：若预计抵达时间晚于亮灯窗口结束，系统是否也提示改期？
12. **规则编号与顺序**：3.3 流程图（规则 1/2/3）与正文（Rule-01…04）如何对齐？四条规则是串行短路还是并行求值？多个软规则同时命中时，Toast / 气泡 / Banner / 卡片标签是否允许叠加显示？
13. **硬约束强度**：Rule-01 标注为「Hard Constraint」，但用户可 `Proceed anyway`。是否存在任何条件下必须拒绝加入（如行程已确认后）？「强阻断」是否应改称「强冲突（需二次确认）」？
14. **Rule-03 的判定量**：25 km 是直线距离还是路线距离/时长？「该城市为高密度主城区」以什么字段判定（`POIMaster` 目前无 `city` / `district`）？25 km 是否需按城市配置（一期仅上海）？
15. **Rule-04 的分类字典**：`sub_category` 的完整枚举是什么？示例中的 `#ClassicalGarden` / `#Temple` 与 `"category": "Modern Skyline"` / `"sub_category": "Riverwalk"` 是什么关系？`category` / `sub_category` 与 Interests 四项标签如何映射？
16. **Rule-04 文案插值**：阈值是 `≥ 3`，当同类达到 5 个时提示文案仍写「You have 3 similar…」还是动态显示实际数量？
17. **Pacing 上限**：`Packed ≥ 5` 是否应改为上界？超过上限时是拦截、软警告还是自动压缩 `planned_dwell_minutes`？
18. **Party Composition 系数**：1.3 作用在「步行段耗时」还是「整个移动区间耗时」？与 `walking_speed_factor` 如何叠加（相乘/取大/覆盖）？`walking_speed_factor` 的取值区间与默认值是什么？「优先推荐打车模式」具体指默认 Tab、排序还是隐藏公共交通？
19. **Interests 权重**：推荐 POI 的排序权重公式是什么？多个标签是否累加？`Interests` 全部未选时按什么排序？
20. **同一 POI 能否跨多天重复装载**？若可以，`Added-Other-Day` 的角标如何显示多个天（`D2/D5`？`D2+1`）？
21. **图钉状态全集**：请确认是否补充「已加入当前天但未选中」与「冲突警告态」两个状态，并给出完整的状态迁移触发事件清单。
22. **撤销与回滚**：拖拽排序、`[Move to Evening]` 一键调整、批量添加后，是否提供 Undo？撤销栈深度是多少？是否存在「行程确认」后不可撤销的边界？
23. **重算触发时机**：拖拽是落点即重算还是松手后防抖重算？NFR 的「≤ 1.2 s」是否包含首屏与冷启动？
24. **API 失败的三级降级**：除「点对点直线距离粗算」外，是否定义「保留上次成功结果 + 标记过期」「仅展示 POI 顺序不含交通」等级别？降级后 3.4 三组对比卡与 3.7 问路卡按钮是否仍展示（直线粗算下没有进/出站口节点）？
25. **坐标基准**：`coordinate` 是 GCJ-02（高德/腾讯）还是 BD-09（百度）？三源混用时如何统一？「步行段最后 300m」「Walk 350m East」等米级指引的精度承诺是多少？
26. **费用字段**：`cost_cny` 单值如何满足 3.4 的「预估费用区间」？是否需要 `cost_min_cny` / `cost_max_cny`？多币种展示口径与汇率时点？
27. **换乘 30% 上浮**：上浮作用在「换乘步行段耗时」还是「整段公交耗时」？上浮后的值是否参与 Rule-02/Rule-03 的时间轴推演？重复重算时是否会叠加？
28. **微观数据来源**：`Enter via: Entrance 2 (2号口)` / `Exit via: Exit 7 (7号口)` / `Target Direction` / `Estimated transfer time: 6-8 mins. Take indoor escalators.` 分别来自第三方 API 还是自建 `Curated Stations`？该库一期覆盖多少站点、字段有哪些、缺失时如何降级？
29. **下客点纠偏**：`suggested_drop_off_coordinate` 是必填还是选填？「针对大型景点」如何判定？它与「地图 API 的 `drop_off_locations`」谁优先？为空时是否拒绝提供打车方案？
30. **离线包范围**：离线缓存是否包含进出站口、换乘指引、`closure_days`、`drop_off_coordinate`？TTL 多长？用户在离线态修改行程后，恢复在线时以本地还是服务端为准？
31. **问路卡模板**：是否要按节点类型（进站口/换乘处/出站口/落客点）分别提供中英问句模板？`Show Target Direction` 的取值与缺失时的降级文案？
32. **问路卡实现**：`强制横屏` 与 `模态弹窗` 二选一还是按平台区分？是否需要防熄屏？
33. **实体字段规格**：是否会为 `POIMaster` 与 `TripInstance` 补充字段表（类型/必填/取值域/默认值/单位/数据来源）？当前两个实体只有 JSON 示例，与「研发就绪」的状态声明不一致。
34. **行程状态与版本**：是否需要 `status`（草稿/已确认/进行中）、`version`、`updated_at` 与冲突确认记录（`Proceed anyway` 的持久化）？
