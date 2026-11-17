import unittest
from services.ranker_service import build_report, resolve_report_type
from pdf.insight_text import insight_paragraph
from reportlab.lib import colors

ROWS = [
    {"tag": "T1", "display_name": "T1", "pairs": [], "report_type": "character_assessment", "report_text": "Adult text", "report_section": "Personality"},
    {"tag": "T1", "display_name": "T1", "pairs": [], "report_type": "understanding_child", "report_text": "Child text", "guidance": "Be patient", "report_section": "Personality"},
]

class ReportContentTests(unittest.TestCase):
    def run_for(self, **kw):
        return build_report({}, ROWS, extra_tags=["T1"], **kw)

    def test_child_source_uses_child_report_content(self):
        t = self.run_for(text_source="child")[0]["traits"][0]
        self.assertEqual((t["text"], t["guidance"]), ("Child text", "Be patient"))

    def test_default_uses_character_assessment(self):
        self.assertEqual(self.run_for()[0]["traits"][0]["text"], "Adult text")

    def test_explicit_report_type_wins(self):
        self.assertEqual(resolve_report_type("report", "marriage_prospect"), "marriage_prospect")
        self.assertEqual(self.run_for(report_type="marriage_prospect"), [])

    def test_guidance_is_printed(self):
        p = insight_paragraph({"text": "x", "guidance": "Be patient"}, 10, colors.black)
        self.assertIn("Guidance:", p.text)

if __name__ == "__main__":
    unittest.main()
