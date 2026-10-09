"use strict";
/* 界面词典：中文原文 | English | 日本語 | 한국어。专有名称与用户输入不属于词典。 */
window.IRLanguageCatalog = `
行程工作台 · InboundRoute|Trip planner · InboundRoute|旅行プランナー · InboundRoute|여행 플래너 · InboundRoute
跳到行程设定|Skip to trip setup|旅行の設定へ移動|여행 설정으로 이동
行程工作台|Trip planner|旅行プランナー|여행 플래너
上海 · 从抵达到返程，安排好每一段|Shanghai · Plan every step, from arrival to departure|上海 · 到着から出発までの旅を計画|상하이 · 도착부터 출국까지 계획하세요
工作区导航|Workspace navigation|ワークスペースのナビゲーション|작업 공간 탐색
请先选择住宿|Choose accommodation first.|先に宿泊先を選んでください。|먼저 숙소를 선택하세요.
示意地图（未接入真实底图）|Sketch map (base map unavailable)|概略地図（地図未接続）|개략 지도 (기본 지도 없음)
未配置底图，当前使用示意地图。|Base map not configured. Showing a sketch map.|地図未設定のため概略図を表示します。|기본 지도가 설정되지 않아 개략도를 표시합니다.
以下功能暂不可用：|These features are currently unavailable: |現在利用できない機能：|현재 사용할 수 없는 기능: 
无法读取已保存行程：|Unable to load saved trips: |保存した旅行を読み込めません：|저장된 여행을 불러올 수 없습니다: 
无法连接 |Unable to connect to |接続できません：|연결할 수 없습니다: 
（trip_engine 未就绪时属预期降级）| (start the trip service to restore saved trips)|（旅行サービス起動後に復元できます）| (여행 서비스를 시작하면 복원할 수 있습니다)
由于目标计算机积极拒绝，无法连接。|Connection refused by the local service.|ローカルサービスが接続を拒否しました。|로컬 서비스가 연결을 거부했습니다.
只看市中心|City center only|中心部のみ|도심만 보기
重试加载|Retry loading|読み込みを再試行|불러오기 재시도
加载中…|Loading…|読み込み中…|불러오는 중…
正在重新加载底图…|Reloading base map…|地図を再読み込み中…|기본 지도 다시 불러오는 중…
保存会更新当前行程并保留已排景点；重置恢复已保存设定。要另建行程，请在历史下拉选择“新建行程”。|Saving updates this trip and keeps planned attractions. Reset restores saved settings. Choose New trip in the saved-trip list to create another trip.|保存すると既存の観光地を保持して更新します。リセットで保存済み設定に戻ります。別の旅行は一覧の「新しい旅行」から作成します。|저장하면 관광지를 유지하며 현재 여행을 업데이트합니다. 초기화는 저장된 설정을 복원합니다. 다른 여행을 만들려면 목록에서 '새 여행'을 선택하세요.
填写后保存即可新建行程。|Complete the form and save to create a trip.|入力して保存すると旅行を作成できます。|입력 후 저장하면 새 여행이 생성됩니다.
请先加入景点或设置不同起终点，再计算交通。|Add attractions or different start / end points before calculating transport.|観光地や異なる出発・到着地点を設定してから移動を計算してください。|관광지 또는 다른 출발 / 도착 지점을 설정한 후 교통을 계산하세요.
点击“计算全部区间交通”，或展开某一天单独计算；交通方案在当天详情中查看。|Calculate all transport, or expand a day to calculate it separately. View routes in each day's details.|すべての移動を計算するか、各日を開いて計算します。経路は各日の詳細で確認できます。|전체 교통을 계산하거나 날짜를 펼쳐 개별 계산하세요. 경로는 해당 날짜 상세 정보에서 확인할 수 있습니다.
部分方式不可用，请查看当天问题提示。|Some modes are unavailable; check the day's messages.|一部の移動手段が利用できません。当日の案内を確認してください。|일부 교통수단을 사용할 수 없습니다. 해당 날짜 안내를 확인하세요.
offline_kit 未就绪：无法生成离线包；启动该模块后重新生成。|Offline service unavailable. Start it before generating a pack.|オフラインサービスが利用できません。起動後に作成してください。|오프라인 서비스가 준비되지 않았습니다. 시작 후 패키지를 생성하세요.
离线包已载入。行程编辑后请重新生成；有效期 24 小时。|Offline pack loaded. Regenerate after editing; valid for 24 hours.|オフライン版を読み込みました。編集後は再作成してください。有効期限24時間。|오프라인 패키지를 불러왔습니다. 수정 후 다시 생성하세요. 유효 기간은 24시간입니다.
生成前请完成闭馆确认及交通计算。可下载 HTML，在关闭本地服务后打开问路卡。|Confirm closure conflicts and calculate transport first. Download the HTML to use direction cards after closing the local service.|休館の確認と移動計算を済ませてください。HTMLを保存するとサービス停止後も道案内を開けます。|휴관 확인과 교통 계산을 먼저 완료하세요. HTML을 다운로드하면 서비스 종료 후에도 길 안내를 열 수 있습니다.
计算完成，包含演示路线，请勿用于真实导航。|Calculated with demo routes. Do not use for actual navigation.|デモ経路を含みます。実際の案内には使えません。|시연 경로가 포함됩니다. 실제 길 안내에 사용하지 마세요.
计算完成，可选择其他交通方式；请核实实时交通。|Calculated. You may choose another mode; verify live transport.|計算済みです。他の移動手段も選べます。最新の交通を確認してください。|계산 완료. 다른 교통수단을 선택할 수 있으며 실시간 교통을 확인하세요.
包含演示路线，请勿用于真实导航。|Includes demo routes. Do not use for actual navigation.|デモ経路を含みます。実際の案内には使えません。|시연 경로 포함. 실제 길 안내에 사용하지 마세요.
请核实实时交通。|Check live transport.|最新の交通を確認してください。|실시간 교통을 확인하세요.
部分交通方式不可用；请选择可用方案补齐时间轴。|Some modes are unavailable. Select an available route to complete the timeline.|一部の移動手段が利用できません。利用可能な経路で時間を補ってください。|일부 교통수단을 사용할 수 없습니다. 가능한 경로를 선택하여 타임라인을 완성하세요.
在“挑选景点”中将景点加入这一天。|Add attractions to this day from Explore attractions.|「観光スポットを探す」でこの日に追加できます。|'관광지 둘러보기'에서 이 날짜에 관광지를 추가하세요.
当天区间交通|Daily transport|当日の移動|당일 구간 교통
已固定|Locked|固定済み|고정됨
换酒店时选择新的终止点，后续日期默认从那里出发；选择“自动”可恢复默认。修改后请重新计算受影响日期的交通。|When changing hotels, select a new end point. Following days start there by default. Choose Automatic to restore defaults and recalculate affected transport.|ホテルを変える場合は到着地点を変更します。翌日以降はそこから出発します。「自動」で初期設定に戻せます。移動を再計算してください。|호텔을 바꾸면 새 도착 지점을 선택하세요. 이후 날짜는 해당 지점에서 출발합니다. '자동'으로 기본값을 복원할 수 있으며 교통을 다시 계산하세요.
自动 · |Automatic · |自動 · |자동 · 
请重启本地服务以加载费用评估。|Restart the local service to load cost estimates.|費用の読み込みにはローカルサービスを再起動してください。|비용 예상을 불러오려면 로컬 서비스를 다시 시작하세요.
价格为估算，请核实实际报价。|Prices are estimates; verify actual quotes.|価格は概算です。実際の料金を確認してください。|가격은 예상치입니다. 실제 요금을 확인하세요.
行程已改变，请核对住宿晚数、门票和交通费用后重新保存。|Trip changed. Verify nights, tickets and transport costs, then save again.|旅行が変更されました。泊数・入場料・交通費を確認して保存してください。|여행이 변경되었습니다. 숙박 일수, 입장권 및 교통비를 확인하고 다시 저장하세요.
费用修改尚未保存。行程如有变化，请核对上述最新评估和费用后保存。|Cost changes are unsaved. Check the latest estimate before saving.|費用の変更は未保存です。最新の費用を確認して保存してください。|비용 변경이 저장되지 않았습니다. 최신 예상을 확인하고 저장하세요.
用户估算|User estimate|入力した概算|사용자 예상
自动参考价|Reference price|参考価格|참고 가격
备用金比例|Contingency percentage|予備費率|예비비 비율
同地点无需交通|No transport needed at the same location|同じ地点のため移動不要|같은 장소로 교통 불필요
手工路线报价|Manual route quote|手動の移動料金|수동 경로 요금
高德路线报价|Amap route quote|高徳の移動料金|Amap 경로 요금
交通费用|Transport costs|交通費|교통비
门票费用|Ticket costs|入場料|입장료
住宿费用|Accommodation costs|宿泊費|숙박비
餐饮费用|Meal costs|食費|식비
每间每晚参考 |Reference per room / night: |1室1泊の参考価格：|객실당 1박 참고 요금: 
；自动模式保留区间，手动模式请填实际房价。|; automatic mode keeps the range; enter actual prices in manual mode.|。自動では価格帯を保持、手動では実際の料金を入力。|; 자동 모드는 가격 범위를 유지하며 수동 모드는 실제 요금을 입력하세요.
留空自动计入 |Leave blank to use |空欄で自動使用：|빈칸이면 자동 적용: 
查询于 |Checked on |確認日：|조회일: 
行程版本 |Trip version |旅行バージョン |여행 버전 
生成于 |Generated on |作成日：|생성일: 
行程设定|Trip setup|旅行の設定|여행 설정
行程概览|Trip overview|旅行の概要|여행 개요
挑选景点|Explore attractions|観光スポットを探す|관광지 둘러보기
行程提醒|Trip reminders|旅行の注意事項|여행 알림
离线问路|Offline directions|オフライン道案内|오프라인 길 안내
旅程规划|PLAN YOUR VISIT|旅の計画|여행 계획
把每一天，安排得刚刚好。|Make every day your own.|毎日を、自分らしい旅に。|매일을 나만의 여행으로.
上海 · 日期 / 景点 / 交通|Shanghai · Dates / Attractions / Transport|上海 · 日程 / 観光 / 交通|상하이 · 날짜 / 관광지 / 교통
填写日期、住宿与出行偏好|Set dates, accommodation and travel preferences|日程・宿泊先・旅行の希望を設定|날짜, 숙소 및 여행 취향을 설정하세요
先确定日期、住宿和出行节奏，再挑选喜欢的景点。保存后会自动计算每日可用时间与建议景点数量；超过建议数量时仍可继续添加。|Set your dates, accommodation and pace, then choose attractions. Saving calculates daily available time and suggested stops; you can add more if you wish.|日程・宿泊先・ペースを決めてから観光地を選びます。保存すると毎日の利用可能時間と推奨スポット数が計算されます。推奨数を超えて追加することもできます。|날짜, 숙소, 여행 속도를 정한 후 관광지를 선택하세요. 저장하면 하루 가용 시간과 권장 관광지 수가 계산되며, 더 추가할 수도 있습니다.
已保存行程|Saved trips|保存した旅行|저장된 여행
选择已保存行程|Choose a saved trip|保存した旅行を選択|저장된 여행 선택
刷新列表|Refresh list|一覧を更新|목록 새로고침
复制当前行程|Duplicate trip|旅行を複製|여행 복제
删除当前行程|Delete trip|旅行を削除|여행 삭제
刷新或重开页面会自动恢复上次编辑的行程。|Your last trip is restored when you reload or reopen this page.|ページを再読み込みすると前回の旅行が復元されます。|페이지를 다시 열면 마지막으로 편집한 여행이 복원됩니다.
目的地城市|Destination city|目的地|목적지 도시
上海（一期）|Shanghai|上海|상하이
行程天数（1~15）|Trip length (1–15 days)|旅行日数（1～15日）|여행 기간 (1~15일)
出行构成|Travel party|同行者|동행 유형
独自出行|Solo|一人旅|혼자 여행
双人|Two people|二人|2인
带小孩的家庭|Family with children|子ども連れ|아이 동반 가족
长者同行|With older travelers|シニア同伴|고령자 동반
轻松（建议 ≤2 个点位/天）|Relaxed (up to 2 stops/day)|ゆったり（1日2か所以内）|여유롭게 (하루 2곳 이하)
均衡（建议 3~4 个）|Balanced (3–4 stops/day)|標準（1日3～4か所）|보통 (하루 3~4곳)
紧凑（建议 5~6 个）|Packed (5–6 stops/day)|充実（1日5～6か所）|알차게 (하루 5~6곳)
节奏|Travel pace|旅行のペース|여행 속도
每人预算（CNY，可选）|Budget per person (CNY, optional)|一人あたりの予算（CNY、任意）|1인당 예산 (CNY, 선택)
例如 3000|e.g. 3000|例：3000|예: 3000
每人整趟行程预算，留空表示未设置；外币按确认汇率换算保存。|Total trip budget per person. Leave blank to skip; foreign currency is saved using the confirmed exchange rate.|旅行全体の一人あたり予算です。空欄で省略できます。外貨は確認した為替レートで換算して保存します。|전체 여행의 1인당 예산입니다. 빈칸으로 두면 설정하지 않으며, 외화는 확인한 환율로 환산하여 저장됩니다.
币种与参考汇率|Currency and exchange rate|通貨と参考為替レート|통화 및 참고 환율
预算及显示币种|Budget and display currency|予算・表示通貨|예산 및 표시 통화
人民币 CNY|Chinese yuan CNY|人民元 CNY|중국 위안 CNY
美元 USD|US dollar USD|米ドル USD|미국 달러 USD
欧元 EUR|Euro EUR|ユーロ EUR|유로 EUR
英镑 GBP|Pound sterling GBP|英ポンド GBP|영국 파운드 GBP
日元 JPY|Japanese yen JPY|日本円 JPY|일본 엔 JPY
港币 HKD|Hong Kong dollar HKD|香港ドル HKD|홍콩 달러 HKD
澳元 AUD|Australian dollar AUD|豪ドル AUD|호주 달러 AUD
加元 CAD|Canadian dollar CAD|カナダドル CAD|캐나다 달러 CAD
新加坡元 SGD|Singapore dollar SGD|シンガポールドル SGD|싱가포르 달러 SGD
1 单位所选外币 = 人民币|1 unit of selected currency = CNY|選択通貨の1単位 = 人民元|선택 통화 1단위 = 위안
更新参考汇率|Refresh exchange rate|為替レートを更新|환율 새로고침
人民币为保存与计算基准。|Amounts are saved and calculated in CNY.|保存と計算には人民元を使います。|금액은 위안으로 저장 및 계산됩니다.
兴趣（可多选，影响推荐排序）|Interests (select any; used to rank suggestions)|興味（複数選択可・おすすめ順に反映）|관심사 (복수 선택 가능, 추천 순서에 반영)
历史人文|History & culture|歴史・文化|역사와 문화
现代天际线|Modern skyline|現代の街並み|현대 스카이라인
市井生活|Local life|地元の暮らし|현지 생활
自然生态|Nature|自然|자연
抵达日期|Arrival date|到着日|도착 날짜
抵达时刻（北京时间）|Arrival time (China time, UTC+8)|到着時刻（中国時間 UTC+8）|도착 시간 (중국 시간 UTC+8)
抵达口岸|Arrival airport / station|到着空港・駅|도착 공항 / 역
中文 / 英文 / 拼音，如 pudong|Chinese / English / pinyin, e.g. pudong|中国語・英語・ピンイン（例：pudong）|중국어 / 영어 / 병음 (예: pudong)
搜索已预订住宿|Find your booked accommodation|予約済みの宿泊先を検索|예약한 숙소 검색
中文 / 英文 / 拼音，如 peace|Chinese / English / pinyin, e.g. peace|中国語・英語・ピンイン（例：peace）|중국어 / 영어 / 병음 (예: peace)
选择住宿搜索结果|Choose accommodation search result|宿泊先の検索結果を選択|숙소 검색 결과 선택
选择已有预订的酒店或民宿；这里只安排行程。|Choose a hotel or homestay you have already booked. This planner arranges your itinerary.|予約済みのホテルや宿を選びます。ここでは旅程を計画します。|이미 예약한 호텔이나 숙소를 선택하세요. 여기에서는 일정을 계획합니다.
请搜索并确认住宿。|Find and confirm your accommodation.|宿泊先を検索して確認してください。|숙소를 검색하고 확인하세요.
离境 / 返程安排（可选）|Departure / return details (optional)|出発・帰路の予定（任意）|출국 / 귀국 일정 (선택)
填写离境口岸与时刻（用于推演最后一天「酒店 → 口岸」这一段；不填也能建行程）|Add departure airport / station and time to plan your final transfer from the hotel (optional).|出発空港・駅と時刻を入力すると、最終日のホテルからの移動を計画できます（任意）。|출발 공항 / 역과 시간을 입력하면 마지막 날 호텔에서의 이동을 계획할 수 있습니다 (선택).
离境口岸|Departure airport / station|出発空港・駅|출발 공항 / 역
离境日期|Departure date|出発日|출발 날짜
离境时刻（北京时间）|Departure time (China time, UTC+8)|出発時刻（中国時間 UTC+8）|출발 시간 (중국 시간 UTC+8)
国际航班 / 国际列车（提前预留 180 分钟）|International flight / train (allow 180 minutes)|国際線・国際列車（180分前に到着）|국제선 / 국제 열차 (180분 여유)
推荐安排哪些天|Choose days for recommendations|おすすめを作成する日|추천 일정을 만들 날짜
生成推荐行程|Generate itinerary|おすすめ旅行を作成|추천 일정 생성
保存行程|Save trip|旅行を保存|여행 저장
重置|Reset|リセット|초기화
每日行程|Daily itinerary|毎日の旅程|일별 일정
先看整趟安排，再展开某一天，调整景点与区间交通。|Review your trip, then expand a day to adjust attractions and transport.|旅行全体を確認し、各日を開いて観光地と交通手段を調整します。|전체 여행을 확인한 후 날짜를 펼쳐 관광지와 교통을 조정하세요.
费用评估|Cost estimate|費用の目安|비용 예상
计算全部区间交通|Calculate all transport|すべての移動を計算|전체 구간 교통 계산
在地图或推荐列表中查看景点，了解开放、预约与亮灯信息，再加入行程。未核验的信息会单独提示；底图不可用时显示示意地图。|Explore attractions on the map or in the list, check opening hours, reservations and lighting, then add them to your trip. Unverified information is flagged; a sketch map appears if the base map is unavailable.|地図や一覧で観光地を確認し、営業時間・予約・ライトアップの情報を見て追加します。未確認情報は明示し、地図が利用できない場合は概略図を表示します。|지도나 목록에서 관광지를 살펴보고 운영 시간, 예약, 조명 정보를 확인한 후 여행에 추가하세요. 미확인 정보는 표시되며 지도를 사용할 수 없으면 개략도가 표시됩니다.
搜索名称 / 拼音（如 waitan）|Search name / pinyin (e.g. waitan)|名称・ピンインで検索（例：waitan）|이름 / 병음 검색 (예: waitan)
搜索 POI|Search attractions|観光地を検索|관광지 검색
景点类别|Attraction category|観光地の種類|관광지 유형
全部类别|All categories|すべての種類|전체 유형
示意地图|Sketch map|概略地図|개략 지도
POI 空间分布|Attraction locations|観光地の位置|관광지 위치
显示全部|Show all|すべて表示|전체 보기
景点自动滚动，使用滚轮或滑动后改为手动浏览。|Attractions scroll automatically. Scroll or swipe to browse manually.|観光地は自動でスクロールします。スクロールやスワイプで手動に切り替わります。|관광지는 자동으로 스크롤됩니다. 스크롤하거나 스와이프하면 수동으로 전환됩니다.
恢复自动滚动|Resume auto-scroll|自動スクロールを再開|자동 스크롤 재개
暂停自动滚动|Pause auto-scroll|自動スクロールを停止|자동 스크롤 일시 중지
景点推荐，滚轮或左右滑动查看|Attractions; scroll or swipe to explore|おすすめ観光地・スクロールやスワイプで表示|추천 관광지, 스크롤 또는 좌우 스와이프로 탐색
看看哪天需要调整、哪些景点需要核实开放信息。每条提醒会说明原因；调整入口可以带你回到当天安排。|Check which days need changes and which attractions need opening information verified. Each reminder explains why and links to that day's plan.|調整が必要な日や、営業情報の確認が必要な観光地を確認します。理由と該当日の予定へのリンクを表示します。|조정이 필요한 날짜와 운영 정보를 확인해야 할 관광지를 살펴보세요. 각 알림은 이유와 해당 날짜 일정 링크를 제공합니다.
重新检查|Check again|再確認|다시 확인
生成后可下载自包含 HTML：关闭本地服务也能打开。存在待确认冲突或缺交通时间时不会把离线包标为完整。|Download a standalone HTML file that works even when the local service is closed. Unresolved conflicts or missing transport times keep the package incomplete.|ローカルサービス停止後も開けるHTMLファイルを保存できます。未解決の競合や移動時間の不足がある場合、完全なパッケージにはなりません。|로컬 서비스가 꺼져도 열 수 있는 HTML 파일을 다운로드하세요. 미해결 충돌이나 교통 시간 누락이 있으면 완성된 패키지로 표시되지 않습니다.
生成离线包|Generate offline pack|オフライン版を作成|오프라인 패키지 생성
下载问路卡 HTML|Download directions HTML|道案内HTMLを保存|길 안내 HTML 다운로드
读取浏览器缓存|Load browser cache|ブラウザーの保存版を読み込む|브라우저 캐시 불러오기
↑ 返回顶部|↑ Back to top|↑ ページ上部へ|↑ 맨 위로
返回顶部|Back to top|ページ上部へ|맨 위로
关闭详情|Close details|詳細を閉じる|상세 정보 닫기
加入哪一天|Add to which day|追加する日|추가할 날짜
加入行程|Add to trip|旅行に追加|여행에 추가
设置 / Settings|Settings|設定 / Settings|설정 / Settings
设置|Settings|設定|설정
界面语言|Interface language|表示言語|화면 언어
关闭设置|Close settings|設定を閉じる|설정 닫기
完成|Done|完了|완료
语言更改立即生效，并在此浏览器中保存。|Changes apply immediately and are saved in this browser.|変更はすぐに反映され、このブラウザーに保存されます。|변경 사항은 즉시 적용되며 이 브라우저에 저장됩니다.
首版翻译界面与常用提示；景点简介、地图与部分原始资料可能保留原文。中文地名与问路卡会保留，方便向当地人问路。|This version translates the interface and common messages. Attraction descriptions, maps and some source information may remain in their original language. Chinese place names and direction cards are kept for asking locals.|画面とよく使うメッセージを翻訳しています。観光地の紹介・地図・一部の原資料は原文のままです。現地で道を尋ねられるよう、中国語の地名と道案内カードを残します。|화면과 자주 쓰는 안내를 번역합니다. 관광지 소개, 지도 및 일부 원본 자료는 원문으로 표시될 수 있습니다. 현지인에게 길을 물을 수 있도록 중국어 지명과 길 안내 카드는 유지됩니다.
详情|Details|詳細|상세 정보
查看详情|View details|詳細を見る|상세 보기
收起详情|Hide details|詳細を閉じる|상세 접기
暂无景点照片|No attraction photo available|観光地の写真はありません|관광지 사진 없음
暂无照片|No photo|写真なし|사진 없음
没有匹配的 POI|No matching attractions|該当する観光地はありません|일치하는 관광지 없음
简介待补充|Description not available|紹介文は未登録|소개 정보 없음
游览时长待核实|Visit duration unverified|見学時間は未確認|관람 소요 시간 미확인
未选择兴趣，当前按热度排序；在①里勾选兴趣会改变这里的顺序。|Sorted by popularity. Select interests in Trip setup to personalize the order.|人気順で表示中です。旅行の設定で興味を選ぶと表示順が変わります。|인기순으로 표시됩니다. 여행 설정에서 관심사를 선택하면 순서가 변경됩니다.
只填充所选空白日，已有安排与锁定点都会保留。可勾选抵达日和返程日。|Only selected empty days are filled. Existing plans and locked stops are kept. You may select arrival and departure days.|選択した空の日だけを埋めます。既存の予定と固定スポットは保持します。到着日・出発日も選べます。|선택한 빈 날짜만 채웁니다. 기존 일정과 고정된 장소는 유지됩니다. 도착일과 출발일도 선택할 수 있습니다.
请勾选想安排的日期；1～2 天行程默认不勾选抵达日和返程日。|Select days to plan. Arrival and departure days are not selected by default for 1–2 day trips.|計画する日を選んでください。1～2日の旅行では到着日と出発日は初期選択されません。|일정을 만들 날짜를 선택하세요. 1~2일 여행은 도착일과 출발일이 기본 선택되지 않습니다.
正在生成推荐…|Generating itinerary…|おすすめを作成中…|추천 생성 중…
请选择住宿|Choose accommodation|宿泊先を選択|숙소 선택
没有匹配的口岸/酒店，请换关键词|No matching airport / station / hotel. Try another search.|該当する空港・駅・ホテルがありません。検索語を変えてください。|일치하는 공항 / 역 / 호텔이 없습니다. 다른 검색어를 입력하세요.
清单未载入：trip_engine 未就绪，创建行程前需先启动该模块|List unavailable: start trip_engine before creating a trip.|一覧が利用できません。旅行作成前にtrip_engineを起動してください。|목록을 불러올 수 없습니다. 여행 생성 전에 trip_engine을 시작하세요.
近似坐标|Approximate coordinates|概算座標|대략적인 좌표
人工整理坐标|Curated coordinates|整理済み座標|정리된 좌표
请先选择住宿（可用中文 / 英文 / 拼音搜索）|Choose accommodation first (search in Chinese, English or pinyin).|先に宿泊先を選んでください（中国語・英語・ピンインで検索）。|먼저 숙소를 선택하세요 (중국어 / 영어 / 병음 검색).
还没有安排景点|No attractions planned yet|観光地はまだ未設定|아직 관광지가 없습니다
抵达与入住|Arrival & check-in|到着・チェックイン|도착 및 체크인
当天出发时刻|Daily departure time|当日の出発時刻|당일 출발 시간
当天时间轴|Daily timeline|当日のタイムライン|당일 타임라인
调整景点顺序或交通方式后，时间轴会重新校验。|The timeline is rechecked after changing attraction order or transport.|観光地の順序や移動手段を変えるとタイムラインを再確認します。|관광지 순서나 교통수단을 변경하면 타임라인을 다시 확인합니다.
这一天只安排抵达与入住，游览从次日开始。|This day is for arrival and check-in. Sightseeing starts the next day.|この日は到着とチェックインのみです。観光は翌日からです。|이날은 도착과 체크인만 합니다. 관광은 다음 날부터 시작합니다.
每一天可设不同时间；修改后自动保存并重新校验，请重算当天交通。|Set a different start time for each day. Changes are saved and checked; recalculate that day's transport.|各日の出発時刻を設定できます。変更は保存・再確認されます。その日の移動を再計算してください。|날짜별로 다른 출발 시간을 설정할 수 있습니다. 변경은 저장 및 확인되며, 해당 날짜 교통을 다시 계산하세요.
正在处理上一项修改，请稍后再试。|Saving the previous change. Please wait.|前の変更を保存中です。少しお待ちください。|이전 변경을 저장 중입니다. 잠시 기다려 주세요.
请输入有效的出发时刻。|Enter a valid departure time.|有効な出発時刻を入力してください。|유효한 출발 시간을 입력하세요.
去程交通已选|Outbound transport selected|往路の移動を選択済み|가는 교통편 선택됨
返程待计算|Return transport pending|帰路は未計算|귀환 교통 계산 대기
返程已计算|Return transport calculated|帰路を計算済み|귀환 교통 계산됨
时间轴已生成|Timeline ready|タイムライン作成済み|타임라인 생성됨
时间轴待补齐|Timeline incomplete|タイムラインは未完成|타임라인 미완성
含演示路线|Includes demo routes|デモ経路を含む|시연 경로 포함
已检查行程提醒|Reminders checked|注意事項を確認済み|여행 알림 확인됨
行程提醒暂不可用|Reminders unavailable|注意事項を利用できません|여행 알림 사용 불가
行程检查未完成|Trip check incomplete|旅行の確認は未完了|여행 확인 미완료
行程待检查|Trip check pending|旅行は未確認|여행 확인 대기
部分检查资料待补充|Some check data is missing|一部の確認資料が不足|일부 확인 자료 누락
计算当天交通|Calculate daily transport|当日の移動を計算|당일 교통 계산
计算这一天的交通|Calculate this day's transport|この日の移動を計算|이 날짜의 교통 계산
还没有交通方案。点击上方按钮计算这一天。|No transport plan yet. Use the button above to calculate this day.|移動プランは未作成です。上のボタンでこの日を計算してください。|교통 계획이 없습니다. 위 버튼으로 이 날짜의 교통을 계산하세요.
加入景点或设置不同起终点后可以计算交通。|Add attractions or set different start and end points to calculate transport.|観光地を追加するか異なる出発・到着地点を設定すると移動を計算できます。|관광지를 추가하거나 다른 출발 및 도착 지점을 설정하면 교통을 계산할 수 있습니다.
已恢复保存的去程方案；当天终点区间请重新计算。|Saved outbound routes restored; recalculate the final transfer.|保存した往路を復元しました。最終地点への移動は再計算してください。|저장된 가는 경로가 복원되었습니다. 마지막 구간을 다시 계산하세요.
公共交通|Public transport|公共交通|대중교통
打车|Taxi|タクシー|택시
步行|Walk|徒歩|도보
暂无耗时|Duration unavailable|所要時間なし|소요 시간 없음
未选择可用方案|No available option selected|利用可能な案は未選択|이용 가능한 경로 미선택
演示路线 · 非真实导航|Demo route · Not for navigation|デモ経路 · 実際の案内には使えません|시연 경로 · 실제 길 안내용 아님
路线不可用，请检查服务配置或稍后重试|Route unavailable. Check service settings or try again later.|経路を利用できません。設定を確認するか後でお試しください。|경로를 사용할 수 없습니다. 설정을 확인하거나 나중에 다시 시도하세요.
换乘步行较长，时间轴已计入额外步行时间。|This transfer includes a long walk, already included in the timeline.|乗り換えの徒歩距離が長いため、追加の歩行時間を計算済みです。|환승 시 도보 이동이 길며, 추가 도보 시간이 타임라인에 반영되었습니다.
该方式暂不可用，已保留原方案|This mode is unavailable. Your previous route is kept.|この移動手段は利用できません。元の案を保持しました。|이 교통수단은 사용할 수 없습니다. 기존 경로가 유지됩니다.
移除|Remove|削除|제거
上移|Move up|上へ|위로
下移|Move down|下へ|아래로
锁定|Lock|固定|고정
解锁|Unlock|固定解除|고정 해제
移到晚上|Move to evening|夜に移動|저녁으로 이동
仍然保留|Keep anyway|そのまま残す|그래도 유지
移除此景点|Remove attraction|観光地を削除|관광지 제거
需要处理|Action needed|対応が必要|조치 필요
安排建议|Suggestions|予定の提案|일정 제안
出发前核实|Verify before visiting|出発前に確認|출발 전 확인
这些安排可能无法按计划完成。|These plans may not work as scheduled.|予定どおりに進められない可能性があります。|이 일정은 계획대로 진행되지 않을 수 있습니다.
可以按自己的旅行偏好调整。|Adjust to suit your travel preferences.|旅行の好みに合わせて調整できます。|여행 취향에 맞게 조정하세요.
资料尚未确认，不代表景点一定闭馆。|Unverified information does not mean the attraction is closed.|情報が未確認でも、必ず休館とは限りません。|미확인 정보가 관광지 휴관을 의미하지는 않습니다.
查看原始备注|View original notes|原文の備考を表示|원본 메모 보기
查看当天安排|View day's plan|当日の予定を見る|당일 일정 보기
调整当天安排|Edit day's plan|当日の予定を調整|당일 일정 수정
检查还缺哪些信息|Missing check information|確認に不足している情報|확인에 필요한 누락 정보
已完成检查，未发现需要处理的闭馆冲突|Checked: no unresolved closure conflicts found.|確認済み：未解決の休館競合はありません。|확인 완료: 처리할 휴관 충돌이 없습니다.
还不能完整判断行程是否合适|More information is needed to check this trip.|旅行の判断にはさらに情報が必要です。|여행을 완전히 확인하려면 정보가 더 필요합니다.
修改景点或出发时间后会自动再检查。|Changes to attractions or departure times trigger a new check.|観光地や出発時刻を変えると自動で再確認します。|관광지나 출발 시간을 변경하면 자동으로 다시 확인합니다.
本次检查未完成，请稍后重新检查。|The check did not finish. Please try again later.|確認が完了しませんでした。後で再確認してください。|확인이 완료되지 않았습니다. 나중에 다시 확인하세요.
还没有检查结果。点击“重新检查”，查看安排是否需要调整。|No results yet. Select Check again to review your plan.|結果はまだありません。「再確認」で予定を確認してください。|아직 결과가 없습니다. '다시 확인'으로 일정을 검토하세요.
提醒服务暂未连接，尚不能检查景点开放与夜景时间。服务恢复后点击“重新检查”。|Reminder service unavailable. Opening hours and night-view times cannot be checked yet. Select Check again when the service returns.|注意事項サービス未接続のため、営業時間と夜景の時刻を確認できません。復旧後に「再確認」を選んでください。|알림 서비스가 연결되지 않아 운영 시간과 야경 시간을 확인할 수 없습니다. 복구 후 '다시 확인'을 선택하세요.
开放与闭馆信息尚未核实，暂时无法判断当天能否入内。出发前请核对景点官网或官方公告。|Opening and closure information is unverified. Check the attraction's official website or announcements before visiting.|営業・休館情報は未確認です。出発前に公式サイトやお知らせを確認してください。|운영 및 휴관 정보가 미확인입니다. 방문 전에 공식 웹사이트나 공지를 확인하세요.
请选择保留或移除。|Choose to keep or remove this stop.|残すか削除するかを選んでください。|유지 또는 제거를 선택하세요.
你已选择保留，闭馆风险仍然存在。|You chose to keep this stop; the closure risk remains.|残すことを選びましたが、休館のリスクは残ります。|유지를 선택했으나 휴관 위험은 남아 있습니다.
闭馆，按当前安排可能无法入内。|Closed; entry may not be possible as planned.|休館のため、予定どおりに入場できない可能性があります。|휴관으로 계획대로 입장하지 못할 수 있습니다.
查看并处理时间冲突|Review time conflicts|時間の競合を確認|시간 충돌 확인
离线行程与问路卡|Offline trip & direction cards|オフライン旅行・道案内カード|오프라인 여행 및 길 안내 카드
离线问路卡|Offline direction cards|オフライン道案内カード|오프라인 길 안내 카드
有效期 24 小时。请核实实时交通与开放情况。|Valid for 24 hours. Check live transport and opening hours.|有効期限は24時間です。最新の交通と営業時間を確認してください。|24시간 동안 유효합니다. 실시간 교통과 운영 정보를 확인하세요.
到达时间未确定|Arrival time unconfirmed|到着時刻は未確定|도착 시간 미정
演示路线，不能用于真实导航。|Demo route. Do not use for actual navigation.|デモ経路です。実際の案内には使えません。|시연 경로입니다. 실제 길 안내에 사용하지 마세요.
请重新生成或读取当前版本离线包|Generate or load an offline pack for the current trip version.|現在の旅行バージョンのオフライン版を作成・読み込んでください。|현재 여행 버전의 오프라인 패키지를 생성하거나 불러오세요.
当前浏览器没有此行程的离线包|No offline pack for this trip in this browser.|このブラウザーに旅行のオフライン版はありません。|이 브라우저에 이 여행의 오프라인 패키지가 없습니다.
请先计算各天交通路线，再生成离线包|Calculate daily transport before generating the offline pack.|各日の移動を計算してからオフライン版を作成してください。|일별 교통을 계산한 후 오프라인 패키지를 생성하세요.
请先处理闭馆冲突：选择仍然保留或移除景点|Resolve closure conflicts first: keep or remove the affected attractions.|先に休館の競合を解決し、観光地を残すか削除してください。|먼저 휴관 충돌을 해결하세요. 해당 관광지를 유지하거나 제거하세요.
离线包已过期或行程有修改，请重新生成；下方显示的是旧快照。|Offline pack expired or trip changed. Generate a new pack; the preview is an old snapshot.|期限切れか旅行が変更されています。再作成してください。下の表示は古い保存版です。|오프라인 패키지가 만료되었거나 여행이 변경되었습니다. 다시 생성하세요. 아래는 이전 저장본입니다.
就绪|Ready|利用可能|준비됨
未就绪|Unavailable|利用不可|사용 불가
行程|Trip|旅行|여행
每人整趟费用评估|Total cost per person|一人あたりの旅行全体の費用|1인당 전체 여행 비용
保存行程后可评估|Save a trip to estimate costs|保存後に費用を確認できます|여행 저장 후 비용 예상 가능
保存行程后可填写费用并评估预算。|Save your trip to enter costs and check your budget.|旅行を保存すると費用と予算を確認できます。|여행을 저장하면 비용과 예산을 확인할 수 있습니다.
评估待加载|Estimate loading|費用を読み込み中|비용 예상 불러오는 중
尚未设置每人预算|Per-person budget not set|一人あたりの予算は未設定|1인당 예산 미설정
费用待补充|Some costs are missing|費用に不足あり|일부 비용 누락
已超出预算|Over budget|予算超過|예산 초과
费用区间可能超出预算|Estimated range may exceed budget|費用の範囲が予算を超える可能性|예상 범위가 예산을 초과할 수 있음
估算费用在预算内|Estimate within budget|概算は予算内|예상 비용이 예산 이내
已填费用估算超出预算，需核对|Entered costs exceed budget; please verify.|入力費用が予算超過・要確認|입력 비용이 예산 초과, 확인 필요
查看费用明细和来源|Cost breakdown and sources|費用の内訳と出典|비용 내역 및 출처
填写 / 核对费用（人民币）|Enter / verify costs (CNY)|費用の入力・確認（人民元）|비용 입력 / 확인 (위안)
实际同行人数（住宿未填按 1 人估算）|Travelers (default: 1 for accommodation)|同行人数（宿泊計算の初期値：1人）|실제 인원 (숙박 기본값: 1명)
自动住宿房间数（未填按 1 间）|Rooms for automatic costing (default: 1)|自動計算の部屋数（初期値：1室）|자동 숙박 계산 객실 수 (기본값: 1실)
每段打车车辆数|Taxis per transfer|各区間のタクシー台数|구간별 택시 수
往返机票 / 跨城交通（每人合计）|Return flights / intercity travel (per person)|往復航空券・都市間移動（一人あたり）|왕복 항공편 / 도시 간 교통 (1인당 합계)
餐饮（每人每天）|Meals (per person per day)|食費（一人あたり・1日）|식비 (1인당 하루)
购物 / 其他（每人合计）|Shopping / other (per person)|買い物・その他（一人あたり）|쇼핑 / 기타 (1인당 합계)
备用金比例（%）|Contingency (%)|予備費（%）|예비비 비율 (%)
实际住宿晚数|Accommodation nights|実際の宿泊日数|실제 숙박 일수
自动按行程酒店和晚数计费（取消勾选可手填房晚及房价）|Calculate from itinerary hotels and nights (uncheck for manual entry)|旅程のホテルと泊数で自動計算（解除すると手動入力）|일정의 호텔과 숙박 일수로 자동 계산 (해제하면 직접 입력)
入住日期|Check-in date|チェックイン日|체크인 날짜
酒店名称|Hotel name|ホテル名|호텔 이름
房间数|Rooms|部屋数|객실 수
每间房 / 每晚|Per room / night|1室・1泊|객실당 / 1박
移除此晚|Remove night|この宿泊を削除|이 숙박일 제거
增加住宿晚数|Add night|宿泊を追加|숙박일 추가
门票及每日餐饮调整|Tickets and daily meal adjustments|入場料・日別食費の調整|입장권 및 일별 식비 조정
保存费用并评估|Save costs and estimate|費用を保存して計算|비용 저장 및 계산
价格待补充|Price unavailable|価格未登録|가격 정보 없음
（人民币元）| (CNY)|（人民元）| (위안)
 门票 / 人| Tickets / person| 入場料 / 人| 입장권 / 1인
 餐饮 / 人（空白沿用每日金额）| Meals / person (blank uses daily amount)| 食費 / 人（空欄は日額を使用）| 식비 / 1인 (빈칸은 일일 금액 사용)
预计费用|Estimated cost|予想費用|예상 비용
已计入费用|Included costs|計上済みの費用|반영된 비용
 / 人（整趟）| / person (whole trip)| / 人（旅行全体）| / 1인 (전체 여행)
 / 人| / person| / 人| / 1인
待补充：|Missing: |未登録：|누락: 
待补充 |Missing |未登録 |누락 
 · 待补充| · Missing| · 未登録| · 누락
已选择住宿|Accommodation selected|宿泊先を選択済み|숙소 선택됨
当前住宿|Current accommodation|現在の宿泊先|현재 숙소
已保存地点|Saved place|保存した地点|저장된 장소
行程口岸|Trip gateway|旅行の空港・駅|여행 공항 / 역
调整起终点|Edit start / end points|出発・到着地点を変更|출발 / 도착 지점 수정
起始点|Start point|出発地点|출발 지점
终止点|End point|到着地点|도착 지점
搜索酒店、口岸或景点|Search hotel, airport / station or attraction|ホテル・空港・駅・観光地を検索|호텔, 공항 / 역 또는 관광지 검색
搜索酒店或口岸|Search hotel or airport / station|ホテル・空港・駅を検索|호텔 또는 공항 / 역 검색
没有匹配地点，请换关键词|No matching places. Try another search.|該当する地点がありません。検索語を変えてください。|일치하는 장소가 없습니다. 다른 검색어를 입력하세요.
添加住宿 / 口岸|Add accommodation / gateway|宿泊・空港・駅を追加|숙소 / 공항 / 역 추가
搜索要添加的住宿或口岸|Search accommodation or gateway to add|追加する宿泊先・空港・駅を検索|추가할 숙소 또는 공항 / 역 검색
添加住宿或口岸|Add accommodation or gateway|宿泊先・空港・駅を追加|숙소 또는 공항 / 역 추가
停留分钟数|Stay in minutes|滞在時間（分）|체류 시간 (분)
停留（分钟）|Stay (minutes)|滞在（分）|체류 (분)
加入位置|Insert position|挿入位置|추가 위치
加入末尾|Add at end|最後に追加|마지막에 추가
住宿用途|Accommodation purpose|宿泊先の用途|숙소 용도
休息|Rest|休憩|휴식
过夜住宿|Overnight stay|宿泊|숙박
添加到行程|Add to trip|旅行に追加|여행에 추가
请选择住宿或口岸|Choose accommodation or gateway|宿泊先・空港・駅を選択|숙소 또는 공항 / 역 선택
请先选择要添加的住宿或口岸|Choose accommodation or a gateway to add first.|追加する宿泊先・空港・駅を先に選んでください。|먼저 추가할 숙소 또는 공항 / 역을 선택하세요.
停留时长须为 0~720 分钟|Stay must be 0–720 minutes.|滞在時間は0～720分です。|체류 시간은 0~720분이어야 합니다.
开放与闭馆|Opening & closures|営業時間・休館|운영 및 휴관
截止入场|Last entry|最終入場|마지막 입장
亮灯时段|Lighting hours|ライトアップ時間|조명 시간
建议停留|Suggested stay|滞在の目安|권장 체류
预约|Reservation|予約|예약
落客点|Drop-off point|降車地点|하차 지점
数据说明|Data notes|資料の説明|자료 안내
约 90 分钟（参考值）|About 90 min (reference)|約90分（参考値）|약 90분 (참고값)
无需预约|No reservation required|予約不要|예약 불필요
需预约|Reservation required|予約必要|예약 필요
闭馆信息待确认|Closure information unconfirmed|休館情報は未確認|휴관 정보 미확인
闭馆信息待复核|Closure information needs review|休館情報は要再確認|휴관 정보 재확인 필요
法定假日照常开放|Open on public holidays|祝日も開館|공휴일 정상 운영
假日期间闭馆|Closed during holidays|休日は休館|휴일 휴관
特定期闭馆|Closed during a special period|特定期間は休館|특정 기간 휴관
修缮闭馆|Closed for maintenance|修繕のため休館|보수 작업으로 휴관
请先在①创建行程，之后才能把 POI 加入某一天。|Create a trip in Trip setup before adding attractions.|旅行の設定で旅行を作成してから観光地を追加してください。|여행 설정에서 여행을 생성한 후 관광지를 추가하세요.
（次日）| (next day)|（翌日）| (다음 날)
全部已固定|All stops locked|すべて固定済み|모든 장소 고정됨
抵达日|Arrival day|到着日|도착일
未装载|Empty|未設定|비어 있음
已超建议 |Over suggested count |推奨数を超過 |권장 수 초과 
已达建议 |Suggested count reached |推奨数に到達 |권장 수 충족 
移到该天|Move to this day|この日に移動|이 날짜로 이동
请选择要移到哪一天|Choose the day to move to.|移動先の日を選んでください。|이동할 날짜를 선택하세요.
确认仍然加入|Add anyway|そのまま追加|그래도 추가
已移除|Removed|削除しました|제거됨
新建行程（填写①后保存）|New trip (complete Trip setup, then save)|新しい旅行（設定を入力して保存）|새 여행 (여행 설정 입력 후 저장)
日期待设置|Date not set|日程未設定|날짜 미설정
天数待设置|Duration not set|日数未設定|기간 미설정
行程天数必须是 1~15 的整数|Trip length must be a whole number from 1 to 15.|旅行日数は1～15の整数です。|여행 기간은 1~15의 정수여야 합니다.
抵达时间无法解析，请检查日期与时刻|Check the arrival date and time.|到着日と時刻を確認してください。|도착 날짜와 시간을 확인하세요.
请先选择抵达口岸（可用中文 / 英文 / 拼音搜索）|Choose an arrival airport / station first.|先に到着空港・駅を選んでください。|먼저 도착 공항 / 역을 선택하세요.
已勾选离境安排，请选择离境口岸（可用中文 / 英文 / 拼音搜索）|Choose a departure airport / station for your departure plan.|帰路の出発空港・駅を選んでください。|출국 일정의 출발 공항 / 역을 선택하세요.
已勾选离境安排，请填写离境日期与时刻|Enter a departure date and time.|出発日と時刻を入力してください。|출발 날짜와 시간을 입력하세요.
离境日期与时刻无法解析，请检查后重试|Check the departure date and time and try again.|出発日と時刻を確認して再度お試しください。|출발 날짜와 시간을 확인하고 다시 시도하세요.
设定有未保存的更改，请先保存行程，再生成推荐。|Save your changes before generating recommendations.|変更を保存してからおすすめを作成してください。|추천 생성 전에 변경 사항을 저장하세요.
请先勾选想安排的日期。|Select days to plan first.|先に計画する日を選んでください。|먼저 일정을 만들 날짜를 선택하세요.
所选日期已有安排，原内容会保留；请改选空白日，或复制行程后调整。|Selected days already have plans and will be kept. Choose empty days or duplicate the trip to edit.|選択日は既に予定があります。空の日を選ぶか旅行を複製して調整してください。|선택한 날짜의 기존 일정은 유지됩니다. 빈 날짜를 선택하거나 여행을 복제하여 수정하세요.
trip_engine 未就绪，请先启动行程模块。|trip_engine unavailable. Start the trip module.|trip_engineが利用できません。旅行モジュールを起動してください。|trip_engine을 사용할 수 없습니다. 여행 모듈을 시작하세요.
recommendation_engine 未就绪，请先启动推荐模块；仍可手动保存和编辑行程。|recommendation_engine unavailable. Start it for recommendations; manual editing is still available.|おすすめモジュールを起動してください。手動保存・編集は引き続き可能です。|추천 모듈을 시작하세요. 수동 저장 및 편집은 계속 가능합니다.
推荐已按住宿与出行偏好安排，可继续编辑。交通为规划估算，实际区间交通请在每日行程中计算。|Your itinerary follows your accommodation and preferences. You can keep editing. Transport times are estimates; calculate actual transfers in the daily itinerary.|宿泊先と希望に合わせて作成しました。編集を続けられます。移動時間は概算です。各日の旅程で実際の移動を計算してください。|숙소와 취향에 맞춰 일정이 생성되었습니다. 계속 편집할 수 있습니다. 교통 시간은 예상치이며 일별 일정에서 실제 구간 교통을 계산하세요.
所选日期没有可新增的推荐安排，请查看原因并调整日期或偏好。|No new recommendations for these days. Check the reasons and adjust dates or preferences.|選択日に追加可能な案がありません。理由を確認し日程や希望を変更してください。|선택한 날짜에 추가할 추천 일정이 없습니다. 이유를 확인하고 날짜나 취향을 조정하세요.
驾车（打车方案）|Drive (taxi route)|車（タクシー経路）|운전 (택시 경로)
骑行|Cycle|自転車|자전거
开始导航（高德）|Navigate (Amap)|ナビ開始（高徳）|길 안내 시작 (Amap)
高德网页版|Amap web|高徳ウェブ版|Amap 웹
查看已选路线 · |Selected route · |選択した経路 · |선택한 경로 · 
演示方案不能用于导航，请先计算真实路线。|Demo routes cannot be used for navigation. Calculate real routes first.|デモ経路は案内に使えません。実際の経路を計算してください。|시연 경로는 길 안내에 사용할 수 없습니다. 실제 경로를 먼저 계산하세요.
尚未选定可用的真实方案，请先计算并选择路线。|Calculate and select an available real route first.|利用可能な実際の経路を計算して選択してください。|이용 가능한 실제 경로를 먼저 계산하고 선택하세요.
当前区间已变化，请重新计算交通。|This transfer changed. Recalculate transport.|区間が変わりました。移動を再計算してください。|구간이 변경되었습니다. 교통을 다시 계산하세요.
线路形状预览 · 无底图与实时定位|Route shape preview · No base map or live location|経路の概略 · 地図・現在地なし|경로 모양 미리보기 · 지도 및 실시간 위치 없음
暂无完整线路轨迹；导航时在高德查看实时路线。|No complete route shape. Use Amap for live navigation.|完全な経路図はありません。高徳で最新の案内を確認してください。|전체 경로 모양이 없습니다. 실시간 길 안내는 Amap에서 확인하세요.
金额以人民币计入预算。|Budget amounts are recorded in CNY.|予算は人民元で計上します。|예산 금액은 위안으로 반영됩니다.
缺少有效汇率，请更新或手动填写。|Refresh or enter a valid exchange rate.|有効な為替レートを更新・入力してください。|유효한 환율을 새로고침하거나 입력하세요.
缺少有效汇率，请更新汇率或手动填写|Refresh or enter a valid exchange rate.|有効な為替レートを更新・入力してください。|유효한 환율을 새로고침하거나 입력하세요.
正在使用手动汇率；更新汇率可恢复参考汇率。|Using a manual rate; refresh to restore the reference rate.|手動レート使用中です。更新で参考レートに戻せます。|수동 환율 사용 중입니다. 새로고침하면 참고 환율로 돌아갑니다.
正在获取参考汇率；可手动填写汇率。|Loading reference rate; you can enter a rate manually.|参考レート取得中です。手動入力もできます。|참고 환율 불러오는 중, 직접 입력도 가능합니다.
外币金额为近似值。|Foreign currency amounts are approximate.|外貨の金額は概算です。|외화 금액은 근사치입니다.
日期未提供|Date unavailable|日付なし|날짜 없음
缓存已过期，请更新核对|Cached rate expired; refresh to verify|保存レート期限切れ・要更新|캐시 환율 만료, 새로고침 필요
缓存参考汇率|Cached reference rate|保存した参考レート|캐시 참고 환율
汇率须为大于 0 的有效数值|Exchange rate must be greater than zero.|為替レートは0より大きい値にしてください。|환율은 0보다 큰 유효한 값이어야 합니다.
每人预算超出允许范围|Per-person budget exceeds the allowed range.|一人あたりの予算が上限を超えています。|1인당 예산이 허용 범위를 초과합니다.
金额超出允许范围|Amount exceeds the allowed range.|金額が上限を超えています。|금액이 허용 범위를 초과합니다.
每人预算须为非负金额，最多两位小数|Budget must be non-negative, with up to 2 decimal places.|予算は0以上、小数点以下2桁以内です。|예산은 0 이상, 소수점 2자리 이내여야 합니다.
费用请输入非负金额，最多两位小数|Costs must be non-negative, with up to 2 decimal places.|費用は0以上、小数点以下2桁以内です。|비용은 0 이상, 소수점 2자리 이내여야 합니다.
每人预算|Budget per person|一人あたりの予算|1인당 예산
未设置|Not set|未設定|미설정
日期|Dates|日程|날짜
住宿|Accommodation|宿泊先|숙소
同行|Travelers|同行者|동행
双人出行|Two people|二人旅|2인 여행
带小孩|With children|子ども連れ|아이 동반
轻松|Relaxed|ゆったり|여유롭게
均衡|Balanced|標準|보통
紧凑|Packed|充実|알차게
预算 |Budget |予算 |예산 
余额 |Remaining |残額 |잔액 
设定已更新：|Settings updated: |設定を更新：|설정 업데이트: 
行程已创建：|Trip created: |旅行を作成：|여행 생성: 
已复制为新行程：|Trip duplicated: |旅行を複製：|여행 복제: 
已删除行程：|Trip deleted: |旅行を削除：|여행 삭제: 
已加入 Day |Added to Day |追加しました：Day |추가됨: Day 
确定删除“|Delete “|「|삭제: “
”？此操作不可撤销。|”? This cannot be undone.|」を削除しますか？取り消しできません。|”? 이 작업은 되돌릴 수 없습니다.
推荐|Recommendations|おすすめ|추천
时间校验|Time checks|時刻確認|시간 확인
交通|Transport|交通|교통
起点：|Start: |出発：|출발: 
终点：|End: |到着：|도착: 
来源：|Source: |出典：|출처: 
当前采用：|Selected: |選択中：|현재 선택: 
推荐理由：|Why: |おすすめ理由：|추천 이유: 
提示：|Note: |注意：|안내: 
已按兴趣排序：|Sorted by interests: |興味に合わせた表示順：|관심사순 정렬: 
（命中的类别排在前面，其余按热度）。| (matching categories first, then popularity).|（該当する種類を優先し、残りは人気順）。| (해당 유형 우선, 나머지는 인기순).
（已有安排，保留）| (existing plan kept)|（既存の予定を保持）| (기존 일정 유지)
 · 点击修改日期、住宿与偏好| · Select to edit dates, accommodation and preferences| · 日程・宿泊先・希望を変更| · 날짜, 숙소 및 취향 수정
 分钟| min|分|분
分钟| min|分|분
 个景点| attractions|か所の観光地|개 관광지
 项住宿 / 口岸| accommodation / gateway stops|件の宿泊・空港・駅|개 숙소 / 공항 / 역
 段交通待补| transfers pending|区間の移動が未設定|개 구간 교통 누락
 段交通方式受限| transfers with limited options|区間の移動に制限あり|개 구간 교통수단 제한
 条闭馆 / 时间风险| closure / time risks|件の休館・時刻リスク|건 휴관 / 시간 위험
建议游览 |Suggested visit: |見学目安：|권장 관람: 
建议停留 |Suggested stay: |滞在目安：|권장 체류: 
停留 |Stay |滞在 |체류 
 出发| depart| 出発| 출발
 抵达| arrive| 到着| 도착
 离开| leave| 出発| 떠남
结束待定|end time pending|終了時刻未定|종료 시간 미정
缓冲结束|arrival buffer ends|到着の余裕時間終了|도착 여유 시간 종료
待补齐交通后计算|Calculated after transport is added|移動設定後に計算|교통 추가 후 계산
等待更新到达时间|Arrival time update pending|到着時刻の更新待ち|도착 시간 업데이트 대기
终点交通未完成，请先计算当天全部区间交通|Final transfer is incomplete. Calculate all transport segments for this day first.|最終地点への移動が未計算です。この日の全区間の移動を先に計算してください。|마지막 구간 교통이 미완료입니다. 먼저 당일 모든 구간 교통을 계산하세요.
周一|Mon|月曜|월요일
周二|Tue|火曜|화요일
周三|Wed|水曜|수요일
周四|Thu|木曜|목요일
周五|Fri|金曜|금요일
周六|Sat|土曜|토요일
周日|Sun|日曜|일요일
使用引导|Getting started|使い方ガイド|사용 가이드
关闭引导|Close guide|ガイドを閉じる|가이드 닫기
引导进度|Guide progress|ガイドの進行状況|가이드 진행 상황
所在区域|Where to find it|操作する場所|위치
跳过引导|Skip guide|ガイドをスキップ|가이드 건너뛰기
上一步|Previous|前へ|이전
下一步|Next|次へ|다음
去设置行程|Set up your trip|行程を設定する|여행 설정하기
先确定这趟旅程|Start with your trip details|まず旅の基本情報を決める|여행 기본 정보 정하기
填写行程天数、抵达时间和已预订的住宿，再选择兴趣与节奏，点击“保存行程”开始规划。|Enter the trip length, arrival time and accommodation you have booked. Choose your interests and pace, then select “Save trip” to start planning.|旅行日数、到着時刻、予約済みの宿泊先を入力し、興味とペースを選んで「行程を保存」を押しましょう。|여행 일수, 도착 시간, 예약한 숙소를 입력하세요. 관심사와 여행 속도를 선택한 뒤 ‘여행 저장’을 누르면 계획을 시작할 수 있어요.
返程信息可选；预算填写每人整趟金额。所有时间按北京时间安排。|Return details are optional. Enter a budget per person for the entire trip. All times use Beijing time.|帰路の情報は任意です。予算は一人あたりの旅行全体の金額を入力してください。時刻はすべて北京時間です。|귀국 정보는 선택 사항이에요. 예산은 1인당 전체 여행 금액을 입력하세요. 모든 시간은 베이징 시간 기준이에요.
选出想去的地方|Choose places to visit|行きたい場所を選ぶ|가고 싶은 장소 고르기
想省心，可以选择游玩日期后生成推荐行程；想自己选，可以搜索景点，打开详情并加入指定日期。|For a quick start, choose your sightseeing days and generate a recommended itinerary. Or search attractions, open their details and add them to a day of your choice.|観光する日を選び、おすすめ行程を生成できます。自分で選ぶ場合は、観光地を検索して詳細を開き、希望の日に追加しましょう。|편하게 시작하려면 관광 날짜를 선택하고 추천 일정을 생성하세요. 직접 고르려면 관광지를 검색하고 상세 정보를 열어 원하는 날짜에 추가하세요.
安排景点前先保存行程。推荐结果可以继续编辑，生成前请确认要安排的日期。|Save your trip before adding attractions. Recommendations remain editable; confirm which days to plan before generating them.|観光地を追加する前に行程を保存してください。おすすめ行程は後から編集できます。生成前に対象の日付を確認しましょう。|관광지를 추가하기 전에 여행을 저장하세요. 추천 결과는 수정할 수 있어요. 생성 전에 계획할 날짜를 확인하세요.
把每一天排顺|Arrange each day|一日の流れを整える|하루 일정 정리하기
展开某一天，查看起点和终点，调整景点顺序，再计算区间交通并选择合适的出行方式。|Expand a day to check its start and end points and reorder attractions. Then calculate transfers and choose how to travel.|各日を開いて出発・到着地点を確認し、観光地の順番を調整します。区間の移動を計算して交通手段を選びましょう。|날짜를 펼쳐 출발지와 도착지를 확인하고 관광지 순서를 조정하세요. 구간별 교통을 계산한 뒤 이동 수단을 선택하세요.
需要途中休息或更换酒店时，可添加住宿或口岸；调整安排后记得重新计算交通。|Add accommodation or gateway stops when you need a break or a hotel change. Recalculate transport after changing the itinerary.|途中の休憩やホテル変更には、宿泊先や空港・駅を追加できます。行程を変更したら移動を再計算してください。|중간에 쉬거나 호텔을 변경하려면 숙소 또는 공항·역을 추가할 수 있어요. 일정을 변경한 뒤에는 교통을 다시 계산하세요.
检查提醒与费用|Check reminders and costs|注意事項と費用を確認する|알림과 비용 확인하기
查看开放、预约与时间冲突提醒，按提示调整安排。展开每日行程上方的费用评估，核对预算和费用明细。|Review opening hours, booking requirements and timing conflicts, then adjust your plans. Expand the cost estimate above your daily itinerary to check your budget and expenses.|営業時間、予約、時間の重複に関する注意事項を確認し、行程を調整します。日別行程の上にある費用見積もりを開き、予算と明細を確認しましょう。|운영 시간, 예약, 시간 충돌 알림을 확인하고 일정을 조정하세요. 일일 일정 위의 비용 평가를 펼쳐 예산과 비용 내역을 확인하세요.
门票和住宿金额是规划参考；待补充项与开放信息需要在出发前确认。|Ticket and accommodation costs are planning estimates. Confirm missing costs and opening information before departure.|入場料や宿泊費は計画用の目安です。未入力の費用や営業情報は出発前に確認してください。|입장료와 숙박비는 계획용 참고 금액이에요. 미입력 비용과 운영 정보는 출발 전에 확인하세요.
出发前保存问路包|Save your offline directions|出発前に道案内を保存する|출발 전 길 안내 저장하기
安排确认后生成离线包，下载问路卡 HTML 并保存到设备。下载的文件可以在没有网络或关闭本地服务时打开。|Once your plans are ready, generate the offline package and download the directions HTML to your device. The downloaded file opens without internet or the local service.|行程が決まったらオフラインパッケージを生成し、道案内のHTMLを端末に保存しましょう。保存したファイルは、ネット接続やローカルサービスがなくても開けます。|일정을 확정한 뒤 오프라인 패키지를 생성하고 길 안내 HTML을 기기에 다운로드하세요. 다운로드한 파일은 인터넷이나 로컬 서비스 없이 열 수 있어요.
中文地名和问路卡方便向当地人问路。行程修改后，请重新生成并下载最新文件。|Chinese place names and direction cards help you ask locals for directions. After changing your trip, generate and download a new file.|中国語の地名と道案内カードは、現地の人に道を尋ねる際に使えます。行程を変更したら、最新のファイルを再生成して保存してください。|중국어 지명과 길 안내 카드를 현지인에게 보여주며 길을 물을 수 있어요. 일정을 변경하면 최신 파일을 다시 생성하고 다운로드하세요.
界面、内置景点简介与常见行程建议会随语言切换。地图与部分原始资料可能保留原文；中文地名与问路卡保留，方便向当地人问路。|The interface, built-in attraction descriptions and common trip suggestions follow your language choice. Maps and some source material may remain in their original language. Chinese place names and direction cards are kept for asking locals.|画面、登録済み観光地の紹介、よく使う行程の提案は選択した言語で表示されます。地図と一部の原資料は原文のままの場合があります。現地で道を尋ねられるよう、中国語の地名と道案内カードを残します。|화면, 내장 관광지 소개, 일반적인 여행 제안은 선택한 언어로 표시돼요. 지도와 일부 원본 자료는 원문으로 표시될 수 있어요. 현지인에게 길을 물을 수 있도록 중국어 지명과 길 안내 카드는 유지돼요.
引导章节|Guide chapters|ガイドの目次|가이드 목차
提醒与费用|Reminders & costs|注意事項と費用|알림과 비용
操作要点|What to do|操作のポイント|사용 방법
示例（仅作说明）|Example (for illustration)|例（説明用）|예시 (설명용)
常见问题|Common questions|よくある質問|자주 묻는 질문
`.trim().split('\n').map(line => line.split('|'));
