"use strict";
/* Fixed display text and shipped POI metadata. Load before i18n.js.
 * No user-supplied names, single-character markers or interpolated templates. */
(() => {
  const rows = `
酒店|Hotel|ホテル|호텔
口岸|Arrival/departure hub|到着・出発拠点|도착/출발 거점
景点|Attraction|観光地|관광지
往返大交通|Round-trip intercity transport|往復の都市間交通|왕복 도시 간 교통
当地交通|Local transport|現地の移動|현지 교통
景点门票|Attraction tickets|観光地の入場料|관광지 입장권
购物及其他|Shopping and other expenses|買い物・その他の費用|쇼핑 및 기타 비용
机动费用|Contingency costs|予備費|예비비
每人往返大交通|Round-trip intercity transport per person|一人あたりの往復都市間交通|1인당 왕복 도시 간 교통
每人购物及其他|Shopping and other expenses per person|一人あたりの買い物・その他の費用|1인당 쇼핑 및 기타 비용
住宿（请确认）|Accommodation (please confirm)|宿泊先（要確認）|숙소 (확인 필요)
演示路线不能计入真实费用|Demo routes cannot be included in actual costs.|デモ経路は実際の費用に計上できません。|시연 경로는 실제 비용에 반영할 수 없습니다.
实际同行人数和打车车辆数待补充|Actual traveler and taxi vehicle counts are missing.|実際の同行人数とタクシーの台数が未入力です。|실제 동행 인원수와 택시 차량수가 미입력 상태입니다.
已选路线或人民币费用待补充|The selected route or its CNY cost is missing.|選択した経路または人民元の費用が未入力です。|선택한 경로 또는 위안화 비용이 미입력 상태입니다.
cost_inputs 必须是对象或 null|cost_inputs must be an object or null|cost_inputsはオブジェクトまたはnullである必要があります|cost_inputs는 객체 또는 null이어야 합니다
cost_inputs 含未知字段|cost_inputs contains unknown fields|cost_inputsに未知のフィールドがあります|cost_inputs에 알 수 없는 필드가 있습니다
cost_inputs 住宿/餐饮日期必须是 YYYY-MM-DD|cost_inputs accommodation/meal dates must use YYYY-MM-DD|cost_inputsの宿泊・食事の日付はYYYY-MM-DD形式である必要があります|cost_inputs의 숙박/식사 날짜는 YYYY-MM-DD 형식이어야 합니다
cost_inputs 住宿/餐饮日期非法|cost_inputs accommodation/meal date is invalid|cost_inputsの宿泊・食事の日付が無効です|cost_inputs의 숙박/식사 날짜가 유효하지 않습니다
cost_inputs.lodging_nights 最多 60 项|cost_inputs.lodging_nights allows at most 60 items|cost_inputs.lodging_nightsは最大60項目です|cost_inputs.lodging_nights는 최대 60개 항목까지 가능합니다
cost_inputs.lodging_nights 字段非法|cost_inputs.lodging_nights fields are invalid|cost_inputs.lodging_nightsのフィールドが無効です|cost_inputs.lodging_nights 필드가 유효하지 않습니다
cost_inputs.hotel_name 非法|cost_inputs.hotel_name is invalid|cost_inputs.hotel_nameが無効です|cost_inputs.hotel_name이 유효하지 않습니다
cost_inputs.itinerary_key 非法|cost_inputs.itinerary_key is invalid|cost_inputs.itinerary_keyが無効です|cost_inputs.itinerary_key가 유효하지 않습니다
行程已变更，请核对房晚、门票和餐饮后重新保存费用设置|The trip has changed. Check room nights, tickets and meals, then save the cost settings again.|旅行が変更されました。宿泊日、入場料、食費を確認してから費用設定を再保存してください。|여행이 변경되었습니다. 숙박일과 입장료, 식사 비용을 확인한 뒤 비용 설정을 다시 저장하세요.
内置|Built-in|内蔵|내장
未知|Unknown|不明|알 수 없음
日期未提供|Date not provided|日付未提供|날짜 미제공
Last Entry|Last Entry|最終入場|마지막 입장
Hours|Hours|時間|시간
Closed on Monday|Closed on Monday|月曜休館|월요일 휴관
Closed on Tuesday|Closed on Tuesday|火曜休館|화요일 휴관
Closed on Wednesday|Closed on Wednesday|水曜休館|수요일 휴관
Closed on Thursday|Closed on Thursday|木曜休館|목요일 휴관
Closed on Friday|Closed on Friday|金曜休館|금요일 휴관
Closed on Saturday|Closed on Saturday|土曜休館|토요일 휴관
Closed on Sunday|Closed on Sunday|日曜休館|일요일 휴관
 · 缓存已过期，请更新核对| · Cached rate has expired; refresh and verify| · キャッシュのレートは期限切れです。更新して確認してください| · 캐시 환율이 만료되었습니다. 갱신하고 확인하세요
 · 缓存参考汇率| · Cached reference exchange rate| · キャッシュ済みの参考為替レート| · 캐시된 참고 환율
费用评估 · 保存行程后可评估|Cost assessment · Save your trip to assess costs|費用評価 · 旅行を保存すると評価できます|비용 평가 · 여행을 저장하면 평가할 수 있습니다
费用评估 · 评估待加载|Cost assessment · Awaiting assessment data|費用評価 · 評価データの読み込み待ち|비용 평가 · 평가 데이터 불러오기 대기 중
夜景景点|Night-view attraction|夜景スポット|야경 명소
请先启动路线适配器|Start the route adapter first.|先に経路アダプターを起動してください。|경로 어댑터를 먼저 시작하세요.
（演示路线，非真实导航）| (demo route, not for actual navigation)|（デモ経路・実際のナビには使用不可）| (시연 경로, 실제 내비게이션용이 아님)
费用金额超出范围|Cost amount is out of range|費用の金額が範囲外です|비용 금액이 허용 범위를 벗어났습니다
腾讯路线报价|Tencent route quote|Tencentの経路料金見積もり|텐센트 경로 요금 견적
百度路线报价|Baidu route quote|Baiduの経路料金見積もり|바이두 경로 요금 견적
已核实路线参考价|Verified route reference price|確認済みの経路参考料金|확인된 경로 참고 요금
加入景点和酒店后自动计入参考费用。门票按成人基础参考价估算，儿童、学生等优惠请手填人均金额。门票留空沿用参考价，找不到价格时待补充；手填金额优先，填 0 表示免费或不发生。住宿、打车按实际人数分摊；门票按每次停靠计入，重复使用同一张票的停靠请填 0。调整建议不会自动改变行程。|Reference costs are added automatically after you add attractions and hotels. Tickets are estimated using the basic adult reference price; enter per-person amounts manually for child, student or other discounts. Leaving a ticket amount blank uses the reference price; if no price is available, it remains incomplete. Manual amounts take priority, and 0 means free or no cost incurred. Accommodation and taxi costs are divided by the actual number of travelers. Tickets are counted for each stop; enter 0 for stops that reuse the same ticket. Adjustment suggestions do not automatically change your itinerary.|観光地とホテルを追加すると参考費用が自動的に計上されます。入場料は大人の基本参考料金で見積もります。子供・学生などの割引は一人あたりの金額を手入力してください。空欄の場合は参考料金を使用し、料金が見つからない場合は未入力のままになります。手入力を優先し、0は無料または費用が発生しないことを表します。宿泊・タクシー代は実際の人数で分割します。入場料は訪問ごとに計上するため、同じ券を再利用する訪問は0を入力してください。調整提案で行程が自動変更されることはありません。|관광지와 호텔을 추가하면 참고 비용이 자동으로 반영됩니다. 입장료는 성인 기본 참고 요금으로 추정하며 어린이·학생 등의 할인은 1인당 금액을 직접 입력하세요. 입장료를 비워 두면 참고 요금을 사용하고, 가격을 찾을 수 없으면 미입력 상태로 남습니다. 직접 입력한 금액이 우선하며 0은 무료 또는 비용이 발생하지 않음을 뜻합니다. 숙박비와 택시비는 실제 인원수로 나눕니다. 입장료는 방문마다 반영되므로 같은 표를 재사용하는 방문에는 0을 입력하세요. 조정 제안은 일정을 자동으로 바꾸지 않습니다.
自动模式按行程前 N−1 晚计费，酒店继承、换酒店和改日期后自动更新；途中酒店停靠不会重复计算房费。跨零点抵达、提前入住或延住请取消自动模式，按实际付费夜晚填写。手动模式删除全部住宿行并保存表示没有住宿费用。|Automatic mode charges for the first N−1 nights of the trip and updates when hotels are carried over, changed or dates are edited. Hotel stops along the way do not duplicate room charges. For arrivals after midnight, early check-in or extended stays, turn off automatic mode and enter the actual paid nights. In manual mode, deleting all accommodation rows and saving means there are no accommodation costs.|自動モードは行程の最初のN−1泊を計上し、ホテルの引き継ぎ、変更、日程変更に応じて更新します。途中のホテル立ち寄りで宿泊料を重複計上しません。日付をまたぐ到着、早めのチェックイン、延泊は自動モードを解除し、実際に支払う宿泊日を入力してください。手動モードで宿泊行をすべて削除して保存すると、宿泊費なしとして扱います。|자동 모드는 일정의 첫 N−1박을 계산하며 호텔 승계, 호텔 변경, 날짜 수정 시 자동으로 갱신됩니다. 이동 중 호텔에 들러도 객실 요금이 중복 계산되지 않습니다. 자정 이후 도착, 조기 체크인, 연장 숙박은 자동 모드를 해제하고 실제로 지불하는 숙박일을 입력하세요. 수동 모드에서 모든 숙박 행을 삭제하고 저장하면 숙박비가 없는 것으로 처리됩니다.
汇率|Exchange rate|為替レート|환율
返回币种不匹配|Returned currency does not match|返された通貨が一致しません|반환된 통화가 일치하지 않습니다
参考汇率|Reference exchange rate|参考為替レート|참고 환율
可选择人民币，或手动填写有效汇率。|Choose CNY or enter a valid exchange rate manually.|人民元を選ぶか、有効な為替レートを手入力してください。|위안화를 선택하거나 유효한 환율을 직접 입력하세요.
保留手动汇率；可稍后更新参考汇率。|Manual exchange rate retained; you can refresh the reference rate later.|手入力の為替レートを保持しました。参考レートは後で更新できます。|직접 입력한 환율을 유지합니다. 참고 환율은 나중에 갱신할 수 있습니다.
请先填有效汇率，或清空预算后切换币种。|Enter a valid exchange rate first, or clear the budget before changing currency.|有効な為替レートを入力するか、予算を空欄にしてから通貨を変更してください。|유효한 환율을 먼저 입력하거나 예산을 지운 뒤 통화를 바꾸세요.
已保存的币种设置无效，已使用人民币；可重新选择币种和填写汇率。|Saved currency settings are invalid, so CNY is being used. You can select a currency again and enter an exchange rate.|保存済みの通貨設定が無効なため、人民元を使用しています。通貨を選び直し、為替レートを入力できます。|저장된 통화 설정이 유효하지 않아 위안화를 사용합니다. 통화를 다시 선택하고 환율을 입력할 수 있습니다.
存在闭馆 / 时间风险，请检查开放信息。|There is a closure or timing risk; check opening information.|休館または時間のリスクがあります。開放情報をご確認ください。|휴관 또는 시간상 위험이 있습니다. 운영 정보를 확인하세요.
路线服务未就绪，请检查模块配置。|Route service is not ready; check the module configuration.|経路サービスが準備できていません。モジュール設定をご確認ください。|경로 서비스가 준비되지 않았습니다. 모듈 설정을 확인하세요.
停靠点|Stops|立ち寄り地点|방문 지점
还没有已保存的行程：填写①后点「保存行程」。|No trips have been saved yet. Complete step ①, then select Save trip.|保存済みの旅行はまだありません。①を入力して「旅行を保存」を選んでください。|저장된 여행이 없습니다. ①을 작성한 뒤 ‘여행 저장’을 누르세요.
请输入有效的出发时刻|Enter a valid departure time.|有効な出発時刻を入力してください。|유효한 출발 시각을 입력하세요.
无效的每日地点|Invalid daily location|各日の地点が無効です|일별 장소가 유효하지 않습니다
每日地点已保存，实际起终点没有变化，现有交通保留。|Daily locations saved. The actual start and end points are unchanged, so existing transport is retained.|各日の地点を保存しました。実際の出発・到着地点に変更がないため、既存の移動情報を保持します。|일별 장소를 저장했습니다. 실제 출발점과 도착점이 바뀌지 않아 기존 교통 정보를 유지합니다.
有一条行程建议，请核对景点运营信息。|There is an itinerary suggestion; check the attraction's operating information.|行程の提案が1件あります。観光地の運営情報をご確認ください。|일정 제안이 1건 있습니다. 관광지 운영 정보를 확인하세요.
rules_engine 未就绪：无法校验闭馆与亮灯规则，这里不会给出结论。启动该模块后点「重新校验行程」。|rules_engine is not ready. Closure and lighting rules cannot be checked, so no conclusion is given here. Start the module, then select Recheck trip.|rules_engineが準備できていません。休館・点灯ルールを確認できないため、ここでは結論を出しません。モジュールを起動後、「行程を再確認」を選んでください。|rules_engine이 준비되지 않았습니다. 휴관 및 점등 규칙을 확인할 수 없어 여기서는 결론을 내리지 않습니다. 모듈을 시작한 뒤 ‘일정 다시 확인’을 누르세요.
尚未校验。请点击“重新校验行程”，核对闭馆信息。|Not checked yet. Select Recheck trip to verify closure information.|まだ確認していません。「行程を再確認」を選んで休館情報をご確認ください。|아직 확인하지 않았습니다. ‘일정 다시 확인’을 눌러 휴관 정보를 확인하세요.
已确认保留，仍存在闭馆风险|Confirmed to keep; closure risk remains|保持を確認済みですが、休館のリスクは残ります|유지하기로 확인했으나 휴관 위험은 남아 있습니다
已完成规则检查；未发现当前可判断的冲突。|Rule check completed; no conflicts identifiable with the available information were found.|ルール確認が完了しました。現在判断できる範囲では競合は見つかりませんでした。|규칙 확인을 완료했습니다. 현재 판단 가능한 범위에서는 충돌을 찾지 못했습니다.
收起建议|Collapse suggestions|提案を折りたたむ|제안 접기
部分规则缺少数据，尚不能完整校验；请先计算区间交通并核实景点时间。|Some rules lack data and cannot be fully checked yet. Calculate transport between stops and verify attraction times first.|一部のルールはデータ不足で完全に確認できません。先に区間の移動を計算し、観光地の時間を確認してください。|일부 규칙은 데이터가 부족해 아직 완전히 확인할 수 없습니다. 구간 교통을 먼저 계산하고 관광지 시간을 확인하세요.
交通区段不存在|Transport segment does not exist|移動区間が存在しません|교통 구간이 존재하지 않습니다
未加入|Not added|未追加|미추가
已加入当天|Added to this day|この日に追加済み|해당 날짜에 추가됨
已加入其他天|Added to another day|別の日に追加済み|다른 날짜에 추가됨
当前选中|Currently selected|選択中|현재 선택됨
有冲突|Has a conflict|競合あり|충돌 있음
住宿（每日起点/终点）|Accommodation (daily start/end point)|宿泊先（各日の出発・到着地点）|숙소 (일별 출발점/도착점)
高德官方 SDK|Official AMap SDK|高徳地図の公式SDK|가오더 공식 SDK
SDK 加载失败（可能是 CSP 或网络）|SDK failed to load (possibly due to CSP or the network)|SDKの読み込みに失敗しました（CSPまたはネットワークの可能性）|SDK 불러오기 실패 (CSP 또는 네트워크 문제일 수 있음)
脚本已加载但未挂载 window.L|Script loaded, but window.L is unavailable|スクリプトは読み込まれましたがwindow.Lがありません|스크립트는 불러왔지만 window.L이 없습니다
加载超时|Loading timed out|読み込みがタイムアウトしました|불러오기 시간 초과
加载失败（网络或 CSP 拦截）|Loading failed (network error or CSP blocked it)|読み込みに失敗しました（ネットワークまたはCSPによるブロック）|불러오기 실패 (네트워크 오류 또는 CSP 차단)
请检查高德 key、安全密钥与域名白名单。|Check the AMap key, security key and domain allowlist.|高徳地図のkey、セキュリティキー、ドメイン許可リストをご確認ください。|가오더 key, 보안 키, 도메인 허용 목록을 확인하세요.
点右上角「重试加载」可再试一次（多为 CDN 一次性抖动）。|Select Retry loading at the top right to try again (usually a temporary CDN issue).|右上の「読み込みを再試行」で再試行できます（多くは一時的なCDNの不調です）。|오른쪽 위 ‘불러오기 재시도’를 눌러 다시 시도할 수 있습니다 (대개 일시적인 CDN 문제입니다).
高德地图|AMap|高徳地図|가오더 지도
Leaflet 地图|Leaflet map|Leaflet地図|Leaflet 지도
图钉状态：默认（白） / 已加入当天（浅绿） / 已加入其他天（D 角标） / 当前选中（深绿） / 有冲突（红）。|Pin states: default (white) / added to this day (light green) / added to another day (D badge) / selected (dark green) / conflict (red).|ピンの状態：初期（白）／この日に追加済み（薄緑）／別の日に追加済み（Dバッジ）／選択中（濃緑）／競合あり（赤）。|핀 상태: 기본 (흰색) / 해당 날짜에 추가됨 (연녹색) / 다른 날짜에 추가됨 (D 표시) / 현재 선택됨 (진녹색) / 충돌 있음 (빨간색).
此交通方式暂不支持高德导航。|This transport mode does not currently support AMap navigation.|この移動手段は現在、高徳地図のナビに対応していません。|이 교통수단은 현재 가오더 내비게이션을 지원하지 않습니다.
起终点缺少有效坐标，请重新选择地点并计算交通。|The start or end point lacks valid coordinates. Select the locations again and recalculate transport.|出発・到着地点に有効な座標がありません。地点を選び直し、移動を再計算してください。|출발점 또는 도착점의 유효한 좌표가 없습니다. 장소를 다시 선택하고 교통을 계산하세요.
方案终点与当前景点不一致，请重新计算交通。|The route destination does not match the current attraction. Recalculate transport.|経路の到着地点が現在の観光地と一致しません。移動を再計算してください。|경로의 도착점이 현재 관광지와 일치하지 않습니다. 교통을 다시 계산하세요.
换乘|Transfer|乗り換え|환승
已选路线的线路形状预览，无底图与实时定位|Selected route shape preview, without a base map or live location|選択した経路の形状プレビュー（地図・リアルタイム位置情報なし）|선택한 경로 형태 미리보기, 기본 지도 및 실시간 위치 없음
当前为打车方案，导航入口打开驾车路线，不提供叫车服务。|This is a taxi plan. The navigation link opens driving directions and does not book a taxi.|現在はタクシーのプランです。ナビのリンクは車の経路を開くもので、配車サービスは提供しません。|현재는 택시 경로입니다. 내비게이션 링크는 운전 경로를 열며 택시 호출 서비스를 제공하지 않습니다.
暂未提供详细路段说明，请在高德查看。|Detailed segment instructions are not available yet. View them in AMap.|詳細な区間案内はまだありません。高徳地図でご確認ください。|상세 구간 안내가 아직 없습니다. 가오더에서 확인하세요.
行程正在修改或方案已变化，请等待保存完成后使用新的导航入口。|The trip is being edited or the route has changed. Wait for saving to finish, then use the new navigation link.|旅行を編集中か、経路が変更されています。保存完了後に新しいナビのリンクを使用してください。|여행을 수정 중이거나 경로가 바뀌었습니다. 저장이 끝난 뒤 새 내비게이션 링크를 사용하세요.
正在计算所选日期的推荐安排…|Calculating recommendations for the selected dates…|選択した日程のおすすめを計算中…|선택한 날짜의 추천 일정 계산 중…
行程已切换或设定已更改，推荐未保存；请按当前设定重新生成。|The trip or settings changed, so recommendations were not saved. Generate them again using the current settings.|旅行または設定が変更されたため、おすすめは保存されませんでした。現在の設定で再生成してください。|여행 또는 설정이 바뀌어 추천을 저장하지 않았습니다. 현재 설정으로 다시 생성하세요.
没有可新增的推荐安排，请查看原因并调整日期或偏好。|No new recommendations can be added. Check the reasons and adjust your dates or preferences.|追加できるおすすめの予定がありません。理由を確認し、日程や希望を調整してください。|추가할 수 있는 추천 일정이 없습니다. 이유를 확인하고 날짜나 취향을 조정하세요.
推荐已计算，正在保存完整行程…|Recommendations calculated. Saving the complete trip…|おすすめを計算しました。旅行全体を保存中…|추천 계산 완료. 전체 여행 저장 중…
推荐已保存到原行程；当前显示的行程和未保存设定已保留。|Recommendations saved to the original trip. The currently displayed trip and unsaved settings are retained.|元の旅行におすすめを保存しました。現在表示中の旅行と未保存の設定は保持しています。|원래 여행에 추천을 저장했습니다. 현재 표시된 여행과 저장하지 않은 설정은 유지됩니다.
推荐已保存到原行程，当前行程或设定已更改；可从历史列表查看推荐结果。|Recommendations saved to the original trip, but the current trip or settings have changed. View the results in the trip history list.|元の旅行におすすめを保存しましたが、現在の旅行または設定は変更されています。履歴一覧で結果を確認できます。|원래 여행에 추천을 저장했으나 현재 여행이나 설정이 바뀌었습니다. 여행 기록 목록에서 결과를 확인할 수 있습니다.
推荐行程已保存，可在每日行程中继续编辑。|Recommended trip saved. Continue editing it in the daily itinerary.|おすすめの旅行を保存しました。各日の行程で編集を続けられます。|추천 여행을 저장했습니다. 일별 일정에서 계속 수정할 수 있습니다.
推荐行程已保存。|Recommended trip saved.|おすすめの旅行を保存しました。|추천 여행을 저장했습니다.
未运行（无注册文件）|Not running (no registration file)|未起動（登録ファイルなし）|실행 중 아님 (등록 파일 없음)
已注册端口但服务无响应|Port registered, but the service is not responding|ポートは登録済みですがサービスが応答しません|포트가 등록되었으나 서비스가 응답하지 않습니다
就绪|Ready|準備完了|준비 완료
已启动但未就绪|Started, but not ready|起動済みですが準備未完了です|시작되었으나 아직 준비되지 않았습니다
路线服务未读取 API Key；使用高德时，请在设置 AMAP_WEB_KEY 的终端重新启动整个软件|Route service has not loaded an API key. To use AMap, restart the entire application from a terminal where AMAP_WEB_KEY is set.|経路サービスがAPIキーを読み込んでいません。高徳地図を使うには、AMAP_WEB_KEYを設定した端末からソフトウェア全体を再起動してください。|경로 서비스가 API 키를 읽지 못했습니다. 가오더를 사용하려면 AMAP_WEB_KEY를 설정한 터미널에서 전체 프로그램을 다시 시작하세요.
行程数据的读写（必需）|Read and write trip data (required)|旅行データの読み書き（必須）|여행 데이터 읽기 및 쓰기 (필수)
时序推演与 Rule-01~04（未接入时编排页只显示数据、不做冲突提示）|Timeline simulation and Rule-01~04 (without this service, the planning page only displays data and provides no conflict warnings)|時系列の推計とRule-01~04（未接続の場合、編成ページはデータ表示のみで競合を通知しません）|시간 흐름 추정 및 Rule-01~04 (연결되지 않으면 일정 페이지에 데이터만 표시하며 충돌 경고를 제공하지 않음)
门到门路线与三模态对比卡（未接入时无法显示区间耗时）|Door-to-door routes and comparison cards for three transport modes (segment travel times are unavailable without this service)|ドア・ツー・ドアの経路と3種類の移動手段の比較カード（未接続の場合、区間の所要時間を表示できません）|출발지부터 목적지까지의 경로 및 세 가지 교통수단 비교 카드 (연결되지 않으면 구간 소요 시간을 표시할 수 없음)
离线包与问路卡（未接入时无此功能）|Offline packs and direction cards (unavailable without this service)|オフラインパックと道案内カード（未接続の場合、利用できません）|오프라인 패키지 및 길 안내 카드 (연결되지 않으면 사용할 수 없음)
按兴趣与日期生成推荐游玩安排（未接入时仍可手动规划）|Generate sightseeing recommendations by interests and dates (manual planning remains available without this service)|興味と日程に応じたおすすめの観光予定を生成（未接続でも手動で計画できます）|관심사와 날짜에 따른 추천 관광 일정 생성 (연결되지 않아도 직접 계획할 수 있음)
滨江步道|Riverside walkway|川沿いの遊歩道|강변 산책로
北京东路圆明园路口|Intersection of Beijing East Rd and Yuanmingyuan Rd|北京東路と円明園路の交差点|베이징둥루와 위안밍위안루 교차로
避开中山东一路全线禁停违章区|Avoid the no-stopping zone along all of Zhongshan East 1st Rd|中山東一路全線の駐停車禁止区域を避けます|중산둥이루 전 구간의 정차 금지 구역을 피합니다
夏季|Summer|夏季|여름
冬季|Winter|冬季|겨울
夜景|Night views|夜景|야경
免费|Free|無料|무료
步行街|Pedestrian street|歩行者専用街|보행 거리
博物馆|Museum|博物館|박물관
人民大道 201 号正门落客区|Main-gate drop-off area at 201 Renmin Ave|人民大道201号の正門降車エリア|런민다다오 201번지 정문 하차 구역
周一闭馆（法定节假日除外）|Closed on Mondays except public holidays|月曜休館（法定祝日を除く）|월요일 휴관 (법정 공휴일 제외)
国庆假期照常开放|Open as usual during the National Day holiday|国慶節休暇中も通常どおり開館|국경절 연휴에도 정상 운영
购票预约|Ticket booking|チケット予約|입장권 예약
周一闭馆（国定假日除外）|Closed on Mondays except national holidays|月曜休館（国定祝日を除く）|월요일 휴관 (국가 공휴일 제외)
人民广场馆特展|Special exhibitions at the People's Square site|人民広場館の特別展|인민광장관 특별전
日场15:00停止入场，夜场以公告为准|Daytime admission ends at 15:00; evening admission follows announcements|昼間の入場は15:00まで。夜間は告知に従います|주간 입장은 15:00에 종료하며 야간 입장은 공지를 따릅니다
古典园林|Classical garden|古典庭園|고전 정원
福佑路豫园商城落客点|Drop-off at Yuyuan Bazaar on Fuyou Rd|福佑路の豫園商城降車地点|푸유루 위위안 상가 하차 지점
园林|Garden|庭園|정원
闭馆信息待复核|Closure information needs rechecking|休館情報は再確認が必要|휴관 정보 재확인 필요
水乡古镇|Historic water town|水郷古鎮|수향 고진
课植园路景区停车场落客区|Drop-off area at the scenic-site parking lot on Kezhiyuan Rd|課植園路の観光地駐車場降車エリア|커즈위안루 관광지 주차장 하차 구역
古镇内禁止机动车通行，需在景区入口落客|Motor vehicles are prohibited in the old town; drop off at the scenic-site entrance|古鎮内は自動車通行禁止のため、観光地入口で降車してください|고진 안에는 자동차가 들어갈 수 없으므로 관광지 입구에서 하차해야 합니다
远郊|Outer suburbs|遠郊外|외곽 교외
水乡|Water town|水郷|수향
观景台|Observation deck|展望台|전망대
陆家嘴环路丰和路口落客区|Drop-off at Lujiazui Ring Rd and Fenghe Rd|陸家嘴環路と豊和路の交差点降車エリア|루자쭈이환루와 펑허루 교차로 하차 구역
地标|Landmark|ランドマーク|랜드마크
开放时间待复核|Opening hours need rechecking|開放時間は再確認が必要|운영 시간 재확인 필요
银城中路花园石桥路口落客区|Drop-off at Yincheng Middle Rd and Huayuanshiqiao Rd|銀城中路と花園石橋路の交差点降車エリア|인청중루와 화위안스차오루 교차로 하차 구역
摩天楼|Skyscraper|超高層ビル|마천루
世纪大道陆家嘴环路口落客区|Drop-off at Century Ave and Lujiazui Ring Rd|世紀大道と陸家嘴環路の交差点降車エリア|스지다다오와 루자쭈이환루 교차로 하차 구역
东泰路世纪大道口落客区|Drop-off at Dongtai Rd and Century Ave|東泰路と世紀大道の交差点降車エリア|둥타이루와 스지다다오 교차로 하차 구역
寺庙|Temple|寺院|사찰
龙华路龙华西路口落客区|Drop-off at Longhua Rd and Longhua West Rd|龍華路と龍華西路の交差点降車エリア|룽화루와 룽화시루 교차로 하차 구역
古寺|Historic temple|古寺|고찰
香火|Incense offerings|参拝・お香|향 공양
愚园路华山路落客区|Drop-off at Yuyuan Rd and Huashan Rd|愚園路と華山路の降車エリア|위위안루와 화산루 하차 구역
市中心|City center|市中心部|도심
历史街区|Historic neighborhood|歴史街区|역사 지구
淮海中路武康路口落客区|Drop-off at Huaihai Middle Rd and Wukang Rd|淮海中路と武康路の交差点降車エリア|화이하이중루와 우캉루 교차로 하차 구역
梧桐区|Plane-tree-lined area|プラタナスの並木エリア|플라타너스 가로수 구역
美食街|Food street|飲食街|먹거리 거리
瑞金二路泰康路口落客区|Drop-off at Ruijin 2nd Rd and Taikang Rd|瑞金二路と泰康路の交差点降車エリア|루이진얼루와 타이캉루 교차로 하차 구역
弄堂|Traditional lanes|路地|전통 골목
小店|Small shops|小さな店|작은 상점
老城厢|Old town|旧市街|구시가지
马当路兴业路口落客区|Drop-off at Madang Rd and Xingye Rd|馬当路と興業路の交差点降車エリア|마당루와 싱예루 교차로 하차 구역
石库门|Shikumen architecture|石庫門建築|스쿠먼 건축
餐饮|Dining|飲食|식사
菜市场|Food market|食料品市場|식료품 시장
乌鲁木齐中路五原路口落客区|Drop-off at Urumqi Middle Rd and Wuyuan Rd|烏魯木斉中路と五原路の交差点降車エリア|우루무치중루와 우위안루 교차로 하차 구역
市井|Local everyday life|庶民の暮らし|서민의 일상
上午最佳|Best in the morning|午前がおすすめ|오전 방문 추천
公园|Park|公園|공원
锦绣路1号门落客区|Drop-off at Gate 1 on Jinxiu Rd|錦繍路の1号門降車エリア|진슈루 1번 게이트 하차 구역
亲子|Family-friendly|親子向け|가족 활동
收费|Paid admission|有料|유료
长宁路1号门落客区|Drop-off at Gate 1 on Changning Rd|長寧路の1号門降車エリア|창닝루 1번 게이트 하차 구역
地铁2号线|Metro Line 2|地下鉄2号線|지하철 2호선
植物园|Botanical garden|植物園|식물원
龙吴路997号正门落客区|Main-gate drop-off at 997 Longwu Rd|龍呉路997号の正門降車エリア|룽우루 997번지 정문 하차 구역
展览温室|Exhibition greenhouse|展示温室|전시 온실
军工路2000号西门落客区|West-gate drop-off at 2000 Jungong Rd|軍工路2000号の西門降車エリア|쥔궁루 2000번지 서문 하차 구역
森林公园|Forest park|森林公園|삼림공원
骑行|Cycling|サイクリング|자전거 타기
野餐|Picnic|ピクニック|소풍
南京西路1649号门口落客区|Entrance drop-off at 1649 Nanjing West Rd|南京西路1649号の入口降車エリア|난징시루 1649번지 입구 하차 구역
口袋公园|Pocket park|小規模公園|소공원
静安寺对面|Opposite Jing'an Temple|静安寺の向かい|정안사 맞은편
肇嘉浜路衡山路口落客区|Drop-off at Zhaojiabang Rd and Hengshan Rd|肇嘉浜路と衡山路の交差点降車エリア|자오자방루와 헝산루 교차로 하차 구역
商圈旁|Beside a shopping district|商業地区のそば|상업 지구 옆
城市绿地|Urban green space|都市緑地|도시 녹지
大渡河路189号门口落客区|Entrance drop-off at 189 Daduhe Rd|大渡河路189号の入口降車エリア|다두허루 189번지 입구 하차 구역
银锄湖|Yinchu Lake|銀鋤湖|인추호
虹桥路2381号正门落客区|Main-gate drop-off at 2381 Hongqiao Rd|虹橋路2381号の正門降車エリア|훙차오루 2381번지 정문 하차 구역
动物园|Zoo|動物園|동물원
四川北路2288号门口落客区|Entrance drop-off at 2288 Sichuan North Rd|四川北路2288号の入口降車エリア|쓰촨베이루 2288번지 입구 하차 구역
鲁迅墓|Lu Xun's tomb|魯迅の墓|루쉰 묘
樱花|Cherry blossoms|桜|벚꽃
博成路世博大道口落客区|Drop-off at Bocheng Rd and Shibo Ave|博成路と世博大道の交差点降車エリア|보청루와 스보다다오 교차로 하차 구역
滨江|Riverside|川沿い|강변
双子山|Twin Hills|双子山|쌍둥이 언덕
辰花公路3888号1号门落客区|Drop-off at Gate 1, 3888 Chenhua Highway|辰花公路3888号の1号門降車エリア|천화궁루 3888번지 1번 게이트 하차 구역
浦东新区|Pudong New Area|浦東新区|푸둥신구
市区|Urban area|市街地|시내
中华艺术与历史专题展，适合安排半天观展。|Themed exhibitions on Chinese art and history, suitable for a half-day visit.|中国の芸術と歴史をテーマとする展示で、半日の鑑賞に適しています。|중국 예술과 역사 주제 전시로, 반나절 관람에 적합합니다.
停留时长为规划参考|Visit duration is a planning reference|滞在時間は計画の参考です|체류 시간은 계획용 참고값입니다
开放与休馆安排待核实|Opening and closure arrangements need verification|開館・休館の予定は確認が必要です|개관 및 휴관 일정 확인 필요
坐标为地点标注点，实际入口待核实|Coordinates mark the location; the actual entrance needs verification|座標は地点の表示位置で、実際の入口は確認が必要です|좌표는 장소 표시 지점이며 실제 입구는 확인이 필요합니다
常规周二休馆，节假日安排须查公告|Normally closed on Tuesdays; check announcements for holiday arrangements|通常は火曜休館。祝日の予定は告知をご確認ください|통상 화요일 휴관이며 공휴일 일정은 공지를 확인하세요
散客常规参观免预约；互动体验空间另行预约|Individual visitors do not need reservations for regular visits; interactive experience spaces require separate reservations|個人の通常見学は予約不要。体験型スペースは別途予約が必要です|개별 방문객의 일반 관람은 예약이 필요 없으며 체험 공간은 별도 예약이 필요합니다
散客入口：B1层东门（近丁香路）|Individual visitor entrance: east gate on B1, near Dingxiang Rd|個人客入口：地下1階東門（丁香路近く）|개별 방문객 입구: 지하 1층 동문 (딩샹루 근처)
静安区|Jing'an District|静安区|징안구
自然科学与生命演化主题展馆，可与静安周边散步组合。|An exhibition venue on natural science and the evolution of life, which can be combined with a walk around Jing'an.|自然科学と生命の進化をテーマとする展示館で、静安周辺の散策と組み合わせられます。|자연 과학과 생명 진화 주제 전시관으로, 징안 주변 산책과 함께할 수 있습니다.
预约政策待核实|Reservation policy needs verification|予約方針は確認が必要です|예약 정책 확인 필요
官网休馆资料存在冲突，出发前请查最新公告|Closure information on the official website is inconsistent; check the latest announcements before departure|公式サイトの休館情報に食い違いがあります。出発前に最新の告知をご確認ください|공식 웹사이트의 휴관 정보가 서로 다릅니다. 출발 전에 최신 공지를 확인하세요
近郊|Nearby suburbs|近郊|근교
临港天文主题场馆，可与滴水湖安排同一天。|An astronomy venue in Lingang, which can be visited on the same day as Dishui Lake.|臨港の天文をテーマとする施設で、滴水湖と同じ日に訪れることができます。|린강의 천문 주제 시설로, 디수이호와 같은 날 방문할 수 있습니다.
黄浦区|Huangpu District|黄浦区|황푸구
了解世界博览会与上海世博记忆。|Learn about world expositions and memories of the Shanghai Expo.|世界博覧会と上海万博の記憶を知ることができます。|세계박람회와 상하이 엑스포의 기억을 알아봅니다.
常规周一休馆，节假日是否开放另行公告|Normally closed on Mondays; holiday opening is announced separately|通常は月曜休館。祝日の開館は別途告知します|통상 월요일 휴관이며 공휴일 개관 여부는 별도로 공지합니다
散客常规参观无需预约|Individual visitors do not need reservations for regular visits|個人の通常見学は予約不要です|개별 방문객의 일반 관람은 예약이 필요 없습니다
从城市规划与模型了解上海，可与人民广场周边组合。|Learn about Shanghai through urban planning and models, and combine the visit with the People's Square area.|都市計画や模型から上海を知り、人民広場周辺と組み合わせて訪れることができます。|도시 계획과 모형을 통해 상하이를 알아보고 인민광장 주변과 함께 방문할 수 있습니다.
临港航海主题展馆，适合与滴水湖组合。|A maritime exhibition venue in Lingang, suitable for combining with Dishui Lake.|臨港の航海をテーマとする展示館で、滴水湖と組み合わせるのに適しています。|린강의 항해 주제 전시관으로, 디수이호와 함께 방문하기에 좋습니다.
导航参考：中国航海博物馆北门，开放状态待核实|Navigation reference: north gate of China Maritime Museum; opening status needs verification|ナビの参考：中国航海博物館北門。開放状況は確認が必要です|내비게이션 참고: 중국 항해 박물관 북문, 개방 여부 확인 필요
历史文化街区|Historic and cultural neighborhood|歴史文化街区|역사문화 지구
松江区|Songjiang District|松江区|쑹장구
松江文化遗址与园区建筑；园内展馆的票务及开放安排需分别核对。|Cultural remains and park architecture in Songjiang; check ticketing and opening arrangements for each exhibition hall separately.|松江の文化遺跡と園内建築。各展示館のチケットと開館予定は個別にご確認ください。|쑹장의 문화 유적과 단지 건축물이며, 각 전시관의 입장권 및 운영 일정을 따로 확인해야 합니다.
陆家嘴滨江美术展馆，可与周边城市景观组合。|An art exhibition venue on the Lujiazui riverfront, which can be combined with surrounding city views.|陸家嘴の川沿いにある美術展示館で、周辺の都市景観と組み合わせられます。|루자쭈이 강변 미술 전시관으로, 주변 도시 경관과 함께 즐길 수 있습니다.
徐汇区|Xuhui District|徐匯区|쉬후이구
历史故居与纪念展示，可与衡复街区步行游览组合。|A historic residence and memorial displays, which can be combined with a walk through the Hengfu neighborhood.|歴史的な旧居と記念展示で、衡復街区の散策と組み合わせられます。|역사적인 옛집과 기념 전시로, 헝푸 지역 도보 탐방과 함께할 수 있습니다.
导航参考：宋庆龄故居西北门，开放状态待核实|Navigation reference: northwest gate of Soong Ching Ling's former residence; opening status needs verification|ナビの参考：宋慶齢旧居北西門。開放状況は確認が必要です|내비게이션 참고: 쑹칭링 옛집 북서문, 개방 여부 확인 필요
虹口区|Hongkou District|虹口区|훙커우구
邮政历史与近代建筑主题，可与苏州河沿岸组合。|Postal history and modern-era architecture, which can be combined with the Suzhou Creek waterfront.|郵便の歴史と近代建築をテーマとし、蘇州河沿岸と組み合わせられます。|우편 역사와 근대 건축을 주제로 하며 쑤저우허 강변과 함께 방문할 수 있습니다.
古镇老街|Old town and historic streets|古鎮の古い街並み|고진과 옛거리
闵行区|Minhang District|閔行区|민항구
老街、水乡与小吃；沿街店铺的营业时间各不相同。|Old streets, water-town scenery and snacks; individual shops along the streets have different opening hours.|古い街並み、水郷、軽食。通り沿いの店はそれぞれ営業時間が異なります。|옛거리와 수향, 간식을 즐길 수 있으며 거리의 상점마다 영업시간이 다릅니다.
嘉定区|Jiading District|嘉定区|자딩구
嘉定老街与地方小吃，适合慢节奏步行游览。|Old streets and local snacks in Jiading, suitable for leisurely exploration on foot.|嘉定の古い街並みと地元の軽食で、ゆっくり歩いて巡るのに適しています。|자딩의 옛거리와 지역 간식으로, 여유로운 도보 탐방에 좋습니다.
金山区|Jinshan District|金山区|진산구
金山水乡古镇；街区与收费展馆分别核对开放安排。|A historic water town in Jinshan; check opening arrangements for the streets and paid exhibition halls separately.|金山の水郷古鎮。街区と有料展示館の開放予定を個別にご確認ください。|진산의 수향 고진이며 거리와 유료 전시관의 운영 일정을 따로 확인하세요.
导航参考：枫泾古镇正门，开放状态待核实|Navigation reference: main entrance of Fengjing Ancient Town; opening status needs verification|ナビの参考：楓涇古鎮正門。開放状況は確認が必要です|내비게이션 참고: 펑징 고진 정문, 개방 여부 확인 필요
浦东历史街区与水乡巷道；不要与成都同名古镇混淆。|Historic streets and water-town lanes in Pudong; do not confuse it with the town of the same name in Chengdu.|浦東の歴史街区と水郷の路地。成都にある同名の古鎮と混同しないでください。|푸둥의 역사 거리와 수향 골목이며 청두에 있는 같은 이름의 고진과 혼동하지 마세요.
黄浦江北岸城市景观与滨江步行。|City views and riverside walks on the north bank of the Huangpu River.|黄浦江北岸の都市景観と川沿いの散策。|황푸강 북쪽 강변의 도시 경관과 강변 산책.
徐汇西岸滨江步行空间，可按体力缩短游览区间。|Riverside walking space on Xuhui's West Bund; shorten the route according to your stamina.|徐匯西岸の川沿いの歩行空間で、体力に応じて見学区間を短くできます。|쉬후이 웨스트번드 강변 산책 공간으로, 체력에 따라 탐방 구간을 줄일 수 있습니다.
青浦区|Qingpu District|青浦区|칭푸구
青浦户外游憩园区，适合给交通与园内步行留足时间。|An outdoor recreation park in Qingpu; allow enough time for travel and walking within the park.|青浦の屋外レクリエーション園区で、移動と園内散策に十分な時間を確保するとよいでしょう。|칭푸의 야외 휴양 단지로, 이동과 단지 내 도보 시간을 충분히 잡는 것이 좋습니다.
导航参考：东方绿舟1号门，开放状态待核实|Navigation reference: Gate 1 of Oriental Land; opening status needs verification|ナビの参考：東方緑舟1号門。開放状況は確認が必要です|내비게이션 참고: 둥팡뤼저우 1번 게이트, 개방 여부 확인 필요
松江山林步道；东佘山与西佘山入口和路线需分别确认。|Wooded hill trails in Songjiang; confirm entrances and routes for East Sheshan and West Sheshan separately.|松江の山林遊歩道。東佘山と西佘山の入口とルートは個別にご確認ください。|쑹장의 산림 산책로이며 동서산과 서서산의 입구 및 경로를 각각 확인해야 합니다.
导航参考：佘山国家森林公园东北门（西佘山一侧），开放状态待核实|Navigation reference: northeast gate of Sheshan National Forest Park, on the West Sheshan side; opening status needs verification|ナビの参考：佘山国家森林公園北東門（西佘山側）。開放状況は確認が必要です|내비게이션 참고: 서산 국가삼림공원 북동문 (서서산 쪽), 개방 여부 확인 필요
奉贤区|Fengxian District|奉賢区|펑셴구
奉贤森林园区，园内距离较长，建议安排较宽松的一天。|A forest park in Fengxian with long distances inside; plan a day with plenty of time.|奉賢の森林園区で、園内の距離が長いため、時間に余裕のある一日をお勧めします。|펑셴의 삼림 단지로, 단지 내 이동 거리가 길어 하루 일정을 여유롭게 잡는 것이 좋습니다.
导航参考：海湾国家森林公园1号门，开放状态待核实|Navigation reference: Gate 1 of Haiwan National Forest Park; opening status needs verification|ナビの参考：海湾国家森林公園1号門。開放状況は確認が必要です|내비게이션 참고: 하이완 국가삼림공원 1번 게이트, 개방 여부 확인 필요
湖滨步道|Lakeside walkway|湖畔の遊歩道|호숫가 산책로
临港湖滨散步，与天文馆、航海博物馆组合时需考虑区间交通。|Lakeside walks in Lingang; consider transport between sites when combining with the Astronomy Museum or Maritime Museum.|臨港の湖畔散策。天文館や航海博物館と組み合わせる際は、区間の移動を考慮してください。|린강 호숫가 산책이며 천문관이나 항해 박물관과 함께 방문할 때는 구간 교통을 고려해야 합니다.
`.trim().split('\n').map(line => line.split('|'));

  const priceRows = `
中文名上海宏安瑞士大酒店指向Swissotel Grand；英文名及南京东路坐标指向Radisson Collection Hyland。须先核对实体，禁止直接匹配价格。|The Chinese name 上海宏安瑞士大酒店 refers to Swissotel Grand, while the English name and Nanjing East Road coordinates refer to Radisson Collection Hyland. Verify the property first; do not match a price directly.|中国語名「上海宏安瑞士大酒店」はSwissotel Grandを指しますが、英語名と南京東路の座標はRadisson Collection Hylandを指しています。まず施設を確認し、料金を直接対応させないでください。|중국어 이름 ‘上海宏安瑞士大酒店’는 Swissotel Grand를 가리키지만 영어 이름과 난징둥루 좌표는 Radisson Collection Hyland를 가리킵니다. 호텔을 먼저 확인해야 하며 가격을 바로 연결해서는 안 됩니다.
Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。|Tripadvisor average price range for standard rooms. It is not tied to your stay dates, room type, breakfast, taxes, fees or cancellation/change policy. CNY amounts are converted at the exchange rate and rounded outward to the nearest 10 yuan. This is not a bookable quote.|Tripadvisorの標準客室の平均料金範囲です。利用者の宿泊日、客室タイプ、朝食、税・諸費用、取消・変更条件には対応していません。人民元は為替換算し、範囲が広がる方向で10元単位に丸めています。予約可能な見積もりではありません。|Tripadvisor의 표준 객실 평균 요금 범위입니다. 사용자의 숙박일, 객실 유형, 조식, 세금 및 수수료, 취소·변경 정책과 연결되어 있지 않습니다. 위안화 금액은 환율로 환산한 뒤 범위를 넓히는 방향으로 10위안 단위로 반올림합니다. 예약 가능한 견적이 아닙니다.
外滩公共步道；不含游船及收费体验|Bund public walkway; excludes cruises and paid experiences|外灘の公共遊歩道。遊覧船や有料体験は含みません|와이탄 공공 산책로이며 유람선과 유료 체험은 포함하지 않습니다
按产品口径基础标注免费，特展单独注明：人民广场馆美洲文明特展全价148、指定日135；2026-07-09至2027-11-14。当前特展期间人民广场馆不展出其他展览，实际入馆需购票（符合免票资格者除外）；指定日排除周末、国定假日及部分寒暑假日期；优惠票74、亲子200/320须匹配资格|The product lists the base cost as free and notes special exhibitions separately: the People's Square site's special exhibition on civilizations of the Americas costs 148 at full price or 135 on designated days, from 2026-07-09 to 2027-11-14. During this special exhibition, the People's Square site has no other exhibitions, so actual entry requires a ticket unless you qualify for free admission. Designated days exclude weekends, national holidays and some winter/summer school holiday dates. Discount tickets at 74 and family tickets at 200/320 require the corresponding eligibility.|製品上は基本費用を無料とし、特別展を別途記載しています。人民広場館のアメリカ大陸文明特別展は通常148、指定日135で、期間は2026-07-09～2027-11-14です。この特別展の期間中、人民広場館では他の展示はなく、実際の入館には購入したチケットが必要です（無料入館資格のある方を除く）。指定日には週末、国定祝日、一部の夏休み・冬休みの日付は含まれません。割引券74、親子券200/320には該当資格が必要です。|제품 기준으로 기본 비용은 무료로 표시하고 특별전은 별도로 안내합니다. 인민광장관 아메리카 문명 특별전은 정가 148, 지정일 135이며 기간은 2026-07-09부터 2027-11-14까지입니다. 현재 특별전 기간에는 인민광장관에서 다른 전시를 하지 않으므로 실제 입장에는 표를 구매해야 합니다 (무료 입장 자격자 제외). 지정일에는 주말, 국가 공휴일, 일부 여름·겨울 방학 날짜가 제외됩니다. 할인표 74와 가족표 200/320은 해당 자격이 필요합니다.
豫园日场成人：4—6月、9—11月40，其余月份30；不含豫园商城灯会等活动|Yu Garden daytime adult admission: 40 in April–June and September–November, 30 in other months. Excludes events such as the Yuyuan Bazaar lantern festival.|豫園の昼間の大人入場料：4～6月・9～11月は40、その他の月は30。豫園商城の灯会などの催しは含みません|위위안 주간 성인 입장료는 4~6월과 9~11월 40, 나머지 달은 30입니다. 위위안 상가 등축제 등의 행사는 포함하지 않습니다
古镇街区免大门票；课植园等场馆另收费，官方联票60，不能把联票当街区门票；街区免费依据第三方游览资料，官网可核实联票。|The old-town streets have no main entrance fee. Venues such as Kezhi Garden charge separately; the official combined ticket is 60 and must not be treated as a ticket for the streets. Free street access is based on third-party visitor information; the combined ticket can be verified on the official website.|古鎮の街区は入口の入場料が不要です。課植園などの施設は別料金で、公式共通券は60です。共通券を街区の入場券として扱わないでください。街区の無料情報は第三者の観光資料に基づき、共通券は公式サイトで確認できます。|고진 거리는 기본 입장료가 없습니다. 커즈위안 등의 시설은 별도 요금이 있으며 공식 통합권은 60입니다. 통합권을 거리 입장권으로 취급해서는 안 됩니다. 거리 무료 입장은 제3자 관광 자료에 근거하며 통합권은 공식 웹사이트에서 확인할 수 있습니다.
成人观光参考199；不同球体、楼层、联票组合名称不一致，须确认具体票种后使用|Adult sightseeing reference price: 199. Names vary between sphere, floor and combined-ticket packages; confirm the specific ticket type before using this price.|大人観光の参考料金は199です。球体・階・共通券の組み合わせで名称が異なるため、具体的な券種を確認してから使用してください|성인 전망 관람 참고 요금은 199입니다. 구체별·층별·통합권 조합의 이름이 서로 다르므로 구체적인 표 종류를 확인한 뒤 사용하세요
上海之巅118层成人参考180；125/126层等组合另收费，非全部楼层通票|Top of Shanghai, floor 118: adult reference price 180. Packages including floors 125/126 and other combinations cost separately; this is not an all-floors pass.|上海之巓118階の大人参考料金は180です。125・126階などの組み合わせは別料金で、全階共通券ではありません|상하이 정상 118층 성인 참고 요금은 180입니다. 125/126층 등의 조합은 별도 요금이며 전 층 통합권이 아닙니다
88层观光成人标准参考120；不含云中漫步等项目|Floor 88 sightseeing: standard adult reference price 120. Excludes activities such as the Skywalk.|88階観光の大人標準参考料金は120です。雲中漫歩などの体験は含みません|88층 전망 관람 성인 표준 참고 요금은 120입니다. 스카이워크 등의 활동은 포함하지 않습니다
未核实当前在售观光票价。2024年因功能调整被取消4A级资质；此公告不等于确认整个大厦停业，不使用旧观光票价|Current sightseeing ticket prices have not been verified. Its 4A attraction rating was revoked in 2024 due to changes in its functions. This announcement does not confirm that the entire building is closed; do not use old sightseeing ticket prices.|現在販売中の観光券の料金は未確認です。2024年に機能の調整により4A級の資格が取り消されました。この告知は建物全体の営業停止を確認するものではありません。過去の観光料金は使用しません|현재 판매 중인 전망 관람권 가격은 확인되지 않았습니다. 2024년 기능 조정으로 4A급 자격이 취소되었습니다. 이 공지는 건물 전체의 영업 중단을 확인하는 것은 아니며 과거 전망 관람 요금은 사용하지 않습니다
普通入寺参考免费，未找到本次可读取的官方常规票价公告；香火、素面、法会另计，需核实|Regular temple entry is provisionally free. No accessible official announcement of regular admission prices was found in this review. Incense offerings, vegetarian noodles and religious ceremonies cost separately and need verification.|通常の寺院入場は無料を参考としています。今回読み取れる公式の通常料金告知は見つかりませんでした。お香、精進麺、法会は別途扱いで、確認が必要です|일반 사찰 입장은 무료를 참고값으로 사용합니다. 이번에 읽을 수 있는 공식 일반 요금 공지를 찾지 못했습니다. 향 공양, 채식 국수, 법회는 별도이며 확인이 필요합니다
常规成人参考50；节庆、特别开放时段可能不同，不套用常规票价|Regular adult reference price: 50. Festivals and special opening periods may differ; do not apply the regular price to them.|通常の大人参考料金は50です。祭事や特別開放時間は異なる可能性があるため、通常料金を適用しないでください|일반 성인 참고 요금은 50입니다. 축제나 특별 개방 시간에는 다를 수 있으므로 일반 요금을 적용하지 마세요
公共街道步行免费；沿街建筑内部参观另核实|Walking along the public street is free; verify visits inside buildings along the street separately.|公共の通りの散策は無料です。沿道の建物内部の見学は別途ご確認ください|공공 거리 도보 이용은 무료이며 거리의 건물 내부 관람은 별도로 확인하세요
街区公共游览免费；购物、餐饮、展览另计|Public neighborhood access is free; shopping, dining and exhibitions cost separately.|街区の公共エリアの見学は無料です。買い物、飲食、展示は別途扱います|거리의 공공 구역 관람은 무료이며 쇼핑, 식사, 전시는 별도입니다
开放街区免费；商店、餐饮、石库门屋里厢等不包含|The open neighborhood is free; shops, dining, Shikumen Open House and similar venues are not included.|開放されている街区は無料です。店、飲食、石庫門屋里廂などは含みません|개방된 거리는 무료이며 상점, 식사, 스쿠먼 우리스샹 등은 포함하지 않습니다
找到政府市集介绍，未找到明确门票价格声明；市场购物不是门票，不凭类型自动填0|A government introduction to the market was found, but no explicit admission-price statement. Shopping at a market is not an admission ticket; do not automatically enter 0 based on the category.|政府の市場紹介は見つかりましたが、明確な入場料金の記載はありませんでした。市場での買い物は入場料ではありません。分類だけで自動的に0を入力しないでください|정부의 시장 소개는 찾았으나 명확한 입장료 안내는 찾지 못했습니다. 시장에서의 쇼핑은 입장료가 아니므로 장소 유형만으로 자동으로 0을 입력하지 않습니다
公园入园免费；园内另收费项目另计|Park admission is free; separately charged activities inside cost extra.|公園の入場は無料です。園内の別料金の項目は別途計上します|공원 입장은 무료이며 공원 내 별도 유료 항목은 따로 계산합니다
公园入园免费|Park admission is free.|公園の入場は無料です|공원 입장은 무료입니다
公共园区免费；专类园、温室等需另外核实票种与价格|Public garden areas are free; verify ticket types and prices for specialty gardens, greenhouses and similar facilities separately.|公共の園区は無料です。専門庭園や温室などの券種・料金は別途確認が必要です|공공 구역은 무료이며 전문 정원과 온실 등의 표 종류 및 요금은 별도로 확인해야 합니다
公园免费；游乐等另计|The park is free; amusement activities and similar items cost separately.|公園は無料です。遊戯施設などは別途計上します|공원은 무료이며 놀이시설 등은 별도입니다
公园公共区域参考免费；依据2025年免费开放报道，收费项目另计|The park's public areas are provisionally free, based on 2025 reports of free access; paid items cost separately.|公園の公共エリアは、2025年の無料開放報道に基づき無料を参考としています。有料項目は別途計上します|공원의 공공 구역은 2025년 무료 개방 보도를 근거로 무료를 참고값으로 사용하며 유료 항목은 별도입니다
公园入园参考免费；来源含游客反馈，需复核|Park admission is provisionally free; sources include visitor feedback and need rechecking.|公園の入場は無料を参考としています。情報源には訪問者の感想が含まれるため、再確認が必要です|공원 입장은 무료를 참고값으로 사용합니다. 출처에 방문객 후기가 포함되어 있어 재확인이 필요합니다
公园本体免费；不包含海洋世界等收费场馆|The park itself is free; paid venues such as the aquarium are not included.|公園そのものは無料です。海洋世界などの有料施設は含みません|공원 자체는 무료이며 해양세계 등의 유료 시설은 포함하지 않습니다
上海动物园成人标准40；非上海野生动物园，游乐另计；不沿用已结束的活动优惠|Shanghai Zoo standard adult admission: 40. This is not Shanghai Wild Animal Park; amusement activities cost separately. Do not carry over discounts from events that have ended.|上海動物園の大人標準料金は40です。上海野生動物園とは異なり、遊戯施設は別料金です。終了済みの催しの割引は適用しません|상하이 동물원 성인 표준 요금은 40입니다. 상하이 야생동물원이 아니며 놀이시설은 별도입니다. 종료된 행사의 할인은 적용하지 않습니다
公园免费开放，无需预约；内部收费项目另计|The park is open free of charge without reservations; paid items inside cost separately.|公園は無料開放で予約不要です。内部の有料項目は別途計上します|공원은 무료 개방이며 예약이 필요 없습니다. 내부 유료 항목은 별도입니다
公共园区免费；温室花园、申园等分区及活动不能默认免费，双子山预约与收费政策需按日期复核|The public park area is free. Do not assume areas and activities such as the greenhouse garden and Shenyuan are free. Recheck Twin Hills reservation and fee policies for the relevant date.|公共の園区は無料です。温室庭園、申園などのエリアや催しを無料と決めつけないでください。双子山の予約・料金方針は日付ごとに再確認が必要です|공공 구역은 무료입니다. 온실 정원과 선위안 등의 구역 및 행사를 무료로 가정해서는 안 됩니다. 쌍둥이 언덕의 예약 및 요금 정책은 해당 날짜를 기준으로 재확인해야 합니다
普通成人60；优惠资格和主题体验另计|Regular adult admission: 60. Discount eligibility and themed experiences are handled separately.|一般大人料金は60です。割引資格やテーマ体験は別途扱います|일반 성인 요금은 60입니다. 할인 자격과 주제별 체험은 별도로 처리합니다
东馆常设展免费；付费特展另计，不能套用人民广场馆收费或把所有特展都标免费|Permanent exhibitions at the East site are free; paid special exhibitions cost separately. Do not apply the People's Square site's charges or mark all special exhibitions as free.|東館の常設展は無料です。有料特別展は別途計上します。人民広場館の料金を適用したり、すべての特別展を無料としたりしないでください|동관 상설전은 무료이며 유료 특별전은 별도입니다. 인민광장관 요금을 적용하거나 모든 특별전을 무료로 표시해서는 안 됩니다
成人30；老人、学生及免费资格按官网，特定体验另计|Adult admission: 30. Senior, student and free-admission eligibility follow the official website; specific experiences cost separately.|大人料金は30です。高齢者・学生・無料入場の資格は公式サイトに従い、特定の体験は別途計上します|성인 요금은 30입니다. 노인·학생 및 무료 입장 자격은 공식 웹사이트를 따르며 특정 체험은 별도입니다
成人参观30；老人25、学生15；球幕电影等另计，免票资格按官方|Adult visit: 30; seniors 25, students 15. Dome films and similar activities cost separately; free-admission eligibility follows official rules.|大人見学は30、高齢者25、学生15です。ドーム映画などは別料金で、無料入場資格は公式の規定に従います|성인 관람 30, 노인 25, 학생 15입니다. 돔 영화 등은 별도이며 무료 입장 자격은 공식 규정을 따릅니다
常设展免费；特展、活动及体验不在本项内。来源较早，出行前复核|Permanent exhibitions are free. Special exhibitions, events and experiences are not included in this item. The source is older; recheck before traveling.|常設展は無料です。特別展、催し、体験はこの項目に含みません。情報源が古いため、出発前に再確認してください|상설전은 무료입니다. 특별전과 행사, 체험은 이 항목에 포함되지 않습니다. 출처가 오래되었으므로 여행 전에 재확인하세요
当前免费预约参观参考；旧政府介绍仍有30元，官网当前须知未明列价格，须复核，不能采用旧票价|Current reference: free visits by reservation. An older government introduction still lists 30 yuan, while current official visitor information does not explicitly state a price. Recheck; do not use the old ticket price.|現在は無料の予約見学を参考としています。古い政府の紹介には30元の記載が残っていますが、公式サイトの現在の案内には料金が明記されていません。再確認が必要で、過去の料金は使用できません|현재 참고값은 무료 예약 관람입니다. 오래된 정부 소개에는 아직 30위안이 표시되어 있으나 현재 공식 이용 안내에는 가격이 명시되어 있지 않습니다. 재확인이 필요하며 과거 입장료를 사용해서는 안 됩니다
普通成人馆票30；2021价格批复，潜艇参观等单独项目另核实|Regular adult museum ticket: 30, based on a 2021 price approval. Verify separate activities such as submarine visits independently.|一般大人の館内チケットは30で、2021年の料金認可に基づきます。潜水艦見学などの個別項目は別途ご確認ください|일반 성인 박물관 입장권은 30이며 2021년 가격 승인에 근거합니다. 잠수함 관람 등의 별도 항목은 따로 확인하세요
公共区域免费；广富林文化展示馆30（2026报道），其他场馆另计|Public areas are free; Guangfulin Cultural Exhibition Hall costs 30 according to 2026 reports. Other venues cost separately.|公共エリアは無料です。広富林文化展示館は30（2026年の報道）で、他の施設は別途計上します|공공 구역은 무료이며 광푸린 문화전시관은 30입니다 (2026년 보도). 다른 시설은 별도입니다
2025公布成人日场：工作日100、周末法定节假日150；17点后80/120；2026实际展览和票种需复核|Adult daytime prices announced in 2025: 100 on weekdays, 150 on weekends and public holidays; after 17:00, 80/120 respectively. Recheck actual exhibitions and ticket types for 2026.|2025年発表の大人昼間料金：平日100、週末・法定祝日150。17時以降はそれぞれ80/120です。2026年の実際の展示と券種は再確認が必要です|2025년에 발표된 성인 주간 요금은 평일 100, 주말과 법정 공휴일 150이며 17시 이후는 각각 80/120입니다. 2026년 실제 전시와 표 종류는 재확인해야 합니다
上海故居普通成人20；学生等优惠另计，不能混同北京宋庆龄故居|Regular adult admission to the Shanghai residence: 20. Student and other discounts are handled separately. Do not confuse it with Soong Ching Ling's former residence in Beijing.|上海の旧居の一般大人料金は20です。学生などの割引は別途扱います。北京の宋慶齢旧居と混同しないでください|상하이 옛집 일반 성인 요금은 20입니다. 학생 등의 할인은 별도로 처리하며 베이징 쑹칭링 옛집과 혼동해서는 안 됩니다
博物馆免费；开放日及预约需核实|The museum is free; opening days and reservations need verification.|博物館は無料です。開館日と予約は確認が必要です|박물관은 무료이며 개관일과 예약은 확인이 필요합니다
古镇街区免首道门票；内部展馆分别收费，不当作整镇收费|The old-town streets have no initial entrance fee. Exhibition halls inside charge separately; do not treat this as a charge for the entire town.|古鎮の街区は最初の入場料が不要です。内部の展示館は個別に有料で、町全体の料金として扱わないでください|고진 거리는 기본 입장료가 없습니다. 내부 전시관은 각각 요금을 받으며 이를 고진 전체의 요금으로 취급하지 않습니다
老街公共游览免费；古猗园、檀园等收费项目另核实|Public access to the old streets is free. Verify charges for Guyi Garden, Tan Garden and other paid sites separately.|古い街並みの公共エリア見学は無料です。古猗園、檀園などの有料項目は別途ご確認ください|옛거리의 공공 관람은 무료입니다. 구이위안과 탄위안 등의 유료 항목은 별도로 확인하세요
古镇街区免费；2025场馆联票参考50，不能套用已结束的半价活动|The old-town streets are free. The 2025 venue combined-ticket reference price is 50; do not apply half-price promotions that have ended.|古鎮の街区は無料です。2025年の施設共通券の参考料金は50で、終了済みの半額キャンペーンは適用できません|고진 거리는 무료입니다. 2025년 시설 통합권 참고 요금은 50이며 종료된 반값 행사를 적용해서는 안 됩니다
古镇公共游览免费；展馆及商业消费另计|Public old-town access is free; exhibition halls and commercial purchases cost separately.|古鎮の公共エリア見学は無料です。展示館や商業消費は別途計上します|고진의 공공 관람은 무료이며 전시관과 상업 소비는 별도입니다
滨江公共绿地参考免费；收费设施另计|Public riverside green space is provisionally free; paid facilities cost separately.|川沿いの公共緑地は無料を参考としています。有料施設は別途計上します|강변 공공 녹지는 무료를 참고값으로 사용하며 유료 시설은 별도입니다
滨江公共步道参考免费；沿线美术馆、活动另计|Public riverside walkways are provisionally free; art museums and events along the route cost separately.|川沿いの公共遊歩道は無料を参考としています。沿道の美術館や催しは別途計上します|강변 공공 산책로는 무료를 참고값으로 사용하며 경로상의 미술관과 행사는 별도입니다
成人普通入园50；住宿、水上活动、体验等另计|Regular adult park admission: 50. Accommodation, water activities, experiences and similar items cost separately.|大人の通常入場は50です。宿泊、水上活動、体験などは別途計上します|성인 일반 입장료는 50입니다. 숙박, 수상 활동, 체험 등은 별도입니다
东、西佘山公共登山游览免费；天马山、天文博物馆及挖笋体验等不能默认免费|Public hiking visits on East and West Sheshan are free. Do not assume Tianma Mountain, the astronomy museum, bamboo-shoot digging experiences and similar activities are free.|東佘山・西佘山の公共登山見学は無料です。天馬山、天文博物館、タケノコ掘り体験などを無料と決めつけないでください|동서산과 서서산의 공공 등산 관람은 무료입니다. 톈마산, 천문 박물관, 죽순 캐기 체험 등을 무료로 가정해서는 안 됩니다
普通成人原价参考80；依据2025报道，2026需复核，不沿用限时60优惠|Regular adult original-price reference: 80, based on 2025 reports. Recheck for 2026; do not carry over the limited-time discounted price of 60.|一般大人の通常料金の参考は80で、2025年の報道に基づきます。2026年は再確認が必要で、期間限定の60の割引は継続適用しません|일반 성인 정가 참고값은 80이며 2025년 보도에 근거합니다. 2026년에는 재확인이 필요하며 한시적 할인 요금 60을 계속 적용하지 않습니다
环湖公共游览参考免费；游船、水上活动及附近景区另计|Public sightseeing around the lake is provisionally free; cruises, water activities and nearby attractions cost separately.|湖周辺の公共エリア見学は無料を参考としています。遊覧船、水上活動、近くの観光地は別途計上します|호수 주변 공공 관람은 무료를 참고값으로 사용하며 유람선, 수상 활동, 인근 관광지는 별도입니다
`.trim().split('\n').map(line => line.split('|'));
  rows.push(...priceRows);
  const exhibitionConditions = priceRows.find(row => row[0].startsWith('按产品口径基础标注免费，特展单独注明：'));
  rows.push([
    `基础费用按免费计入；${exhibitionConditions[0]}`,
    `The base cost is counted as free; ${exhibitionConditions[1]}`,
    `基本費用は無料として計上します。${exhibitionConditions[2]}`,
    `기본 비용은 무료로 반영합니다. ${exhibitionConditions[3]}`,
  ]);

  rows.push(['自动','Automatic','自動','자동']);
  window.IRCommonLanguageCatalog = rows;
  const catalog = window.IRLanguageCatalog || (window.IRLanguageCatalog = []);
  const existingKeys = new Set(catalog.map(row => row[0]));
  for (const row of rows) {
    if (existingKeys.has(row[0])) continue;
    catalog.push(row);
    existingKeys.add(row[0]);
  }
})();

window.IRLanguageCatalog.push(
 ['核对地名英文','Review place names','地名の英語表記を確認','장소 영문 이름 확인'],
 ['拼音候选尚未确认。可填写正确英文，保存后会重新生成离线卡片。','Romanized names are unconfirmed. Enter the correct English name and save to regenerate the cards.','ローマ字表記は未確認です。正しい英語表記を入力して保存するとカードを再作成します。','로마자 표기는 미확인 상태입니다. 올바른 영문 이름을 입력하고 저장하면 카드를 다시 생성합니다.'],
 ['英文地名','English place name','英語の地名','장소 영문 이름'],
 ['确认英文并更新卡片','Confirm and update cards','確認してカードを更新','확인 및 카드 업데이트'],
 ['地名译文已更新，请重新生成并下载离线卡片。','Place names have changed. Regenerate and download the offline cards.','地名表記が更新されました。オフラインカードを再作成してダウンロードしてください。','장소 이름이 변경되었습니다. 오프라인 카드를 다시 생성하고 다운로드하세요.']
);
