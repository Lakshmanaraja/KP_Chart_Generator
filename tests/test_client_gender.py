import os
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from models.schemas import ReportRequest
from routers.report import router
from services.client_gender_service import resolve_report_gender


CLIENT_ID = "00000000-0000-4000-8000-000000000001"
BODY = dict(name="Test", date_of_birth="2020-01-02", time_of_birth="10:20:30",
            latitude=13.0, longitude=80.0, client_id=CLIENT_ID)


def response(value, status=200):
    result = Mock(status_code=status)
    result.json.return_value = value
    return result


@patch.dict(os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_ANON_KEY": "test-public-key"})
class SavedGenderTests(unittest.TestCase):
    @patch("services.client_gender_service.requests.get")
    def test_explicit_gender_has_precedence(self, get):
        req = ReportRequest(**BODY, gender="male")
        self.assertIs(resolve_report_gender(req, None), req)
        get.assert_not_called()

    @patch("services.client_gender_service.requests.get")
    def test_guest_without_id_uses_neutral(self, get):
        req = ReportRequest(**{k: v for k, v in BODY.items() if k != "client_id"})
        self.assertIsNone(resolve_report_gender(req, None).gender)
        get.assert_not_called()

    def test_id_alone_is_not_authorization(self):
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), None)
        self.assertEqual(caught.exception.status_code, 401)

    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_invalid_token_never_reads_client(self, get, post):
        get.return_value = response({}, 401)
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(get.call_count, 1)
        post.assert_not_called()

    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_unassigned_client_never_reads_gender(self, get, post):
        get.return_value = response({"id": "test-user"})
        post.return_value = response(False)
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(get.call_count, 1)

    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_authorized_gender_and_blank_fallback(self, get, post):
        for gender in (None, "", "   "):
            with self.subTest(gender=gender):
                get.side_effect = [response({"id": "test-user"}), response([{"gender": "Female"}])]
                post.return_value = response(True)
                req = ReportRequest(**BODY, gender=gender)
                resolved = resolve_report_gender(req, "Bearer test-token")
                self.assertEqual(resolved.gender, "Female")
                self.assertEqual(req.gender, gender)
                self.assertEqual(get.call_args.kwargs["params"]["select"], "gender")
                self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer test-token")
                post.assert_called_with("https://test.supabase.co/rest/v1/rpc/can_access_assigned_client",
                    headers={"apikey": "test-public-key", "Authorization": "Bearer test-token"},
                    json={"_client_id": CLIENT_ID}, timeout=10)

    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_saved_null_remains_neutral(self, get, post):
        get.side_effect = [response({"id": "test-user"}), response([{"gender": None}])]
        post.return_value = response(True)
        self.assertIsNone(resolve_report_gender(ReportRequest(**BODY), "Bearer test-token").gender)

    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_missing_or_rls_hidden_row_is_forbidden(self, get, post):
        get.side_effect = [response({"id": "test-user"}), response([])]
        post.return_value = response(True)
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 403)

    @patch("services.client_gender_service.requests.get", side_effect=requests.Timeout("private upstream detail"))
    def test_network_failure_is_not_silent_neutral(self, get):
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("private", caught.exception.detail)

    @patch.dict(os.environ, {"SUPABASE_ANON_KEY": ""})
    def test_missing_config_is_503(self):
        with self.assertRaises(HTTPException) as caught:
            resolve_report_gender(ReportRequest(**BODY), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 503)

    def test_client_id_must_be_uuid(self):
        with self.assertRaises(ValidationError):
            ReportRequest(**{**BODY, "client_id": "not-an-id"})

    @patch("routers.report._pdf", return_value=b"%PDF-test")
    @patch("routers.report._sections", return_value=[])
    @patch("routers.report._trait", return_value=[])
    @patch("services.client_gender_service.requests.post")
    @patch("services.client_gender_service.requests.get")
    def test_http_fallback_reaches_traits_json_and_both_pdf_versions(self, get, post, trait, sections, pdf):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        post.return_value = response(True)
        for path, version, renderer in (
            ("/report/api/traits", "mobile", trait),
            ("/report/api/character?format=json", "mobile", sections),
            ("/report/api/character", "mobile", pdf),
            ("/report/api/character", "desktop", pdf),
        ):
            with self.subTest(path=path, version=version):
                get.side_effect = [response({"id": "test-user"}), response([{"gender": "female"}])]
                result = client.post(path, json={**BODY, "version": version},
                                     headers={"Authorization": "Bearer test-token"})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(renderer.call_args.args[0].gender, "female")
                self.assertEqual(renderer.call_args.args[0].version, version)