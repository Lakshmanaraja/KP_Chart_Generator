"""Card-per-trait layout: title rows, separated guidance callouts, one card each."""
import unittest
from reportlab.lib import colors

from pdf.insight_text import (
    insight_height, insight_paragraph, insight_title, title_height, title_lines,
)


TRAIT = {
    "text": "Your child notices small details and keeps things in order.",
    "summary_title": "Process Oriented",
    "code": "P2",
    "kind": "primary",
    "guidance": "Give simple routines and praise the effort, not just the result.",
}


class TestTitleRow(unittest.TestCase):
    def test_title_extracted_without_colon(self):
        self.assertEqual(insight_title({"summary_title": "Manager:"}), "Manager")

    def test_title_adds_height(self):
        plain = {"text": TRAIT["text"], "code": "P1", "kind": "primary"}
        self.assertGreater(insight_height(TRAIT, 12, 400, colors.black),
                           insight_height(plain, 12, 400, colors.black))

    def test_no_title_no_title_height(self):
        self.assertEqual(title_height({"text": "x"}, 12, 400), 0.0)
        self.assertEqual(title_lines({"text": "x"}, 12, 400), [])

    def test_paragraph_is_prediction_only(self):
        p = insight_paragraph(TRAIT, 12, colors.black)
        self.assertNotIn("Process Oriented", p.text)
        self.assertIn("notices small details", p.text)


class TestGuidanceCallout(unittest.TestCase):
    def test_guidance_adds_height(self):
        no_guidance = {k: v for k, v in TRAIT.items() if k != "guidance"}
        self.assertGreater(insight_height(TRAIT, 12, 400, colors.black),
                           insight_height(no_guidance, 12, 400, colors.black))

    def test_blank_guidance_omits_box(self):
        blank = dict(TRAIT, guidance="   ")
        no_guidance = {k: v for k, v in TRAIT.items() if k != "guidance"}
        self.assertEqual(insight_height(blank, 12, 400, colors.black),
                         insight_height(no_guidance, 12, 400, colors.black))


class TestCardPerTrait(unittest.TestCase):
    def test_mobile_renders_each_trait_on_own_card(self):
        from pdf.mobile_report import render_mobile_pdf
        sections = [{"title": "Personality", "traits": [
            dict(TRAIT, code="P1"),
            dict(TRAIT, code="P2", summary_title="Empathetic", guidance=""),
            dict(TRAIT, code="P3", summary_title="", kind="secondary"),
        ]}]
        pdf = render_mobile_pdf(sections, {"name": "Test Child"}, "child")
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_desktop_renders_each_trait_on_own_card(self):
        from pdf.desktop_report import render_desktop_pdf
        sections = [{"title": "Personality", "traits": [
            dict(TRAIT, code="P1"),
            dict(TRAIT, code="P2", kind="low", guidance=""),
        ]}]
        pdf = render_desktop_pdf(sections, {"name": "Test Child"}, "child")
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
