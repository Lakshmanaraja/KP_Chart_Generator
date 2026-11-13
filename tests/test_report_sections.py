import unittest
from unittest.mock import patch
from services.ranker_service import build_report, report_section


class ReportSections(unittest.TestCase):
    def render(self, mappings, source="report", topics=None):
        with patch("services.ranker_service.chart_mapping_matches", return_value={m["tag"]: ["PL"] for m in mappings}):
            return build_report({}, mappings, topics=topics, text_source=source)

    def mapping(self, **overrides):
        return {"tag": "Routine", "section": "Original hierarchy", "report_section": "New Report Heading",
                "pairs": [], "report_text": "Adult insight", "child_report_text": "Child insight", **overrides}

    def test_both_sources_use_report_section_only(self):
        for source in ("report", "child"):
            self.assertEqual(self.render([self.mapping()], source)[0]["title"], "New Report Heading")

    def test_blank_does_not_fall_back_to_hierarchy(self):
        for blank in (None, "", " "):
            self.assertEqual(report_section(self.mapping(report_section=blank)), "Others")

    def test_selection_uses_report_section(self):
        self.assertEqual(len(self.render([self.mapping()], topics=["New Report Heading"])), 1)
        self.assertEqual(self.render([self.mapping()], topics=["Original hierarchy"]), [])

    def test_same_report_heading_groups_different_hierarchy_sections(self):
        result = self.render([self.mapping(), self.mapping(tag="Other", section="Another hierarchy", report_text="Different insight")])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["traits"]), 2)


if __name__ == "__main__":
    unittest.main()