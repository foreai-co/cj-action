"""Tests for the runner module."""
import importlib

import pytest
import requests

import runner as runner_module

@pytest.fixture(scope="session")
def openapi_spec():
    """Get the OpenAPI spec for the backend."""
    response = requests.get(f"{runner_module.BACKEND_URL}/openapi.json", timeout=10)
    response.raise_for_status()
    return response.json()

def test_run_settings_with_invalid_json(monkeypatch):
    """Test that the run settings are created correctly from the environment variables."""
    monkeypatch.setenv("INPUT_WEBSITE_URL_OVERRIDE", "https://example.com")
    monkeypatch.setenv("INPUT_PARAMS_OVERRIDE", '"foo": "bar"')
    monkeypatch.setenv("INPUT_SERVICE_ACCOUNT_KEY", "test_key")
    importlib.reload(runner_module)
    result, msg = runner_module.run(requests.Session())
    assert not result
    assert "Failed: Invalid JSON in params_override" in msg

def test_no_login_on_invalid_service_account_key():
    """Test that the login fails if the service account key is invalid."""
    importlib.reload(runner_module)
    result, msg = runner_module.run(requests.Session())
    assert not result
    assert msg == "Failed: Service account key should be provided."

def test_invalid_login_response(monkeypatch):
    """Test that the login fails if the response is invalid."""
    session = requests.Session()
    class FakeResponse:
        """Fake response for the login request."""
        status_code = 401
        def json(self):
            """Fake JSON response for the login request."""
            return "jwt-token"

    monkeypatch.setenv("INPUT_SERVICE_ACCOUNT_KEY", "test_key")
    monkeypatch.setattr(session, "post", lambda _: FakeResponse())
    result, msg = runner_module.run(session)
    assert not result
    assert msg == "Failed: Service account key should be provided."

def test_handle_single_test_run_success(monkeypatch, openapi_spec):
    """Test that the single test run works when no settings are provided."""
    session = requests.Session()

    class FakeResponse:
        """Fake response for the login request."""
        def __init__(self, url, method):
            """Fake response class."""
            self.url = url
            self.url_path = url.split(runner_module.BACKEND_URL)[-1]
            self.url_path_with_placeholder = (
                self.url_path.replace("test-case-id", "{test_case_id}")
                .replace("test-run-id", "{test_run_id}")
            )
            self.method = method
            self.path_spec = openapi_spec["paths"][self.url_path_with_placeholder][method.lower()]

        def json(self):
            """Fake JSON response for the login request."""
            if self.url_path == "/auth/login_service_account":
                assert self.method == "POST"
                return {"auth_token": "123"}
            if self.url_path == "/test-run/test-case-id":
                assert self.method == "POST"
                return "test-run-id"
            if self.url_path == "/test-run/test-run-id":
                assert self.method == "GET"
                return {"status": "passed"}
            else:
                raise ValueError(f"Unexpected URL: {self.url}")

        @property
        def status_code(self):
            """Fake status code for the post request."""
            if "login_service_account" in self.url:
                return 200
            if "/test-run/test-case-id" in self.url:
                return 201
            if "/test-run/test-run-id" in self.url:
                return 200
            else:
                raise ValueError(f"Unexpected URL: {self.url}")

    def fake_post(url, json=None, **kwargs):
        """Fake response for the post request."""
        del kwargs
        if url == f"{runner_module.BACKEND_URL}/test-run/test-case-id":
            test_run_input_schema = openapi_spec["components"]["schemas"]["TestRun-Input"]
            for field in json:
                assert (
                    field in test_run_input_schema.get("properties", {}).keys() or
                    field in test_run_input_schema.get("required", [])
                ), f"Unexpected field: {field}"
        return FakeResponse(url, "POST")

    def fake_get(url, **kwargs):
        """Fake response for the get request."""
        del kwargs
        return FakeResponse(url, "GET")

    monkeypatch.setenv("INPUT_SERVICE_ACCOUNT_KEY", "test_key")
    monkeypatch.setenv("INPUT_TEST_ID", "test-case-id")
    monkeypatch.setenv("INPUT_WEBSITE_URL_OVERRIDE", "https://example.com")
    monkeypatch.setenv("INPUT_PARAMS_OVERRIDE", '{"foo": "bar"}')
    monkeypatch.setattr(session, "post", fake_post)
    monkeypatch.setattr(session, "get", fake_get)
    importlib.reload(runner_module)
    result, msg = runner_module.run(session)
    assert result
    assert msg == "Test passed!"

def test_handle_bulk_test_run_success(monkeypatch, openapi_spec):
    """Test that the bulk test run works when no settings are provided."""
    session = requests.Session()

    class FakeResponse:
        """Fake response for the login request."""
        def __init__(self, url, method):
            """Fake response for the login request."""
            self.url = url
            self.url_path = url.split(runner_module.BACKEND_URL)[-1]
            self.url_path_with_placeholder = (
                self.url_path.replace("collection-id", "{collection_id}")
            )
            self.method = method
            self.path_spec = openapi_spec["paths"][self.url_path_with_placeholder][method.lower()]

        def json(self):
            """Fake JSON response for the login request."""
            if self.url_path == "/auth/login_service_account":
                assert self.method == "POST"
                return {"auth_token": "123"}
            if self.url_path == "/test-suites/collection/collection-id/run-all":
                assert self.method == "POST"
                return "test-run-id"
            if self.url_path == "/test-suites/collection/collection-id":
                assert self.method == "GET"
                return {"test_suite_id": "project-id", "linked_runs": [
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
                ]}
            else:
                raise ValueError(f"Unexpected URL: {self.url}")

        @property
        def status_code(self):
            """Fake status code for the post request."""
            if "login_service_account" in self.url:
                return 200
            if "/test-suites/collection/collection-id/run-all" in self.url:
                return 200
            if "/test-suites/collection/collection-id" in self.url:
                return 200
            else:
                raise ValueError(f"Unexpected URL: {self.url}")

    def fake_post(url, json=None, **kwargs):
        """Fake response for the post request."""
        del kwargs
        if url == f"{runner_module.BACKEND_URL}/test-suites/collection/collection-id/run-all":
            test_run_input_schema = openapi_spec["components"]["schemas"]["RunSettings"]
            for field in json:
                assert (
                    field in test_run_input_schema.get("properties", {}).keys() or
                    field in test_run_input_schema.get("required", [])
                ), f"Unexpected field: {field}"
        return FakeResponse(url, "POST")

    def fake_get(url, **kwargs):
        """Fake response for the get request."""
        del kwargs
        return FakeResponse(url, "GET")

    monkeypatch.setenv("INPUT_SERVICE_ACCOUNT_KEY", "test_key")
    monkeypatch.setenv("INPUT_TEST_SUITE_ID", "collection-id")
    monkeypatch.setenv("INPUT_WEBSITE_URL_OVERRIDE", "https://example.com")
    monkeypatch.setenv("INPUT_PARAMS_OVERRIDE", '{"foo": "bar"}')
    monkeypatch.setattr(session, "post", fake_post)
    monkeypatch.setattr(session, "get", fake_get)
    importlib.reload(runner_module)
    result, msg = runner_module.run(session)
    assert result is False
    assert "1 passed, 1 failed" in msg
    assert "https://cj.foreai.co/collections/project-id/collection-id" in msg
