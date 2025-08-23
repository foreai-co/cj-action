"""Unittest version of tests for the runner module."""
import os
import unittest
from unittest.mock import patch

import requests
import runner as runner_module


class RunnerTests(unittest.TestCase):
    """Tests for the runner module."""

    def setUp(self):
        """Fetch the OpenAPI spec once for all tests."""
        # Load OpenAPI spec for the backend.
        response = requests.get(f"{runner_module.BACKEND_URL}/openapi.json", timeout=10)
        response.raise_for_status()
        self.openapi_spec = response.json()

    def test_run_settings_with_invalid_json(self):
        """Test that the runner module returns an error when the params_override is invalid JSON."""
        with patch.dict(os.environ, {
            "INPUT_WEBSITE_URL_OVERRIDE": "https://example.com",
            "INPUT_PARAMS_OVERRIDE": '"foo": "bar"',  # invalid JSON
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
        }, clear=True):
            result, msg = runner_module.run(requests.Session())
            self.assertFalse(result)
            self.assertIn("Failed: Invalid JSON in params_override", msg)

    def test_no_login_on_invalid_service_account_key(self):
        """Test that the runner module returns an error when the service account key is invalid."""
        with patch.dict(os.environ, {}, clear=True):
            result, msg = runner_module.run(requests.Session())
            self.assertFalse(result)
            self.assertEqual(msg, "Failed: Service account key should be provided.")

    def test_invalid_login_response(self):
        """Test that the runner module returns an error when the login response is invalid."""
        session = requests.Session()

        class FakeResponse:
            """Fake response for the login endpoint."""
            status_code = 401
            def json(self):
                """Return a JSON response."""
                return "jwt-token"

        with patch.dict(os.environ, {"INPUT_SERVICE_ACCOUNT_KEY": "test_key"}, clear=True):
            with patch.object(session, "post", return_value=FakeResponse()):
                result, msg = runner_module.run(session)
                self.assertFalse(result)
                self.assertEqual(msg, "Failed to login service account.")

    def test_handle_single_test_run_success(self):
        """Test that the runner module returns a success message when the single test run is
        successful."""
        session = requests.Session()
        openapi_spec = self.openapi_spec

        class FakeResponse:
            """Fake response for the test run endpoint."""
            def __init__(self, url, method):
                self.url = url
                self.url_path = url.split(runner_module.BACKEND_URL)[-1]
                self.url_path_with_placeholder = (
                    self.url_path.replace("test-case-id", "{test_case_id}")
                    .replace("test-run-id", "{test_run_id}")
                )
                self.method = method
                self.path_spec = (
                    openapi_spec["paths"][self.url_path_with_placeholder][method.lower()]
                )

            def json(self):
                """Return a JSON response."""
                if self.url_path == "/auth/login_service_account":
                    self.assert_method("POST")
                    return {"auth_token": "123"}
                if self.url_path == "/test-run/test-case-id":
                    self.assert_method("POST")
                    return "test-run-id"
                if self.url_path == "/test-run/test-run-id":
                    self.assert_method("GET")
                    return {"status": "passed"}
                raise ValueError(f"Unexpected URL: {self.url}")

            def assert_method(self, expected):
                """Assert that the method is as expected."""
                assert self.method == expected

            @property
            def status_code(self):
                """Return an OK status code."""
                if "login_service_account" in self.url:
                    return 200
                if "/test-run/test-case-id" in self.url:
                    return 201
                if "/test-run/test-run-id" in self.url:
                    return 200
                raise ValueError(f"Unexpected URL: {self.url}")

        def fake_post(url, json=None, **kwargs):
            if url == f"{runner_module.BACKEND_URL}/test-run/test-case-id":
                schema = openapi_spec["components"]["schemas"]["TestRun-Input"]
                for field in json:
                    self.assertIn(
                        field,
                        schema.get("properties", {}).keys() | set(schema.get("required", []))
                    )
            return FakeResponse(url, "POST")

        def fake_get(url, **kwargs):
            del kwargs
            return FakeResponse(url, "GET")

        with patch.dict(os.environ, {
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
            "INPUT_TEST_ID": "test-case-id",
            "INPUT_WEBSITE_URL_OVERRIDE": "https://example.com",
            "INPUT_PARAMS_OVERRIDE": '{"foo": "bar"}',
        }, clear=True):
            with patch.object(session, "post", side_effect=fake_post):
                with patch.object(session, "get", side_effect=fake_get):
                    result, msg = runner_module.run(session)
                    self.assertTrue(result)
                    self.assertEqual(msg, "Test passed!")

    def test_handle_bulk_test_run_success(self):
        """Test that the runner module returns a success message when the bulk test run is
        successful."""
        session = requests.Session()
        openapi_spec = self.openapi_spec

        class FakeResponse:
            """Fake response for the test suite run endpoint."""
            def __init__(self, url, method):
                self.url = url
                self.url_path = url.split(runner_module.BACKEND_URL)[-1]
                self.url_path_with_placeholder = (
                    self.url_path.replace("collection-id", "{collection_id}")
                )
                self.method = method
                self.path_spec = (
                    openapi_spec["paths"][self.url_path_with_placeholder][method.lower()]
                )

            def json(self):
                """Return a JSON response."""
                if self.url_path == "/auth/login_service_account":
                    return {"auth_token": "123"}
                if self.url_path == "/test-suites/collection/collection-id/run-all":
                    return "2025-01-01T00:00:00.000Z"
                if self.url_path == "/test-suites/collection/collection-id":
                    return {
                        "test_suite_id": "project-id",
                        "linked_runs": [
                            {
                                "id": "test-run-id",
                                "status": "passed",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": "test-run-id-2",
                                "status": "failed",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                            # Run at different time.
                            {
                                "id": "test-run-id-3",
                                "status": "passed",
                                "created_at": "2026-01-01T00:00:01Z",
                            },
                        ],
                    }
                raise ValueError(f"Unexpected URL: {self.url}")

            @property
            def status_code(self):
                """Return an OK status code."""
                return 200

        def fake_post(url, json=None, **kwargs):
            del kwargs
            if url == f"{runner_module.BACKEND_URL}/test-suites/collection/collection-id/run-all":
                schema = openapi_spec["components"]["schemas"]["RunSettings"]
                for field in json:
                    self.assertIn(
                        field,
                        schema.get("properties", {}).keys() | set(schema.get("required", []))
                    )
            return FakeResponse(url, "POST")

        def fake_get(url, **kwargs):
            return FakeResponse(url, "GET")

        with patch.dict(os.environ, {
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
            "INPUT_TEST_SUITE_ID": "collection-id",
            "INPUT_WEBSITE_URL_OVERRIDE": "https://example.com",
            "INPUT_PARAMS_OVERRIDE": '{"foo": "bar"}',
        }, clear=True):
            with patch.object(session, "post", side_effect=fake_post):
                with patch.object(session, "get", side_effect=fake_get):
                    result, msg = runner_module.run(session)
                    self.assertFalse(result)
                    self.assertIn("1 passed, 1 failed", msg)
                    self.assertIn(
                        "https://cj.foreai.co/collections/project-id/"
                        "collection-id?created_at=2025-01-01T00:00:00.000000Z",
                        msg,
                    )


if __name__ == "__main__":
    unittest.main()
