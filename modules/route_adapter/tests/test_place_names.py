import common  # noqa: F401
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from place_names import english_place_name, place_name_en, place_reference, translate_place_tokens
from normalize import parse_amap_access_name


class PlaceNameTests(unittest.TestCase):
    def test_intersections_annotations_and_published_spelling(self):
        self.assertEqual(place_name_en('建国中路瑞金二路'), 'Middle Jianguo Road / Ruijin Road Number Two')
        self.assertEqual(place_name_en('上海动物园(虹井路)'), 'Shanghai Zoo (Hongjing Road)')
        self.assertEqual(place_name_en('纪翟路保乐路'), 'Jidi Road / Baole Road')

    def test_known_name_is_not_substituted_inside_an_unknown_name(self):
        self.assertIsNone(place_name_en('未知上海图书馆商场'))
        self.assertEqual(translate_place_tokens('Towards 未知上海图书馆商场'), 'Towards 未知上海图书馆商场')
        for empty in (None, '', [], {}, 42):
            self.assertIsNone(place_name_en(empty))

    def test_existing_english_is_preserved_but_duplicate_chinese_is_repaired(self):
        self.assertEqual(english_place_name('静安寺', 'Verified custom spelling'), 'Verified custom spelling')
        self.assertEqual(english_place_name('静安寺', '静安寺'), "Jing'an Temple")
        self.assertEqual(place_name_en("浦东国际机场 T2 / Pudong Int'l Airport T2"), "Pudong Int'l Airport T2")

    def test_directional_access_names_translate_without_inventing_a_number(self):
        self.assertEqual(parse_amap_access_name('南出入口'), (None, 'South entrance / exit'))
        self.assertEqual(parse_amap_access_name('东南出口', 'exit'), (None, 'Southeast exit'))
        self.assertEqual(parse_amap_access_name('东口'), (None, 'East entrance'))

    def test_catalog_has_sources_and_distinguishes_derived_labels(self):
        catalog = json.loads((Path(__file__).resolve().parents[1]/'data/curated_place_names.json').read_text(encoding='utf-8'))
        for row in catalog['places'].values():
            self.assertIn(row['source'], catalog['sources'])
            self.assertTrue(catalog['sources'][row['source']]['url'].startswith('https://'))
        self.assertEqual(catalog['places']['虹桥2号航站楼']['kind'], 'official_english')
        self.assertEqual(catalog['places']['隧道夜宵线']['kind'], 'pinyin_display')

    def test_missing_files_degrade_without_network_or_fabricated_names(self):
        place_reference.cache_clear()
        try:
            with patch.object(Path, 'read_text', side_effect=OSError('missing')):
                self.assertEqual(place_reference(), {})
                self.assertIsNone(place_name_en('未核录车站'))
        finally:
            place_reference.cache_clear()
