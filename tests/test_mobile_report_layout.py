import io
import unittest
from pathlib import Path

from pypdf import PdfReader
from pdf.mobile_report import render_mobile_pdf
from pdf.topic_headers import TOPICS, topic_inset


class MobileReportLayout(unittest.TestCase):
    def test_requested_section_aliases_have_existing_icons(self):
        icon_dir = Path(__file__).parents[1] / "pdf" / "topic_icons"
        for title in ("Speaking", "Wellness", "Places and Things", "Social Circle"):
            self.assertGreater(topic_inset(title), 0)
            self.assertTrue((icon_dir / f"{TOPICS[title.lower()]}.png").is_file(), title)

    def test_each_report_section_starts_on_a_new_page(self):
        titles = ("Speaking", "Wellness", "Places and Things", "Social Circle")
        sections = [{
            "title": title,
            "traits": [{"kind": "primary", "code": f"T{i + 1}", "text": f"{title} insight for the child."}],
        } for i, title in enumerate(titles)]
        pdf = render_mobile_pdf(sections, {"name": "Test Child"})
        pages = PdfReader(io.BytesIO(pdf)).pages
        title_pages = [next(i + 1 for i, page in enumerate(pages) if title in (page.extract_text() or ""))
                       for title in titles]
        self.assertEqual(title_pages, [3, 4, 5, 6])

    def test_redesigned_closing_copy_is_on_the_final_child_page(self):
        pdf = render_mobile_pdf([], {"name": "Test Child"}, "child")
        final_text = PdfReader(io.BytesIO(pdf)).pages[-1].extract_text() or ""
        normalized_text = " ".join(final_text.split()).replace(" .", ".")
        for expected in (
            "Primary + other category traits",
            "Your child will show the Primary trait most often.",
            "Other traits appear in specific situations and may change over time.",
            "Both traits appear as Primary",
            "Uncommon",
            "Both behaviors are strong.",
            "difficult to predict",
            "This report is built to support understanding, not dictate who your child should be.",
            "Our goal is not to enforce pressure, but to help you better understand your child and reduce distress from social trends, outside expectations, or differences.",
        ):
            self.assertIn(expected, normalized_text)


if __name__ == "__main__":
    unittest.main()
