import common  # noqa: F401
import unittest

from ask_cards import ASK_CARD_NODES, ASK_CARD_TEMPLATES, card, render, transfer_card
import json
from pathlib import Path


class AskCardTests(unittest.TestCase):
    def test_five_node_types_available(self):
        self.assertEqual(set(ASK_CARD_NODES), {"station_entrance", "transfer", "station_exit",
                                               "drop_off", "poi_arrival"})

    def test_station_entrance_renders(self):
        c = card("station_entrance", {"access_name_zh": "2号口", "access_name_en": "Entrance 2"})
        self.assertEqual(c["template_key"], "station_entrance")
        self.assertIn("2号口", render(c, "zh"))

    def test_transfer_direction_fallback(self):
        c = transfer_card(line_name_zh="2 号线", line_name_en="Line 2", direction_present=False)
        self.assertEqual(c["template_key"], "direction_fallback")
        self.assertIn("2 号线", render(c, "zh"))

    def test_transfer_with_direction(self):
        c = transfer_card(line_name_zh="2 号线", line_name_en="Line 2", direction_present=True)
        self.assertEqual(c["template_key"], "transfer")

    def test_japanese_and_korean_match_the_contract(self):
        mappings = json.loads((Path(__file__).resolve().parents[3] / 'contracts/mappings.json').read_text(encoding='utf-8'))
        for key, templates in ASK_CARD_TEMPLATES.items():
            self.assertEqual(set(templates), {'zh','en','ja','ko'})
            self.assertEqual(templates, {k:v for k,v in mappings['ask_card_templates'][key].items() if k != 'note'})
        c = card('poi_arrival', {'poi_name_zh':'外滩','poi_name_en':'The Bund'})
        self.assertIn('すみません', render(c,'ja'))
        self.assertIn('실례합니다', render(c,'ko'))


if __name__ == "__main__":
    unittest.main()
