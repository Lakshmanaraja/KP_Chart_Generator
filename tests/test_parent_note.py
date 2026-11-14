import unittest
from unittest.mock import patch

from pdf.mobile_report import PARENT_NOTE_BODY, PARENT_NOTE_LEAD, PARENT_NOTE_TITLE, render_mobile_pdf


EXPECTED_LEAD = "This report is built to support understanding, not dictate who your child should be."
EXPECTED_BODY = (
    "Our goal is not to enforce pressure, but to help you better understand your child and reduce "
    "distress from social trends, outside expectations, or differences."
)


class ParentNote(unittest.TestCase):
    def test_exact_closing_copy(self):
        self.assertEqual(PARENT_NOTE_TITLE, "A Note to Parents")
        self.assertEqual(PARENT_NOTE_LEAD, EXPECTED_LEAD)
        self.assertEqual(PARENT_NOTE_BODY, EXPECTED_BODY)

    @patch("pdf.mobile_report._parents_note")
    def test_only_mobile_child_reports_receive_the_note(self, note):
        client = {"name": "Test Child"}
        render_mobile_pdf([], client, "child")
        note.assert_called_once()

        note.reset_mock()
        render_mobile_pdf([], client, "report")
        note.assert_not_called()


if __name__ == "__main__":
    unittest.main()
