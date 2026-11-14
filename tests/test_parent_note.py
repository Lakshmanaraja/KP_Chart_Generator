import unittest
from unittest.mock import patch

from pdf.mobile_report import PARENT_NOTE_BODY, PARENT_NOTE_TITLE, render_mobile_pdf


EXPECTED_BODY = (
    "Time Science does not encourage forcing a child to conform to any set of values—including "
    "those described in this report. Its purpose is not to replace one kind of pressure with another, "
    "but to help parents better understand their child and reduce the distress that can arise from "
    "social trends, outside expectations, or differences between parent and child. The report is "
    "intended to support understanding, not dictate who a child should be."
)


class ParentNote(unittest.TestCase):
    def test_exact_closing_copy(self):
        self.assertEqual(PARENT_NOTE_TITLE, "A Note to Parents")
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
