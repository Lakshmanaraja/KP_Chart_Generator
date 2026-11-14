import unittest
from unittest.mock import patch

from models.schemas import ReportRequest
from services.pronoun_service import personalize_pronouns
from services.ranker_service import build_report
from services.report_service import _sections


class PronounReplacement(unittest.TestCase):
    def test_male_pairs(self):
        source = "He or she is calm. His or her focus grows. Ask him or her. He/she trusts himself or herself."
        self.assertEqual(
            personalize_pronouns(source, "male"),
            "He is calm. His focus grows. Ask him. He trusts himself.",
        )

    def test_female_pairs_and_reverse_order(self):
        source = "She or he is calm. Her or his focus grows. Ask her or him. She/he trusts herself or himself."
        self.assertEqual(
            personalize_pronouns(source, "girl"),
            "She is calm. Her focus grows. Ask her. She trusts herself.",
        )

    def test_neutral_pairs_and_verb_agreement(self):
        source = "He or she is calm and has patience. His or her ideas are his or hers. Ask him or her to trust himself or herself."
        self.assertEqual(
            personalize_pronouns(source, None),
            "They are calm and have patience. Their ideas are theirs. Ask them to trust themselves.",
        )
        self.assertEqual(personalize_pronouns("He/she needs space.", "unknown"), "They need space.")

    def test_uppercase_and_standalone_pronouns(self):
        self.assertEqual(personalize_pronouns("HE OR SHE IS CALM.", "female"), "SHE IS CALM.")
        self.assertEqual(personalize_pronouns("His father helps him.", "female"), "His father helps him.")

    def test_report_builder_uses_gender_for_json_and_both_pdf_renderers(self):
        mapping = {
            "tag": "Calm", "display_name": "Calm", "section": "Personality",
            "report_section": "Personality", "pairs": [], "summary_title": "Calm",
            "report_text": "He or she is calm.", "child_report_text": "He or she is calm.",
        }
        with patch("services.ranker_service.chart_mapping_matches", return_value={"Calm": ["PL"]}):
            sections = build_report({}, [mapping], text_source="child", gender="female")
        self.assertEqual(sections[0]["traits"][0]["text"], "She is calm.")

    @patch("services.report_service.build_report", return_value=[])
    @patch("services.report_service.load_mappings", return_value=[])
    @patch("services.report_service.compute_kp_json", return_value={"planets": []})
    def test_request_gender_reaches_report_builder(self, _chart, _mappings, builder):
        request = ReportRequest(
            name="Test Child", date_of_birth="2020-01-02", time_of_birth="10:20:30",
            latitude=13.0827, longitude=80.2707, gender="female",
        )
        _sections(request)
        self.assertEqual(builder.call_args.kwargs["gender"], "female")


if __name__ == "__main__":
    unittest.main()
