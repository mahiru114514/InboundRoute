"""高德文本归一化的纯函数测试：线路身份、行车方向、出入口编号、步行指引翻译。

这些断言直接对应两个用户可见缺陷：
  1. 导出 HTML 里出现 `Line 900000160000`（三方主键被当成线路号）；
  2. 英文包里线路名、出入口、步行指引全是中文。
"""
import unittest

import common  # noqa: F401
from normalize import (build_amap_direction, clean_text, derive_line_code,
                       derive_line_name_en, normalize_amap_transit_line,
                       parse_amap_access_name, split_amap_line_name,
                       translate_amap_instruction, translate_amap_instructions)

RAIL_REFERENCE = {"市域机场线": "Airport Link Line", "机场联络线": "Airport Link Line",
                  "磁浮线": "Maglev Line"}

# route.schema.json 对 line/direction 的约束：additionalProperties=false，字段都是非空字符串。
LINE_FIELDS = {"code", "name_en", "name_zh", "color_hex"}
DIRECTION_FIELDS = {"name_en", "name_zh", "terminal_station_id"}


class LineIdentityTests(unittest.TestCase):
    def test_intermediate_metro_stop_keeps_translated_terminal_pair(self):
        raw = '地铁2号线(蟠祥路·国家会计学院--浦东1号2号航站楼)'
        line, direction = normalize_amap_transit_line(raw, alight_name='陆家嘴')
        self.assertEqual(line['name_zh'], raw)
        self.assertEqual(line['name_en'],
                         'Line 2 (Panxiang Road · Shanghai National Accounting Institute — Pudong Airport Terminal 1 & 2)')
        self.assertIsNone(direction)

    def test_bus_terminal_pair_is_translated_in_both_orders(self):
        for zh, en in [
            ('889路(尚泰路乐高路--泸定路同普路)',
             'Bus 889 (Shangtai Road / Legao Road — Luding Road / Tongpu Road)'),
            ('889路(泸定路同普路--尚泰路乐高路)',
             'Bus 889 (Luding Road / Tongpu Road — Shangtai Road / Legao Road)'),
        ]:
            with self.subTest(zh=zh):
                line, direction = normalize_amap_transit_line(zh, alight_name='天山西路福泉路')
                self.assertEqual(line['name_en'], en)
                self.assertIsNone(direction)

    def test_loop_and_nested_terminal_annotations_are_preserved_in_english(self):
        cases = {
            '189路(莘庄地铁站(北广场)--纪王)':
                'Bus 189 (Xinzhuang Metro Station (North Square) — Jiwang)',
            '陆家嘴金融城1路(环线)(东昌路渡口--东昌路渡口)':
                'Bus 1 (Loop) (Dongchang Road Ferry Crossing — Dongchang Road Ferry Crossing)',
        }
        for zh, en in cases.items():
            with self.subTest(zh=zh):
                line, direction = normalize_amap_transit_line(zh, alight_name='陆家嘴')
                self.assertEqual(line['name_en'], en)
                self.assertEqual(line['name_zh'], zh)
                self.assertIsNone(direction)

    def test_unknown_terminal_is_retained_without_guessing_its_translation(self):
        line, direction = normalize_amap_transit_line('2号线(未知站--浦东1号2号航站楼)', alight_name='陆家嘴')
        self.assertEqual(line['name_zh'], '2号线(未知站--浦东1号2号航站楼)')
        self.assertEqual(line['name_en'], 'Line 2 (未知站 — Pudong Airport Terminal 1 & 2)')
        self.assertIsNone(direction)

    def test_airport_direction_translates_the_terminal_name(self):
        direction = build_amap_direction(
            "市域机场线(浦东1号2号航站楼--虹桥2号航站楼)", "虹桥2号航站楼")
        self.assertEqual(direction["name_en"], "Towards Hongqiao Airport Terminal 2")

    def test_walking_translates_known_roads_and_intersection_names(self):
        self.assertEqual(
            translate_amap_instruction("沿北青公路辅路步行384米左转"),
            "Walk 384 m along Beiqing Highway service road, turn left")
        self.assertEqual(
            translate_amap_instruction("步行252米到达北青公路繁兴路"),
            "Walk 252 m to reach Beiqing Highway / Fanxing Road")
        self.assertEqual(
            translate_amap_instruction("步行44米到达浦东1号2号航站楼"),
            "Walk 44 m to reach Pudong Airport Terminal 1 & 2")

    def assert_contract_shape(self, line, direction):
        if line is not None:
            self.assertLessEqual(set(line), LINE_FIELDS)
            for key, value in line.items():
                self.assertIsInstance(value, str, key)
                self.assertTrue(value.strip(), key)
        if direction is not None:
            self.assertLessEqual(set(direction), DIRECTION_FIELDS)
            for key, value in direction.items():
                if value is not None:
                    self.assertTrue(isinstance(value, str) and value.strip(), key)

    def test_named_rail_line_uses_official_english_and_drops_parens(self):
        line, direction = normalize_amap_transit_line(
            "市域机场线(浦东1号2号航站楼--虹桥2号航站楼)",
            alight_name="虹桥2号航站楼", rail_reference=RAIL_REFERENCE)
        self.assertEqual(line, {"name_zh": "市域机场线", "name_en": "Airport Link Line"})
        self.assertEqual(direction, {"name_zh": "往虹桥2号航站楼方向",
                                     "name_en": "Towards Hongqiao Airport Terminal 2"})
        self.assert_contract_shape(line, direction)

    def test_direction_follows_the_alight_station_not_the_parens_order(self):
        # 反向乘坐时方向必须跟着下车站走，不能照抄括号里的第一个终点。
        _, direction = normalize_amap_transit_line(
            "市域机场线(浦东1号2号航站楼--虹桥2号航站楼)",
            alight_name="浦东1号2号航站楼", rail_reference=RAIL_REFERENCE)
        self.assertEqual(direction["name_zh"], "往浦东1号2号航站楼方向")

    def test_numbered_lines_get_language_neutral_code_and_english(self):
        line, direction = normalize_amap_transit_line("地铁2号线")
        self.assertEqual(line, {"code": "2", "name_en": "Line 2", "name_zh": "地铁2号线"})
        self.assertIsNone(direction)
        self.assert_contract_shape(line, direction)

    def test_bus_keeps_full_name_when_direction_cannot_be_proven(self):
        # 下车站与括号里的两个终点都不吻合：不猜方向，保留原始名（含起讫点）不丢信息。
        line, direction = normalize_amap_transit_line(
            "闵行18路(合川路虹泉路--金辉路保乐路)", alight_name="虹桥东交通中心")
        self.assertIsNone(direction)
        self.assertEqual(line["code"], "18")
        self.assertEqual(line["name_en"], "Bus 18 (Hechuan Road / Hongquan Road — Jinhui Road / Baole Road)")
        self.assertEqual(line["name_zh"], "闵行18路(合川路虹泉路--金辉路保乐路)")

    def test_bus_direction_is_kept_when_the_alight_station_is_a_terminus(self):
        line, direction = normalize_amap_transit_line(
            "闵行18路(合川路虹泉路--金辉路保乐路)", alight_name="金辉路保乐路")
        self.assertEqual(line["name_zh"], "闵行18路")
        self.assertEqual(direction["name_zh"], "往金辉路保乐路方向")

    def test_unknown_named_line_stays_chinese_without_inventing_english(self):
        line, direction = normalize_amap_transit_line("某某专线")
        self.assertEqual(line, {"name_zh": "某某专线"})
        self.assertIsNone(direction)
        self.assertIsNone(line.get("name_en"))

    def test_provider_id_is_never_returned_as_a_line_code(self):
        for raw in ("市域机场线", "900000160000", "310100017532"):
            with self.subTest(raw=raw):
                line, _ = normalize_amap_transit_line(raw)
                self.assertNotEqual(line.get("code"), "900000160000")
                self.assertNotEqual(line.get("code"), "310100017532")

    def test_empty_and_placeholder_inputs_yield_nothing(self):
        for raw in (None, "", "   ", [], {}, 0):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_amap_transit_line(raw), (None, None))
                self.assertIsNone(clean_text(raw))
                self.assertIsNone(derive_line_code(raw))
                self.assertIsNone(derive_line_name_en(raw, RAIL_REFERENCE))
                self.assertIsNone(build_amap_direction(raw, "虹桥2号航站楼"))

    def test_direction_is_not_guessed_when_both_or_neither_terminal_matches(self):
        name = "某某线(甲站--乙站)"
        self.assertIsNone(build_amap_direction(name, "丙站"))
        self.assertIsNone(build_amap_direction(name, "甲站乙站"))
        self.assertEqual(build_amap_direction(name, "甲站")["name_zh"], "往甲站方向")
        self.assertEqual(build_amap_direction(name, "乙站")["name_zh"], "往乙站方向")

    def test_split_handles_missing_parens_and_full_width_forms(self):
        self.assertEqual(split_amap_line_name("2号线"), ("2号线", None))
        self.assertEqual(split_amap_line_name("市域机场线（A--B）"), ("市域机场线", "A--B"))
        self.assertEqual(split_amap_line_name(None), (None, None))


class AccessPointTests(unittest.TestCase):
    def test_numbered_access_names_gain_number_and_english(self):
        self.assertEqual(parse_amap_access_name("2号口", "exit"), ("2", "Exit 2"))
        self.assertEqual(parse_amap_access_name("2号口", "entrance"), ("2", "Entrance 2"))
        self.assertEqual(parse_amap_access_name("11号出入口", "exit"), ("11", "Exit 11"))
        self.assertEqual(parse_amap_access_name("Exit 3", "exit"), ("3", "Exit 3"))

    def test_station_like_or_landmark_names_are_not_treated_as_access_points(self):
        for name in ("浦东1号2号航站楼", "南京东路步行街方向", "虹桥2号航站楼", "", None, [], 7):
            with self.subTest(name=name):
                self.assertEqual(parse_amap_access_name(name, "exit"), (None, None))


class WalkInstructionTests(unittest.TestCase):
    def test_full_current_trip_instruction_shapes(self):
        cases = {
            '沿银城中路辅路向东步行84米向右前方行走':
                'Walk 84 m east along Middle Yincheng Road service road, bear right and continue',
            '向东南步行14米到达目的地': 'Walk 14 m southeast, arrive at your destination',
            '步行212米向左前方直行下过街天桥':
                'Walk 212 m, bear left and continue and go down the pedestrian overpass',
            '沿丰和路步行228米靠右进入右转专用道':
                'Walk 228 m along Fenghe Road, keep right and enter the right-turn lane',
            '沿花园石桥路步行257米左转进入辅路':
                'Walk 257 m along Huayuanshiqiao Road, turn left and enter the service road',
            '沿南京路步行街步行249米左转':
                'Walk 249 m along Nanjing Road pedestrian street, turn left',
        }
        for zh, en in cases.items():
            with self.subTest(zh=zh):
                self.assertEqual(translate_amap_instruction(zh), en)

    def test_distance_and_action_templates(self):
        cases = {
            "步行24米右转": "Walk 24 m, turn right",
            "步行8米左转": "Walk 8 m, turn left",
            "步行36米直行": "Walk 36 m, continue straight",
            "步行11米右转上阶梯": "Walk 11 m, turn right and take the stairs up",
            "步行13米左转出阶梯": "Walk 13 m, turn left and exit the stairs",
            "步行93米向右后方直行": "Walk 93 m, bear back-right and continue",
            "步行43米向右前方直行": "Walk 43 m, bear right and continue",
            "步行3米到达虹桥东交通中心": "Walk 3 m to reach Hongqiao East Transportation Center",
            "步行9米到达目的地": "Walk 9 m to arrive at your destination",
            "沿浦东机场路步行382米向左前方直行": "Walk 382 m along Pudong Jichang Road, bear left and continue",
            "沿北青公路辅路步行384米到达目的地": "Walk 384 m along Beiqing Highway service road to arrive at your destination",
            "靠右": "keep right",
            "向右后方直行": "bear back-right and continue",
        }
        for chinese, english in cases.items():
            with self.subTest(chinese=chinese):
                self.assertEqual(translate_amap_instruction(chinese), english)

    def test_real_corpus_clauses_that_used_to_be_unmatched(self):
        # 这几条来自实际导出的离线包：以前整段翻不出来，导致整条指引只剩中文。
        cases = {
            "步行98米": "Walk 98 m",
            "步行22米左转进入右侧道路": "Walk 22 m, turn left and enter the road on the right",
            "步行24米左转进入匝道": "Walk 24 m, turn left and enter the ramp",
            "步行35米左转到达目的地": "Walk 35 m, turn left and arrive at your destination",
            "沿七莘路辅路步行55米到达七宝": "Walk 55 m along Qixin Road service road to reach Qibao",
            "沿纪翟路步行57米到达纪翟路保乐路": "Walk 57 m along Jidi Road to reach Jidi Road / Baole Road",
        }
        for chinese, english in cases.items():
            with self.subTest(chinese=chinese):
                self.assertEqual(translate_amap_instruction(chinese), english)

    def test_unknown_sentences_are_left_alone_instead_of_guessed(self):
        for chinese in ("穿过广场后询问工作人员", "沿道路步行", "", None, 5, []):
            with self.subTest(chinese=chinese):
                self.assertIsNone(translate_amap_instruction(chinese))

    def test_unknown_piece_keeps_the_rest_in_english(self):
        # 一个片段不认识不再拖垮整条指引：能翻的翻，翻不出的原样保留（不猜义）。
        self.assertEqual(
            translate_amap_instructions(["步行24米右转", "步行8米左转"]),
            "Walk 24 m, turn right; Walk 8 m, turn left")
        self.assertEqual(
            translate_amap_instructions(["步行24米右转", "穿过广场后询问工作人员"]),
            "Walk 24 m, turn right; 穿过广场后询问工作人员")
        self.assertIsNone(translate_amap_instructions([]))
        self.assertIsNone(translate_amap_instructions([None, {}]))
        self.assertIsNone(translate_amap_instructions(["完全陌生的一句话"]))

    def test_full_real_world_note_from_the_offline_html(self):
        instructions = [
            "沿浦东机场路步行382米向左前方直行",
            "沿浦东机场路步行89米靠右",
            "步行24米右转",
            "步行9米到达目的地",
            "步行44米到达浦东1号2号航站楼",
        ]
        translated = translate_amap_instructions(instructions)
        self.assertEqual(translated,
                         "Walk 382 m along Pudong Jichang Road, bear left and continue; "
                         "Walk 89 m along Pudong Jichang Road, keep right; "
                         "Walk 24 m, turn right; "
                         "Walk 9 m to arrive at your destination; "
                         "Walk 44 m to reach Pudong Airport Terminal 1 & 2")

    def test_every_clause_of_the_real_exported_notes_is_covered(self):
        # 实际离线包里三条最长指引的全文：改造后应当每个片段都有英文。
        notes = [
            "沿浦东机场路步行382米向左前方直行；沿浦东机场路步行89米靠右；沿浦东机场路步行154米右转；"
            "步行24米右转；步行408米右转；步行9米到达目的地；步行9米右转；步行185米向右前方直行；"
            "步行8米左转；步行44米到达浦东1号2号航站楼",
            "步行93米向右后方直行；步行8米左转；步行320米左转；步行12米到达目的地；步行12米左转；"
            "步行22米左转进入右侧道路；步行43米向右前方直行；步行3米到达虹桥东交通中心",
            "沿纪翟路步行1米右转；步行11米右转上阶梯；步行13米左转出阶梯；步行36米直行；步行261米左转；"
            "沿繁兴路步行295米右转；沿北青公路辅路步行384米到达目的地",
        ]
        for note in notes:
            with self.subTest(note=note[:20]):
                translated = translate_amap_instructions(note.split("；"))
                self.assertIsNotNone(translated)
                self.assertEqual(translated.count(";"), note.count("；"))
                for clause in translated.split("; "):
                    self.assertFalse(any("\u4e00" <= ch <= "\u9fff" for ch in clause.split(" ")[0]),
                                     "片段开头仍是中文，说明没翻出来：" + clause)


if __name__ == "__main__":
    unittest.main()
