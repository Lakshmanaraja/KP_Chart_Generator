import io
import unittest
from pypdf import PdfReader
from pdf.trait_pagination import card_pages
from pdf.mobile_report import render_mobile_pdf
from pdf.desktop_report import render_desktop_pdf


class TraitPagination(unittest.TestCase):
    def test_three_cards_no_fourth_and_full_height(self):
        pages = list(card_pages(list(range(7)), 600, lambda t, pt: 100, gap=12))
        self.assertEqual([len(p[0]) for p in pages], [3, 3, 1])
        self.assertAlmostEqual(sum(pages[0][2]) + 24, 600)

    def test_opening_reserves_header_space_and_two_cards(self):
        pages = list(card_pages(list(range(8)), 600, lambda t, pt: 100, gap=12, first_available=480))
        self.assertEqual([len(p[0]) for p in pages], [2, 3, 3])
        self.assertAlmostEqual(sum(pages[0][2]) + 12, 480)

    def test_single_trait_section_does_not_invent_a_second_card(self):
        pages = list(card_pages([1], 600, lambda t, pt: 100, first_available=480))
        self.assertEqual(len(pages[0][0]), 1)

    def test_long_content_uses_readable_fallback(self):
        pages = list(card_pages(list(range(3)), 500, lambda t, pt: 220, min_pt=10))
        self.assertEqual([len(p[0]) for p in pages], [2, 1])
        self.assertGreaterEqual(pages[0][1], 10)

    def test_both_formats_open_with_two_then_three_cards(self):
        traits = [{"summary_title": "Careful Observer", "text": "Your child notices details and enjoys simple routines.",
                   "guidance": "Offer a calm routine and praise steady effort." if i % 2 == 0 else "",
                   "kind": "primary", "code": f"P{i+1}"} for i in range(7)]
        for render in (render_mobile_pdf, render_desktop_pdf):
            pdf = render([{"title": "Personality", "traits": traits}], {"name": "Aarav"})
            pages = PdfReader(io.BytesIO(pdf)).pages[2:]
            self.assertEqual(len(pages), 3)
            for i, page in enumerate(pages):
                text = page.extract_text()
                self.assertIn("Personality", text)
                self.assertIn(f"Aarav", text)
                self.assertIn(f"Page {i+3}", text)
                codes = [t["code"] for t in traits if t["code"] in text.split()]
                self.assertEqual(len(codes), [2, 3, 2][i])


if __name__ == "__main__":
    unittest.main()