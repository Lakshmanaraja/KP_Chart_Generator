import unittest
from unittest.mock import patch
from services.ranker_service import build_report


class SummaryTitles(unittest.TestCase):
    def mapping(self, **overrides):
        return {"tag": "Routine", "display_name": "Structure & Routine", "section": "Personality", "report_section": "Personality",
                "pairs": [], "report_text": "Adult insight", "child_report_text": "Child insight",
                "summary_title": "Structure & Routine", **overrides}

    def report(self, mappings, source="report"):
        with patch("services.ranker_service.chart_mapping_matches", return_value={m["tag"]: ["PL"] for m in mappings}):
            return build_report({}, mappings, text_source=source)

    def test_shared_title_for_both_sources(self):
        for source, expected in [("child", "Child insight"), ("report", "Adult insight")]:
            trait = self.report([self.mapping()], source)[0]["traits"][0]
            self.assertEqual(trait["summary_title"], "Structure & Routine")
            self.assertEqual(trait["text"], expected)
            self.assertEqual(trait["code"], "P1")

    def test_blank_title_falls_back_to_short_display_name(self):
        trait = self.report([self.mapping(summary_title=None, display_name="Structure and Routine extended")])[0]["traits"][0]
        self.assertEqual(trait["summary_title"], "Structure and Routine")

    def test_body_deduplication_ignores_different_titles(self):
        sections = self.report([self.mapping(), self.mapping(tag="Other", summary_title="Other Title")])
        self.assertEqual(len(sections[0]["traits"]), 1)


if __name__ == "__main__":
    unittest.main()