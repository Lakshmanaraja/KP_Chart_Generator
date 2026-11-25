from datetime import date, datetime
from io import BytesIO
import unittest
from unittest.mock import patch

from models.schemas import PredictionPeriodsRequest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from services import predict_service


def request(bhava_number=7, from_date=date(2026, 11, 25)):
    return PredictionPeriodsRequest(
        date_of_birth="1981-10-14",
        time_of_birth="12:46",
        latitude=13.76,
        longitude=75,
        timezone=5.5,
        from_date=from_date,
        duration_years=1,
        bhava_number=bhava_number,
    )


class PredictionServiceTests(unittest.TestCase):
    def test_calendar_year_addition_clamps_leap_day(self):
        self.assertEqual(predict_service.add_calendar_years(date(2024, 2, 29), 1), date(2025, 2, 28))
        self.assertEqual(predict_service.add_calendar_years(date(2024, 2, 29), 4), date(2028, 2, 29))

    def test_bhava_groups_include_primary_and_two_secondaries(self):
        expected = {
            1: (1, 5, 9), 2: (2, 6, 10), 3: (3, 7, 11),
            4: (4, 8, 12), 5: (1, 5, 9), 6: (2, 6, 10),
            7: (3, 7, 11), 8: (4, 8, 12), 9: (1, 5, 9),
            10: (2, 6, 10), 11: (3, 7, 11), 12: (4, 8, 12),
        }
        for bhava, group in expected.items():
            with self.subTest(bhava=bhava):
                self.assertEqual(predict_service.bhava_group(bhava), group)

    def test_dba_keeps_in_progress_periods_and_parent_original_boundaries(self):
        major = [{
            "planet": "Jupiter",
            "start": datetime(2026, 1, 1),
            "end": datetime(2027, 1, 1),
        }]
        bhukti_active = {
            "planet": "Saturn",
            "start": datetime(2026, 11, 24),
            "end": datetime(2026, 12, 1),
        }
        bhukti_finished_at_start = {
            "planet": "Mercury",
            "start": datetime(2026, 11, 1),
            "end": datetime(2026, 11, 25),
        }
        antara_active = {
            "planet": "Venus",
            "start": datetime(2026, 11, 24),
            "end": datetime(2026, 11, 26),
        }
        antara_finished_at_start = {
            "planet": "Mars",
            "start": datetime(2026, 11, 20),
            "end": datetime(2026, 11, 25),
        }

        def bhuktis(_lord, _start, _end):
            return [bhukti_active, bhukti_finished_at_start]

        def antaras(lord, _start, _end):
            return [antara_active, antara_finished_at_start] if lord == "Saturn" else []

        with (
            patch.object(predict_service, "_birth_times", return_value=(datetime(1981, 10, 14), 0)),
            patch.object(predict_service, "compute_major_dasha", return_value=major),
            patch.object(predict_service, "calculate_bhuktis", side_effect=bhuktis),
            patch.object(predict_service, "calculate_antaras", side_effect=antaras),
        ):
            result = predict_service.get_dba_periods(request())

        self.assertEqual([row["bhukthi"] for row in result["bhukti_periods"]], ["Saturn"])
        bhukti = result["bhukti_periods"][0]
        self.assertEqual(bhukti["mahadasha_start"], "2026-01-01T00:00:00")
        self.assertEqual(bhukti["mahadasha_end"], "2027-01-01T00:00:00")
        self.assertEqual([row["antara"] for row in result["antara_periods"]], ["Venus"])
        antara = result["antara_periods"][0]
        self.assertEqual(antara["bhukthi_start"], "2026-11-24T00:00:00")
        self.assertEqual(antara["bhukthi_end"], "2026-12-01T00:00:00")

    def test_bhava_seven_transits_keep_actual_houses_and_labels(self):
        rows = [
            {"planet": "Venus", "star": "Rohini", "bhava": 3, "date": "2026-12-01T00:00:00Z", "exit_date": "2026-12-03T00:00:00Z"},
            {"planet": "Mars", "star": "Ashwini", "bhava": 7, "date": "2026-12-04T00:00:00Z", "exit_date": "2026-12-06T00:00:00Z"},
            {"planet": "Jupiter", "star": "Revati", "bhava": 11, "date": "2026-12-07T00:00:00Z", "exit_date": "2026-12-09T00:00:00Z"},
            {"planet": "Saturn", "star": "Pushya", "bhava": 2, "date": "2026-12-10T00:00:00Z", "exit_date": "2026-12-12T00:00:00Z"},
        ]
        chart = {"houses": [{"house_id": n, "full_degree": n * 30} for n in range(1, 13)]}
        with (
            patch.object(predict_service, "compute_kp_json", return_value=chart),
            patch.object(predict_service, "get_star_transits_for_cusps", return_value=rows),
        ):
            result = predict_service.get_transit_periods(request())

        self.assertEqual(result["bhava_group"], [3, 7, 11])
        self.assertEqual(
            [(row["actual_bhava"], row["bhava_type"]) for row in result["transit_periods"]],
            [(3, "secondary"), (7, "primary"), (11, "secondary")],
        )

    def test_prediction_pdf_keeps_cover_first_and_adds_sections_in_both_formats(self):
        cover_buffer = BytesIO()
        cover_canvas = canvas.Canvas(cover_buffer, pagesize=A4)
        cover_canvas.drawString(40, 800, "ADULT CHARACTER COVER")
        cover_canvas.save()
        report = predict_service.PredictionReportRequest(
            name="Test Client", date_of_birth="1981-10-14", time_of_birth="12:46",
            latitude=13.76, longitude=75, from_date=date(2026, 11, 25),
            duration_years=1,
        )
        dba = {
            "from_date": "2026-11-25", "end_date_exclusive": "2027-11-25",
            "bhukti_periods": [], "antara_periods": [],
        }
        transit = {"transit_periods": []}

        for version in ("mobile", "desktop"):
            with (
                self.subTest(version=version),
                patch.object(predict_service, "get_dba_periods", return_value=dba),
                patch.object(predict_service, "get_transit_periods", return_value=transit),
                patch.object(predict_service, "_report_cover", return_value=cover_buffer.getvalue()),
            ):
                report.version = version
                pdf = predict_service.create_prediction_pdf(report, "marriage", 7)
                pages = PdfReader(BytesIO(pdf)).pages
                self.assertGreaterEqual(len(pages), 2)
                self.assertIn("ADULT CHARACTER COVER", pages[0].extract_text() or "")
                prediction_text = " ".join(page.extract_text() or "" for page in pages[1:])
                self.assertIn("DBA Periods", prediction_text)
                self.assertIn("Transit Periods", prediction_text)

    def test_no_traits_uses_standard_cover_renderer(self):
        report = predict_service.PredictionReportRequest(
            name="Test Client", date_of_birth="1981-10-14", time_of_birth="12:46",
            latitude=13.76, longitude=75, version="mobile",
        )
        with (
            patch.object(predict_service, "_pdf", side_effect=predict_service.NoTraitsFoundError()),
            patch.object(predict_service, "render_mobile_pdf", return_value=b"cover") as render,
        ):
            self.assertEqual(predict_service._report_cover(report), b"cover")
        render.assert_called_once()


if __name__ == "__main__":
    unittest.main()
