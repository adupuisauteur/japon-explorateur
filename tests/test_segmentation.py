"""Évolution 1.3.0 — lot 6 : découpage en segments.

Propriété vérifiée sur des milliers de textes fictifs générés au hasard (graine fixe) : la concaténation
des segments redonne EXACTEMENT le texte d'origine, et aucun segment n'est vide.
"""
import random

from django.test import SimpleTestCase

from apps.translation.segmentation import is_translatable, split_text

POOL = list("あいうえおかきくけこ武士道葉隠死事見付漢字読") + list("。、！？．「」『』（）()\n\r 　\t") + list("AbcXyz.! 123")


class ConcatenationPropertyTests(SimpleTestCase):
    def test_random_texts_are_rebuilt_exactly(self):
        rng = random.Random(20261113)
        for _ in range(3000):
            text = "".join(rng.choice(POOL) for _ in range(rng.randint(0, 120)))
            segments = split_text(text)
            self.assertEqual("".join(segments), text)
            self.assertTrue(all(segments), "aucun segment vide")


class SplittingRulesTests(SimpleTestCase):
    def check(self, text, expected):
        self.assertEqual(split_text(text), expected)

    def test_japanese_sentence_ends(self):
        self.check("武士道と云は死ぬ事と見付たり。二つ二つの場にて！早く？",
                   ["武士道と云は死ぬ事と見付たり。", "二つ二つの場にて！", "早く？"])

    def test_quotations_are_kept_whole(self):
        self.check("彼は「行く。止まる。」と言った。次。", ["彼は「行く。止まる。」と言った。", "次。"])
        self.check("『葉隠』に「毎朝。毎夕。」\n次の段落。", ["『葉隠』に「毎朝。毎夕。」\n", "次の段落。"])

    def test_quotation_closing_a_sentence(self):
        self.check("彼は言った。「行く。」次の文。", ["彼は言った。", "「行く。」", "次の文。"])

    def test_line_breaks_and_blank_lines(self):
        self.check("一行目\n二行目", ["一行目\n", "二行目"])
        self.check("段落。\r\n\r\n次。", ["段落。\r\n\r\n", "次。"])

    def test_unclosed_quote_stops_at_paragraph(self):
        self.check("「閉じない。\n\n次の段落。", ["「閉じない。\n\n", "次の段落。"])

    def test_readings_in_parentheses_stay_in_their_segment(self):
        self.check("漢字（かんじ）の読み。終わり", ["漢字（かんじ）の読み。", "終わり"])

    def test_leading_and_trailing_spaces(self):
        self.check("  前置き。後ろ。  ", ["  前置き。", "後ろ。  "])
        self.check("\n\n", ["\n\n"])
        self.check("", [])

    def test_english_abbreviations(self):
        self.check("Written c. 1716. The text ends. vol. 2 here", ["Written c. 1716. ", "The text ends. vol. 2 here"])

    def test_translatable(self):
        self.assertTrue(is_translatable("文。"))
        self.assertFalse(is_translatable("。」\n"))
        self.assertFalse(is_translatable("  　"))
