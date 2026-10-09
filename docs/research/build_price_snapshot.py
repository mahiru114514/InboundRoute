"""Generate the sourced reference snapshot used by automatic budget estimates."""
import json
import sys
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modules.trip_engine.poi_seed import POIS

DATE = '2026-10-06'
FX = Decimal('6.7351')
FX_URL = 'https://www.chinamoney.org.cn/chinese/bkccpr/?tab=2'
TA = 'https://www.tripadvisor.com/Hotel_Review-g308272-d{}-Reviews-{}-Shanghai.html'
hotel_rows = [
 ('hotel_peace',339,452,'303020','Fairmont_Peace_Hotel'),
 ('hotel_westin_bund',177,230,'301757','The_Westin_Bund_Center_Shanghai'),
 ('hotel_porter',192,298,'302253','The_Portman_Ritz_Carlton_Shanghai'),
 ('hotel_jinjiang',85,139,'303013','Jin_Jiang_Hotel_Shanghai'),
 ('hotel_pudong_shangrila',166,384,'307540','Pudong_Shangri_La_Shanghai'),
 ('hotel_waldorf_bund',361,542,'1800802','Waldorf_Astoria_Shanghai_on_the_Bund'),
 ('hotel_peninsula',373,611,'1461776','The_Peninsula_Shanghai'),
 ('hotel_ritz_pudong',359,695,'1654265','The_Ritz_Carlton_Shanghai_Pudong'),
 ('hotel_garden_okura',124,296,'301722','Okura_Garden_Hotel_Shanghai'),
 ('hotel_marriott_city',179,323,'1954359','Shanghai_Marriott_Marquis_City_Centre'),
 ('hotel_conrad',177,311,'23833016','Conrad_Shanghai'),
]
# POI ID suffix, adult base price in yuan, evidence tier, exact scope, source URLs.
rows = [
 ('00042',0,0,'secondary_reference','外滩公共步道；不含游船及收费体验',['https://m.ly.com/scenery_1/detail/?sceneryId=8259']),
 ('00088',0,0,'product_policy_base','按产品口径基础标注免费，特展单独注明：人民广场馆美洲文明特展全价148、指定日135；2026-07-09至2027-11-14。当前特展期间人民广场馆不展出其他展览，实际入馆需购票（符合免票资格者除外）；指定日排除周末、国定假日及部分寒暑假日期；优惠票74、亲子200/320须匹配资格',['https://www.shanghaimuseum.net/mu/frontend/pg/m/article/id/I00005037','https://www.jfdaily.com.cn/sgh/detail?id=4066231']),
 ('00107',30,40,'official_reference','豫园日场成人：4—6月、9—11月40，其余月份30；不含豫园商城灯会等活动',['https://www.shanghai.gov.cn/huangpu/index.html']),
 ('00119',0,0,'mixed_reference','古镇街区免大门票；课植园等场馆另收费，官方联票60，不能把联票当街区门票',['https://www.zhujiajiao.com/cn/questions/','https://www.shanghai.gov.cn/nw15343/20260520/076b925cd6424c99a319e9199536af42.html']),
 ('00120',199,199,'secondary_reference','成人观光参考199；不同球体、楼层、联票组合名称不一致，须确认具体票种后使用',['https://m.qianlvtong.com/home/product/id/1.html?shco=1234567912345','https://ep.shxwcb.com/2025/09/12/img/08-090912.pdf']),
 ('00121',180,180,'official_reference','上海之巅118层成人参考180；125/126层等组合另收费，非全部楼层通票',['https://www.gzw.sh.gov.cn/shgzw_zxzx_gqdt/20230919/5dd39d37aaa648d9aee71573b4c901b6.html','https://ep.shxwcb.com/2026/08/08/20260808-06-07-1_20260807215208.html']),
 ('00122',120,120,'official_reference','88层观光成人标准参考120；不含云中漫步等项目',['https://whlyj.sh.gov.cn/cysc/20250912/b34d37b3289f43389c18d98c8ae23d62.html','https://www.klook.cn/zh-CN/activity/3972-jin-mao-tower-tickets-shanghai/']),
 ('00123',None,None,'unavailable','未核实当前在售观光票价。2024年因功能调整被取消4A级资质；此公告不等于确认整个大厦停业，不使用旧观光票价',['https://whlyj.sh.gov.cn/jqxxgk/20240524/8bbd2926eaae4ea59fa1319125f6707e.html']),
 ('00124',0,0,'secondary_reference','普通入寺参考免费，未找到本次可读取的官方常规票价公告；香火、素面、法会另计，需核实',['https://travelnews.qunar.com/ugc/shanghai-longhua-temple-winter-pet','https://travelnews.qunar.com/qa_strategy/shanghai-longhuasi-weekend-prayer-photo-travel-guide']),
 ('00125',50,50,'secondary_reference','常规成人参考50；节庆、特别开放时段可能不同，不套用常规票价',['https://www.jtb.co.jp/kaigai_guide/china/people_s_republic_of_china/SHA/111928/']),
 ('00126',0,0,'secondary_reference','公共街道步行免费；沿街建筑内部参观另核实',['https://www.ly.com/scenery/BookSceneryTicket_815429.html']),
 ('00127',0,0,'secondary_reference','街区公共游览免费；购物、餐饮、展览另计',['https://you.ctrip.com/destinationsite/sight/shanghai2/64755-traffic.html']),
 ('00128',0,0,'secondary_reference','开放街区免费；商店、餐饮、石库门屋里厢等不包含',['https://m.sh.bendibao.com/jingdian/shanghaixintiandi/price/']),
 ('00129',None,None,'unverified','找到政府市集介绍，未找到明确门票价格声明；市场购物不是门票，不凭类型自动填0',['https://touch.shio.gov.cn/jsp/tjcf_detail.jsp?id=196&lineId=1']),
 ('00130',0,0,'official_reference','公园入园免费；园内另收费项目另计',['https://www.shanghai.gov.cn/nw4411/20240329/6f67596eb1b84a39abe4ddbaf7c85b64.html']),
 ('00131',0,0,'official_reference','公园入园免费',['https://www.shanghai.gov.cn/cnq/20230824/3672e702721245ebaa47e9f1631e6e80.html']),
 ('00132',0,0,'official_reference','公共园区免费；专类园、温室等需另外核实票种与价格',['https://lhsr.sh.gov.cn/gyhd/20211230/5ff26486-7b39-424b-93f8-35f9bd2bf93c.html']),
 ('00133',0,0,'official_reference','公园免费；游乐等另计',['https://lhsr.sh.gov.cn/gyhd/20210623/e7da767b-26d2-4cf9-b043-e3dc6356ded3.html']),
 ('00134',0,0,'media_reference','公园公共区域参考免费；依据2025年免费开放报道，收费项目另计',['https://ep.shxwcb.com/2025/04/09/img/030409.pdf']),
 ('00135',0,0,'secondary_reference','公园入园参考免费；来源含游客反馈，需复核',['https://you.ctrip.com/sight/shanghai2/109946.html']),
 ('00136',0,0,'official_reference','公园本体免费；不包含海洋世界等收费场馆',['https://www.shpt.gov.cn/zhengwu/kpgz-kwzdgz/2024/105/158387.html']),
 ('00137',40,40,'official_reference','上海动物园成人标准40；非上海野生动物园，游乐另计；不沿用已结束的活动优惠',['https://www.shanghai.gov.cn/nw17239/20260519/b4cc7db33efe486b83f02e1b9dc4b712.html']),
 ('00138',0,0,'official_reference','公园免费开放，无需预约；内部收费项目另计',['https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002005/20250215/74e3afa7-144b-422c-9f5d-1608d530d89c.html']),
 ('00139',0,0,'mixed_reference','公共园区免费；温室花园、申园等分区及活动不能默认免费，双子山预约与收费政策需按日期复核',['https://english.shanghai.gov.cn/en-Parks/20240920/4c47d7f55b3f4a25b043981f4f54434d.html','https://zh.wikipedia.org/wiki/上海世博文化公园']),
 ('00140',60,60,'official_republication','普通成人60；优惠资格和主题体验另计',['https://www.shobserver.cn/sgh/detail?id=1724704']),
 ('00141',0,0,'mixed_reference','东馆常设展免费；付费特展另计，不能套用人民广场馆收费或把所有特展都标免费',['https://www.shanghaimuseum.cn/mu/frontend/pg/service/visit-east','https://ep.shxwcb.com/2026/01/29/img/080129.pdf']),
 ('00142',30,30,'official_reference','成人30；老人、学生及免费资格按官网，特定体验另计',['https://www.snhm.org.cn/cgfw/cgzx.htm']),
 ('00143',30,30,'official_reference','成人参观30；老人25、学生15；球幕电影等另计，免票资格按官方',['https://www.shanghai.gov.cn/pudong/index.html']),
 ('00144',0,0,'official_reference','常设展免费；特展、活动及体验不在本项内。来源较早，出行前复核',['https://www.shanghai.gov.cn/nw9822/20200906/0001-9822_1225204.html']),
 ('00145',0,0,'secondary_reference','当前免费预约参观参考；旧政府介绍仍有30元，官网当前须知未明列价格，须复核，不能采用旧票价',['https://sh.bendibao.com/jingdian/shanghaichengshiguihuazhanshiguan/','https://www.supec.org.cn/employ-index.html?tab=tab1','https://touch.shio.gov.cn/jsp/whjljd_detail.jsp?id=74']),
 ('00146',30,30,'official_reference','普通成人馆票30；2021价格批复，潜艇参观等单独项目另核实',['https://www.shanghai.gov.cn/gwk/search/content/48c1a399c92c44f281afdab6b9c7d56e','https://tt.shmmc.com.cn/SHMM_WeChat/visit?shelfCode=SHMM01']),
 ('00147',0,0,'official_reference','公共区域免费；广富林文化展示馆30（2026报道），其他场馆另计',['https://www.meet-in-shanghai.net/cn/news/the-public-area-of-guangfulin-cultural-site-will-be-open-to-the-public-free-of-charge-from-tomorrow-291420/','https://whlyj.sh.gov.cn/gqfc/20260109/755016cfa16649e3a9e761598b4857f9.html']),
 ('00148',100,150,'official_reference','2025公布成人日场：工作日100、周末法定节假日150；17点后80/120；2026实际展览和票种需复核',['https://whlyj.sh.gov.cn/gqfc/20250515/2c814efbcb234c31a36d94c933e4b5e6.html','https://www.museumofartpd.org.cn/ticketing?id=10']),
 ('00149',20,20,'official_reference','上海故居普通成人20；学生等优惠另计，不能混同北京宋庆龄故居',['https://www.meet-in-shanghai.net/cn/revolutionary-venues/the-former-residence-of-song-qingling-in-shanghai-is-basically-displayed-145303/','https://www.shsoong-chingling.com/list-canguanyuyue.html']),
 ('00150',0,0,'official_reference','博物馆免费；开放日及预约需核实',['https://shanghai.chinapost.com.cn/xhtml1/report/23051/1809-1.htm','https://whlyj.sh.gov.cn/gqfc/20241218/b7a180236c7d47cba6b939a6092ae6c1.html']),
 ('00151',0,0,'mixed_reference','古镇街区免首道门票；内部展馆分别收费，不当作整镇收费',['https://sh.bendibao.com/tour/2023114/265817.shtm','https://whlyj.sh.gov.cn/4ajjq/20201124/0b873aa685d44ddcbb1bd66609e53b0f.html']),
 ('00152',0,0,'secondary_reference','老街公共游览免费；古猗园、檀园等收费项目另核实',['https://sh.bendibao.com/jingdian/nanxianglaojie/']),
 ('00153',0,0,'mixed_reference','古镇街区免费；2025场馆联票参考50，不能套用已结束的半价活动',['https://m.cncn.com/piao/1255','https://whlyj.sh.gov.cn/cmsres/60/60195750731c4871a03be0d896b2c7dc/7fdaf71fb7145466340c367268a7c85f.pdf']),
 ('00154',0,0,'official_reference','古镇公共游览免费；展馆及商业消费另计',['https://www.meet-in-shanghai.net/tc/news/spring-is-coming-to-shanghaiin-this-free-admission-jiangnan-water-townfeel-the-freshness-of-spring-in-one-go-268898/']),
 ('00155',0,0,'secondary_reference','滨江公共绿地参考免费；收费设施另计',['https://you.ctrip.com/sight/shanghai2/2043565.html','https://news.sina.com.cn/o/2012-07-17/062024787721.shtml']),
 ('00156',0,0,'secondary_reference','滨江公共步道参考免费；沿线美术馆、活动另计',['https://you.ctrip.com/sight/shanghai2/1483401.html']),
 ('00157',50,50,'official_reference','成人普通入园50；住宿、水上活动、体验等另计',['https://www.shanghai.gov.cn/nw17239/20250225/0e9088c68a81408394b0a88580677d95.html']),
 ('00158',0,0,'official_republication','东、西佘山公共登山游览免费；天马山、天文博物馆及挖笋体验等不能默认免费',['https://www.shobserver.cn/sgh/detail?id=1724704','https://www.songjiang.gov.cn/xwzx/001001/20260325/13758570-6c3d-4f5e-97c9-37d24cbd5a1b.html']),
 ('00159',80,80,'media_reference','普通成人原价参考80；依据2025报道，2026需复核，不沿用限时60优惠',['https://ep.shxwcb.com/2025/11/27/img/06-071127.pdf','https://whlyj.sh.gov.cn/bmxx/20210514/7692b4249ca5472ba5a5eae918e747ff.html']),
 ('00160',0,0,'secondary_reference','环湖公共游览参考免费；游船、水上活动及附近景区另计',['https://you.ctrip.com/destinationsite/sight/shanghai2/64745-sight.html']),
]

def converted(lo, hi):
    # Outward rounding to ten yuan avoids suggesting precision absent in hotel estimates.
    return [int((Decimal(lo) * FX / 10).to_integral_value(rounding=ROUND_FLOOR)) * 1000,
            int((Decimal(hi) * FX / 10).to_integral_value(rounding=ROUND_CEILING)) * 1000]

def generate():
    anchors = json.loads((ROOT / 'modules/trip_engine/data/anchors.json').read_text(encoding='utf-8'))
    hotel_names = {x['id']: x['name_zh'] for x in anchors['hotels']}
    hotels = []
    for hid, lo, hi, number, slug in hotel_rows:
        url = TA.format(number, slug)
        if hid == 'hotel_ritz_pudong':
            url = url.replace('www.tripadvisor.com', 'cn.tripadvisor.com')
        a, b = converted(lo, hi)
        hotels.append(dict(entity_id=hid, name=hotel_names[hid], currency='CNY', unit='per_room_per_night',
            min_cents=a, max_cents=b, status='ota_reference', retrieved_at=DATE,
            original_price={'currency':'USD','min':lo,'max':hi}, sources=[url],
            scope='Tripadvisor标准客房平均房价范围；没有绑定用户入住日期、房型、早餐、税费及退改政策；人民币为汇率折算并向外取整到10元。不是可预订报价。',
            requires_confirmation=True, auto_fill_eligible=True))
    hotels.insert(0, dict(entity_id='hotel_hyland',name=hotel_names['hotel_hyland'],currency='CNY',
        unit='per_room_per_night',min_cents=None,max_cents=None,status='identity_conflict',retrieved_at=DATE,
        sources=['https://www.swissotel.cn/hotels/shanghai/',TA.format('1021906','Swissotel_Grand_Shanghai'),TA.format('299549','Radisson_Collection_Hotel_Hyland_Shanghai')],
        scope='中文名上海宏安瑞士大酒店指向Swissotel Grand；英文名及南京东路坐标指向Radisson Collection Hyland。须先核对实体，禁止直接匹配价格。',
        candidates=[dict(name='上海宏安瑞士大酒店 / Swissotel Grand Shanghai',original_currency='USD',original_min=118,original_max=195,cny_range_cents=converted(118,195)),
                    dict(name='上海海仑丽笙精选酒店 / Radisson Collection Hyland Shanghai',original_currency='USD',original_min=119,original_max=224,cny_range_cents=converted(119,224))],
        requires_confirmation=True,auto_fill_eligible=False))
    poi_names = {x['poi_id']:x['names']['zh-Hans'] for x in POIS}
    attractions = [dict(entity_id='sh_poi_'+suffix,name=poi_names['sh_poi_'+suffix],currency='CNY',
        unit='per_person_admission',min_cents=None if lo is None else lo*100,max_cents=None if hi is None else hi*100,
        status=tier,scope=scope,sources=urls,retrieved_at=DATE,requires_confirmation=True,auto_fill_eligible=lo is not None)
        for suffix,lo,hi,tier,scope,urls in rows]
    attractions[3]['sources'].append('https://you.ctrip.com/sight/shanghai2/14903.html')
    attractions[3]['scope'] += '；街区免费依据第三方游览资料，官网可核实联票。'
    museum = next(r for r in attractions if r['entity_id'] == 'sh_poi_00088')
    museum['base_price_basis'] = 'user_requested_product_label'
    museum['special_exhibitions'] = [dict(
        name='世界树之巅：美洲古代文明大展', currency='CNY',
        full_price_cents=14800, designated_day_price_cents=13500,
        valid_from='2026-07-09', valid_until='2027-11-14',
        admission_requires_ticket_during_exhibition=True,
        sources=museum['sources'], conditions= museum['scope'])]
    assert {x['entity_id'] for x in hotels} == set(hotel_names)
    assert {x['entity_id'] for x in attractions} == set(poi_names)
    assert len(hotels)==12 and len(attractions)==45
    for row in hotels+attractions:
        assert row['sources'] and all(u.startswith('https://') for u in row['sources'])
        assert (row['min_cents'] is None) == (row['max_cents'] is None)
        if row['min_cents'] is not None:
            assert 0 <= row['min_cents'] <= row['max_cents']
    snapshot = dict(researched_at=DATE,purpose='价格调研快照，用于行程预算自动参考估算；不代表指定日期实时报价',
        pricing_basis='公开可访问资料；部分来源发布于2021—2025年或为游客反馈，查询日期不等于报价日期。官方来源也不代表已核实指定出行日价格。未知保留null。',
        exchange_rate=dict(base='USD',quote='CNY',rate=str(FX),effective_date='2026-09-30',source=FX_URL),
        counts=dict(hotels=len(hotels),attractions=len(attractions)),hotels=hotels,attractions=attractions)
    (ROOT / 'modules/trip_engine/data/price_research_2026-10-06.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out=['# 上海酒店与景点价格调研（2026-10-06）','',
        '覆盖当前主数据中的12家酒店和45个景点。所有记录均保留实体ID、来源、币种、计价单位及适用范围；已接入预算自动参考估算，手填金额优先，未知和实体冲突不自动计入。','',
        '酒店是每间每晚的公开标准客房平均房价范围，不是指定入住日期的报价；早餐、税费、房型、退改条件需复核。按[2026-09-30美元兑人民币中间价](%s)1美元=6.7351元折算，向外取整到10元。酒店费用需按房间数、晚数及实际人数分摊，不能直接作为每人每晚费用。'%FX_URL,'',
        '景点以成人普通入园/参观为基准；公共区域免费不表示内部展馆或体验免费。上海博物馆按用户要求基础标注免费，特展票价另列；这一产品标注不代表当前人民广场馆可免费入馆。部分资料较早或来自第三方/游客，标记为参考并待复核。未查实价格使用“待核实”，不填0；活动已结束的优惠价不作为当前价格。','',
        '重点：宏安瑞士大酒店的中英文实体冲突；环球金融中心没有查实当前观光票；乌中市集未查到明确门票声明；城市规划展示馆旧收费介绍和现有免费参考存在年代差异。','',
        '## 酒店','', '| ID / 酒店 | 人民币参考（元/间/晚） | 原始美元范围 | 范围与来源 |','|---|---:|---:|---|']
    def price(row):
        if row['min_cents'] is None: return '待核实'
        a,b=row['min_cents']//100,row['max_cents']//100
        return str(a) if a==b else f'{a}—{b}'
    def links(row): return ' '.join(f'[来源{i+1}]({u})' for i,u in enumerate(row['sources']))
    for r in hotels:
        dollar=r.get('original_price')
        orig=f"{dollar['min']}—{dollar['max']}" if dollar else '实体冲突'
        out.append(f"| {r['entity_id']} / {r['name']} | {price(r)} | {orig} | {r['scope']} {links(r)} |")
    out += ['', '宏安瑞士大酒店候选参考：Swissotel约790—1320元/间/晚（USD118—195）；海仑丽笙精选候选约800—1510元/间/晚（USD119—224）。这两项仅用于帮助核对，不关联到当前hotel_hyland价格。','',
        '## 景点','', '| ID / 景点 | 成人基础参考（元/人） | 证据类别 | 适用范围与来源 |','|---|---:|---|---|']
    for r in attractions:
        out.append(f"| {r['entity_id']} / {r['name']} | {price(r)} | {r['status']} | {r['scope']} {links(r)} |")
    out += ['', '## 后续预填依据','',
        '- 先修正实体冲突，并区分成人、儿童、老人、学生等票种；有明确有效期的价格按行程日期匹配。',
        '- 酒店按入住/退房日期、房型、间数取得范围或报价；保留来源和报价时间。',
        '- 现有用户手填费用优先；历史参考和第三方参考应标为估算，允许修改。',
        '- 公共区域和付费内部项目分别计费；不因公共区域免费而忽略已选内部项目。',
        '- 有可用基础价格的记录启用auto_fill_eligible，仅用于参考估算；未知和实体冲突为false。豫园按月份选价，特展费用提示另列。','']
    (ROOT / 'docs/research/2026-10-06-shanghai-prices.md').write_text('\n'.join(out),encoding='utf-8')
    print(json.dumps({'hotels':len(hotels),'attractions':len(attractions),'unknown_attractions':[r['entity_id'] for r in attractions if r['min_cents'] is None]},ensure_ascii=True))

if __name__ == '__main__':
    generate()
