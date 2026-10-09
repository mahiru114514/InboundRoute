# 上海酒店与景点价格调研（2026-10-06）

覆盖当前主数据中的12家酒店和45个景点。所有记录均保留实体ID、来源、币种、计价单位及适用范围；已接入预算自动参考估算，手填金额优先，未知和实体冲突不自动计入。

酒店是每间每晚的公开标准客房平均房价范围，不是指定入住日期的报价；早餐、税费、房型、退改条件需复核。按[2026-09-30美元兑人民币中间价](https://www.chinamoney.org.cn/chinese/bkccpr/?tab=2)1美元=6.7351元折算，向外取整到10元。酒店费用需按房间数、晚数及实际人数分摊，不能直接作为每人每晚费用。

景点以成人普通入园/参观为基准；公共区域免费不表示内部展馆或体验免费。上海博物馆按用户要求基础标注免费，特展票价另列；这一产品标注不代表当前人民广场馆可免费入馆。部分资料较早或来自第三方/游客，标记为参考并待复核。未查实价格使用“待核实”，不填0；活动已结束的优惠价不作为当前价格。

重点：宏安瑞士大酒店的中英文实体冲突；环球金融中心没有查实当前观光票；乌中市集未查到明确门票声明；城市规划展示馆旧收费介绍和现有免费参考存在年代差异。

## 酒店

| ID / 酒店 | 人民币参考（元/间/晚） | 原始美元范围 | 范围与来源 |
|---|---:|---:|---|
| hotel_hyland / 上海宏安瑞士大酒店 | 待核实 | 实体冲突 | 中文名上海宏安瑞士大酒店指向Swissotel Grand；英文名及南京东路坐标指向Radisson Collection Hyland。须先核对实体，禁止直接匹配价格。 [来源1](https://www.swissotel.cn/hotels/shanghai/) [来源2](https://www.tripadvisor.com/Hotel_Review-g308272-d1021906-Reviews-Swissotel_Grand_Shanghai-Shanghai.html) [来源3](https://www.tripadvisor.com/Hotel_Review-g308272-d299549-Reviews-Radisson_Collection_Hotel_Hyland_Shanghai-Shanghai.html) |
| hotel_peace / 和平饭店 | 2280—3050 | 339—452 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d303020-Reviews-Fairmont_Peace_Hotel-Shanghai.html) |
| hotel_westin_bund / 威斯汀大饭店 | 1190—1550 | 177—230 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d301757-Reviews-The_Westin_Bund_Center_Shanghai-Shanghai.html) |
| hotel_porter / 波特曼丽思卡尔顿酒店 | 1290—2010 | 192—298 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d302253-Reviews-The_Portman_Ritz_Carlton_Shanghai-Shanghai.html) |
| hotel_jinjiang / 锦江饭店 | 570—940 | 85—139 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d303013-Reviews-Jin_Jiang_Hotel_Shanghai-Shanghai.html) |
| hotel_pudong_shangrila / 浦东香格里拉大酒店 | 1110—2590 | 166—384 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d307540-Reviews-Pudong_Shangri_La_Shanghai-Shanghai.html) |
| hotel_waldorf_bund / 上海外滩华尔道夫酒店 | 2430—3660 | 361—542 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d1800802-Reviews-Waldorf_Astoria_Shanghai_on_the_Bund-Shanghai.html) |
| hotel_peninsula / 上海半岛酒店 | 2510—4120 | 373—611 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d1461776-Reviews-The_Peninsula_Shanghai-Shanghai.html) |
| hotel_ritz_pudong / 上海浦东丽思卡尔顿酒店 | 2410—4690 | 359—695 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://cn.tripadvisor.com/Hotel_Review-g308272-d1654265-Reviews-The_Ritz_Carlton_Shanghai_Pudong-Shanghai.html) |
| hotel_garden_okura / 上海花园饭店 | 830—2000 | 124—296 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d301722-Reviews-Okura_Garden_Hotel_Shanghai-Shanghai.html) |
| hotel_marriott_city / 上海雅居乐万豪酒店 | 1200—2180 | 179—323 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d1954359-Reviews-Shanghai_Marriott_Marquis_City_Centre-Shanghai.html) |
| hotel_conrad / 上海康莱德酒店 | 1190—2100 | 177—311 | Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。 [来源1](https://www.tripadvisor.com/Hotel_Review-g308272-d23833016-Reviews-Conrad_Shanghai-Shanghai.html) |

宏安瑞士大酒店候选参考：Swissotel约790—1320元/间/晚（USD118—195）；海仑丽笙精选候选约800—1510元/间/晚（USD119—224）。这两项仅用于帮助核对，不关联到当前hotel_hyland价格。

## 景点

| ID / 景点 | 成人基础参考（元/人） | 证据类别 | 适用范围与来源 |
|---|---:|---|---|
| sh_poi_00042 / 外滩 | 0 | secondary_reference | 外滩公共步道；不含游船及收费体验 [来源1](https://m.ly.com/scenery_1/detail/?sceneryId=8259) |
| sh_poi_00088 / 上海博物馆 | 0 | product_policy_base | 按产品口径基础标注免费，特展单独注明：人民广场馆美洲文明特展全价148、指定日135；2026-07-09至2027-11-14。当前特展期间人民广场馆不展出其他展览，实际入馆需购票（符合免票资格者除外）；指定日排除周末、国定假日及部分寒暑假日期；优惠票74、亲子200/320须匹配资格 [来源1](https://www.shanghaimuseum.net/mu/frontend/pg/m/article/id/I00005037) [来源2](https://www.jfdaily.com.cn/sgh/detail?id=4066231) |
| sh_poi_00107 / 豫园 | 30—40 | official_reference | 豫园日场成人：4—6月、9—11月40，其余月份30；不含豫园商城灯会等活动 [来源1](https://www.shanghai.gov.cn/huangpu/index.html) |
| sh_poi_00119 / 朱家角古镇 | 0 | mixed_reference | 古镇街区免大门票；课植园等场馆另收费，官方联票60，不能把联票当街区门票；街区免费依据第三方游览资料，官网可核实联票。 [来源1](https://www.zhujiajiao.com/cn/questions/) [来源2](https://www.shanghai.gov.cn/nw15343/20260520/076b925cd6424c99a319e9199536af42.html) [来源3](https://you.ctrip.com/sight/shanghai2/14903.html) |
| sh_poi_00120 / 东方明珠 | 199 | secondary_reference | 成人观光参考199；不同球体、楼层、联票组合名称不一致，须确认具体票种后使用 [来源1](https://m.qianlvtong.com/home/product/id/1.html?shco=1234567912345) [来源2](https://ep.shxwcb.com/2025/09/12/img/08-090912.pdf) |
| sh_poi_00121 / 上海中心大厦 | 180 | official_reference | 上海之巅118层成人参考180；125/126层等组合另收费，非全部楼层通票 [来源1](https://www.gzw.sh.gov.cn/shgzw_zxzx_gqdt/20230919/5dd39d37aaa648d9aee71573b4c901b6.html) [来源2](https://ep.shxwcb.com/2026/08/08/20260808-06-07-1_20260807215208.html) |
| sh_poi_00122 / 金茂大厦 | 120 | official_reference | 88层观光成人标准参考120；不含云中漫步等项目 [来源1](https://whlyj.sh.gov.cn/cysc/20250912/b34d37b3289f43389c18d98c8ae23d62.html) [来源2](https://www.klook.cn/zh-CN/activity/3972-jin-mao-tower-tickets-shanghai/) |
| sh_poi_00123 / 上海环球金融中心 | 待核实 | unavailable | 未核实当前在售观光票价。2024年因功能调整被取消4A级资质；此公告不等于确认整个大厦停业，不使用旧观光票价 [来源1](https://whlyj.sh.gov.cn/jqxxgk/20240524/8bbd2926eaae4ea59fa1319125f6707e.html) |
| sh_poi_00124 / 龙华寺 | 0 | secondary_reference | 普通入寺参考免费，未找到本次可读取的官方常规票价公告；香火、素面、法会另计，需核实 [来源1](https://travelnews.qunar.com/ugc/shanghai-longhua-temple-winter-pet) [来源2](https://travelnews.qunar.com/qa_strategy/shanghai-longhuasi-weekend-prayer-photo-travel-guide) |
| sh_poi_00125 / 静安寺 | 50 | secondary_reference | 常规成人参考50；节庆、特别开放时段可能不同，不套用常规票价 [来源1](https://www.jtb.co.jp/kaigai_guide/china/people_s_republic_of_china/SHA/111928/) |
| sh_poi_00126 / 武康路历史文化名街 | 0 | secondary_reference | 公共街道步行免费；沿街建筑内部参观另核实 [来源1](https://www.ly.com/scenery/BookSceneryTicket_815429.html) |
| sh_poi_00127 / 田子坊 | 0 | secondary_reference | 街区公共游览免费；购物、餐饮、展览另计 [来源1](https://you.ctrip.com/destinationsite/sight/shanghai2/64755-traffic.html) |
| sh_poi_00128 / 新天地 | 0 | secondary_reference | 开放街区免费；商店、餐饮、石库门屋里厢等不包含 [来源1](https://m.sh.bendibao.com/jingdian/shanghaixintiandi/price/) |
| sh_poi_00129 / 乌中市集 | 待核实 | unverified | 找到政府市集介绍，未找到明确门票价格声明；市场购物不是门票，不凭类型自动填0 [来源1](https://touch.shio.gov.cn/jsp/tjcf_detail.jsp?id=196&lineId=1) |
| sh_poi_00130 / 世纪公园 | 0 | official_reference | 公园入园免费；园内另收费项目另计 [来源1](https://www.shanghai.gov.cn/nw4411/20240329/6f67596eb1b84a39abe4ddbaf7c85b64.html) |
| sh_poi_00131 / 中山公园 | 0 | official_reference | 公园入园免费 [来源1](https://www.shanghai.gov.cn/cnq/20230824/3672e702721245ebaa47e9f1631e6e80.html) |
| sh_poi_00132 / 上海植物园 | 0 | official_reference | 公共园区免费；专类园、温室等需另外核实票种与价格 [来源1](https://lhsr.sh.gov.cn/gyhd/20211230/5ff26486-7b39-424b-93f8-35f9bd2bf93c.html) |
| sh_poi_00133 / 共青森林公园 | 0 | official_reference | 公园免费；游乐等另计 [来源1](https://lhsr.sh.gov.cn/gyhd/20210623/e7da767b-26d2-4cf9-b043-e3dc6356ded3.html) |
| sh_poi_00134 / 静安公园 | 0 | media_reference | 公园公共区域参考免费；依据2025年免费开放报道，收费项目另计 [来源1](https://ep.shxwcb.com/2025/04/09/img/030409.pdf) |
| sh_poi_00135 / 徐家汇公园 | 0 | secondary_reference | 公园入园参考免费；来源含游客反馈，需复核 [来源1](https://you.ctrip.com/sight/shanghai2/109946.html) |
| sh_poi_00136 / 长风公园 | 0 | official_reference | 公园本体免费；不包含海洋世界等收费场馆 [来源1](https://www.shpt.gov.cn/zhengwu/kpgz-kwzdgz/2024/105/158387.html) |
| sh_poi_00137 / 上海动物园 | 40 | official_reference | 上海动物园成人标准40；非上海野生动物园，游乐另计；不沿用已结束的活动优惠 [来源1](https://www.shanghai.gov.cn/nw17239/20260519/b4cc7db33efe486b83f02e1b9dc4b712.html) |
| sh_poi_00138 / 鲁迅公园 | 0 | official_reference | 公园免费开放，无需预约；内部收费项目另计 [来源1](https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002005/20250215/74e3afa7-144b-422c-9f5d-1608d530d89c.html) |
| sh_poi_00139 / 世博文化公园 | 0 | mixed_reference | 公共园区免费；温室花园、申园等分区及活动不能默认免费，双子山预约与收费政策需按日期复核 [来源1](https://english.shanghai.gov.cn/en-Parks/20240920/4c47d7f55b3f4a25b043981f4f54434d.html) [来源2](https://zh.wikipedia.org/wiki/上海世博文化公园) |
| sh_poi_00140 / 辰山植物园 | 60 | official_republication | 普通成人60；优惠资格和主题体验另计 [来源1](https://www.shobserver.cn/sgh/detail?id=1724704) |
| sh_poi_00141 / 上海博物馆东馆 | 0 | mixed_reference | 东馆常设展免费；付费特展另计，不能套用人民广场馆收费或把所有特展都标免费 [来源1](https://www.shanghaimuseum.cn/mu/frontend/pg/service/visit-east) [来源2](https://ep.shxwcb.com/2026/01/29/img/080129.pdf) |
| sh_poi_00142 / 上海自然博物馆 | 30 | official_reference | 成人30；老人、学生及免费资格按官网，特定体验另计 [来源1](https://www.snhm.org.cn/cgfw/cgzx.htm) |
| sh_poi_00143 / 上海天文馆 | 30 | official_reference | 成人参观30；老人25、学生15；球幕电影等另计，免票资格按官方 [来源1](https://www.shanghai.gov.cn/pudong/index.html) |
| sh_poi_00144 / 世博会博物馆 | 0 | official_reference | 常设展免费；特展、活动及体验不在本项内。来源较早，出行前复核 [来源1](https://www.shanghai.gov.cn/nw9822/20200906/0001-9822_1225204.html) |
| sh_poi_00145 / 上海城市规划展示馆 | 0 | secondary_reference | 当前免费预约参观参考；旧政府介绍仍有30元，官网当前须知未明列价格，须复核，不能采用旧票价 [来源1](https://sh.bendibao.com/jingdian/shanghaichengshiguihuazhanshiguan/) [来源2](https://www.supec.org.cn/employ-index.html?tab=tab1) [来源3](https://touch.shio.gov.cn/jsp/whjljd_detail.jsp?id=74) |
| sh_poi_00146 / 中国航海博物馆 | 30 | official_reference | 普通成人馆票30；2021价格批复，潜艇参观等单独项目另核实 [来源1](https://www.shanghai.gov.cn/gwk/search/content/48c1a399c92c44f281afdab6b9c7d56e) [来源2](https://tt.shmmc.com.cn/SHMM_WeChat/visit?shelfCode=SHMM01) |
| sh_poi_00147 / 广富林文化遗址 | 0 | official_reference | 公共区域免费；广富林文化展示馆30（2026报道），其他场馆另计 [来源1](https://www.meet-in-shanghai.net/cn/news/the-public-area-of-guangfulin-cultural-site-will-be-open-to-the-public-free-of-charge-from-tomorrow-291420/) [来源2](https://whlyj.sh.gov.cn/gqfc/20260109/755016cfa16649e3a9e761598b4857f9.html) |
| sh_poi_00148 / 浦东美术馆 | 100—150 | official_reference | 2025公布成人日场：工作日100、周末法定节假日150；17点后80/120；2026实际展览和票种需复核 [来源1](https://whlyj.sh.gov.cn/gqfc/20250515/2c814efbcb234c31a36d94c933e4b5e6.html) [来源2](https://www.museumofartpd.org.cn/ticketing?id=10) |
| sh_poi_00149 / 上海宋庆龄故居纪念馆 | 20 | official_reference | 上海故居普通成人20；学生等优惠另计，不能混同北京宋庆龄故居 [来源1](https://www.meet-in-shanghai.net/cn/revolutionary-venues/the-former-residence-of-song-qingling-in-shanghai-is-basically-displayed-145303/) [来源2](https://www.shsoong-chingling.com/list-canguanyuyue.html) |
| sh_poi_00150 / 上海邮政博物馆 | 0 | official_reference | 博物馆免费；开放日及预约需核实 [来源1](https://shanghai.chinapost.com.cn/xhtml1/report/23051/1809-1.htm) [来源2](https://whlyj.sh.gov.cn/gqfc/20241218/b7a180236c7d47cba6b939a6092ae6c1.html) |
| sh_poi_00151 / 七宝古镇 | 0 | mixed_reference | 古镇街区免首道门票；内部展馆分别收费，不当作整镇收费 [来源1](https://sh.bendibao.com/tour/2023114/265817.shtm) [来源2](https://whlyj.sh.gov.cn/4ajjq/20201124/0b873aa685d44ddcbb1bd66609e53b0f.html) |
| sh_poi_00152 / 南翔老街 | 0 | secondary_reference | 老街公共游览免费；古猗园、檀园等收费项目另核实 [来源1](https://sh.bendibao.com/jingdian/nanxianglaojie/) |
| sh_poi_00153 / 枫泾古镇 | 0 | mixed_reference | 古镇街区免费；2025场馆联票参考50，不能套用已结束的半价活动 [来源1](https://m.cncn.com/piao/1255) [来源2](https://whlyj.sh.gov.cn/cmsres/60/60195750731c4871a03be0d896b2c7dc/7fdaf71fb7145466340c367268a7c85f.pdf) |
| sh_poi_00154 / 新场古镇 | 0 | official_reference | 古镇公共游览免费；展馆及商业消费另计 [来源1](https://www.meet-in-shanghai.net/tc/news/spring-is-coming-to-shanghaiin-this-free-admission-jiangnan-water-townfeel-the-freshness-of-spring-in-one-go-268898/) |
| sh_poi_00155 / 北外滩滨江绿地 | 0 | secondary_reference | 滨江公共绿地参考免费；收费设施另计 [来源1](https://you.ctrip.com/sight/shanghai2/2043565.html) [来源2](https://news.sina.com.cn/o/2012-07-17/062024787721.shtml) |
| sh_poi_00156 / 徐汇滨江绿地 | 0 | secondary_reference | 滨江公共步道参考免费；沿线美术馆、活动另计 [来源1](https://you.ctrip.com/sight/shanghai2/1483401.html) |
| sh_poi_00157 / 东方绿舟 | 50 | official_reference | 成人普通入园50；住宿、水上活动、体验等另计 [来源1](https://www.shanghai.gov.cn/nw17239/20250225/0e9088c68a81408394b0a88580677d95.html) |
| sh_poi_00158 / 佘山国家森林公园 | 0 | official_republication | 东、西佘山公共登山游览免费；天马山、天文博物馆及挖笋体验等不能默认免费 [来源1](https://www.shobserver.cn/sgh/detail?id=1724704) [来源2](https://www.songjiang.gov.cn/xwzx/001001/20260325/13758570-6c3d-4f5e-97c9-37d24cbd5a1b.html) |
| sh_poi_00159 / 上海海湾国家森林公园 | 80 | media_reference | 普通成人原价参考80；依据2025报道，2026需复核，不沿用限时60优惠 [来源1](https://ep.shxwcb.com/2025/11/27/img/06-071127.pdf) [来源2](https://whlyj.sh.gov.cn/bmxx/20210514/7692b4249ca5472ba5a5eae918e747ff.html) |
| sh_poi_00160 / 滴水湖 | 0 | secondary_reference | 环湖公共游览参考免费；游船、水上活动及附近景区另计 [来源1](https://you.ctrip.com/destinationsite/sight/shanghai2/64745-sight.html) |

## 后续预填依据

- 先修正实体冲突，并区分成人、儿童、老人、学生等票种；有明确有效期的价格按行程日期匹配。
- 酒店按入住/退房日期、房型、间数取得范围或报价；保留来源和报价时间。
- 现有用户手填费用优先；历史参考和第三方参考应标为估算，允许修改。
- 公共区域和付费内部项目分别计费；不因公共区域免费而忽略已选内部项目。
- 有可用基础价格的记录启用auto_fill_eligible，仅用于参考估算；未知和实体冲突为false。豫园按月份选价，特展费用提示另列。
