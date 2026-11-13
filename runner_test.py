"""Unittest version of tests for the runner module."""
import os
import tempfile
import unittest
from unittest.mock import patch

import requests
from dotenv import load_dotenv

import runner as runner_module


class RunnerTests(unittest.TestCase):
    """Tests for the runner module."""

    @classmethod
    def setUpClass(cls):
        """Fetch the OpenAPI spec once for all tests."""
        # The backend only serves its spec to a signed-in user.
        load_dotenv()
        session = requests.Session()
        if not runner_module._login_service_account(
                session, os.environ["CJ_PROD_SERVICE_ACCOUNT_KEY"]):
            raise RuntimeError("Failed to login the CJ_PROD_SERVICE_ACCOUNT_KEY service account.")
        response = session.get(f"{runner_module.get_backend_url()}/openapi.json", timeout=10)
        session.close()
        response.raise_for_status()
        cls.openapi_spec = response.json()

    @classmethod
    def tearDownClass(cls):
        """Clean up the OpenAPI spec."""
        cls.openapi_spec = None

    def test_run_settings_with_invalid_json(self):
        """Test that an error is returned when variable_overrides is invalid JSON."""
        with patch.dict(os.environ, {
            "INPUT_WEBSITE_URL_OVERRIDE": "https://example.com",
            "INPUT_VARIABLE_OVERRIDES": '"foo": "bar"',  # invalid JSON
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
        }, clear=True):
            result, msg, _ = runner_module.run(requests.Session())
            self.assertFalse(result)
            self.assertIn("Failed: Invalid JSON in variable_overrides", msg)

    def test_no_login_on_invalid_service_account_key(self):
        """Test that the runner module returns an error when the service account key is invalid."""
        with patch.dict(os.environ, {}, clear=True):
            result, msg, _ = runner_module.run(requests.Session())
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
                result, msg, _ = runner_module.run(session)
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
                self.url_path = url.split(runner_module.get_backend_url())[-1]
                self.url_path_with_placeholder = (
                    self.url_path.replace("test-case-id", "{test_case_id}")
                    .replace("test-run-id", "{test_run_id}")
                )
                self.method = method
                self.path_spec = (
                    openapi_spec.get("paths", {})
                    .get(self.url_path_with_placeholder, {})
                    .get(method.lower())
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
            if url == f"{runner_module.get_backend_url()}/test-run/test-case-id":
                schema = openapi_spec["components"]["schemas"]["SubmitTestRunRequest"]
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
            "INPUT_VARIABLE_OVERRIDES": (
                '{"3f2504e0-4f89-11d3-9a0c-0305e82c3301":'
                ' {"kind": "non_secret", "value": "bar"}}'
            ),
            "INPUT_BROWSER_TYPE_OVERRIDE": "firefox",
        }, clear=True):
            with patch.object(session, "post", side_effect=fake_post):
                with patch.object(session, "get", side_effect=fake_get):
                    result, msg, _ = runner_module.run(session)
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
                self.url_path = url.split(runner_module.get_backend_url())[-1]
                self.url_path_with_placeholder = (
                    self.url_path.replace("collection-id", "{collection_id}")
                )
                self.method = method
                self.path_spec = (
                    openapi_spec.get("paths", {})
                    .get(self.url_path_with_placeholder, {})
                    .get(method.lower())
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
                                "_id": "test-run-id",
                                "status": "passed",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "_id": "test-run-id-2",
                                "status": "failed",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                            # Run at different time.
                            {
                                "_id": "test-run-id-3",
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

        # Collected here rather than asserted inline: run() wraps everything in a
        # broad except, which would swallow the AssertionError and report it as a
        # generic failure.
        unknown_fields = []

        def fake_post(url, json=None, **kwargs):
            del kwargs
            run_all_url = (
                f"{runner_module.get_backend_url()}"
                "/test-suites/collection/collection-id/run-all"
            )
            if url == run_all_url:
                schema = openapi_spec["components"]["schemas"]["RunSettings-Input"]
                known = schema.get("properties", {}).keys() | set(schema.get("required", []))
                unknown_fields.extend(field for field in json if field not in known)
            return FakeResponse(url, "POST")

        def fake_get(url, **kwargs):
            return FakeResponse(url, "GET")

        with patch.dict(os.environ, {
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
            "INPUT_TEST_SUITE_ID": "collection-id",
            "INPUT_WEBSITE_URL_OVERRIDE": "https://example.com",
            "INPUT_VARIABLE_OVERRIDES": (
                '{"3f2504e0-4f89-11d3-9a0c-0305e82c3301":'
                ' {"kind": "non_secret", "value": "bar"}}'
            ),
            "INPUT_BROWSER_TYPE_OVERRIDE": "firefox",
            "INPUT_APP_NAME_OVERRIDE": "My App",
            "INPUT_APP_PLATFORM_OVERRIDE": "android",
        }, clear=True):
            with patch.object(session, "post", side_effect=fake_post):
                with patch.object(session, "get", side_effect=fake_get):
                    result, msg, _ = runner_module.run(session)
                    self.assertEqual(unknown_fields, [])
                    self.assertFalse(result)
                    self.assertIn("1 passed, 1 failed", msg)
                    self.assertIn(
                        f"{runner_module.get_app_url()}/collections/project-id/"
                        "collection-id?created_at=2025-01-01T00:00:00.000000Z",
                        msg,
                    )

    def test_handle_bulk_test_run_without_overrides_sends_no_body(self):
        """Test that no request body is sent when no run settings are provided.

        An empty object would be read as an all-default RunSettings and override the
        collection's stored settings.
        """
        session = requests.Session()
        run_all_url = (
            f"{runner_module.get_backend_url()}"
            "/test-suites/collection/collection-id/run-all"
        )

        class FakeResponse:
            """Fake response for the test suite run endpoint."""
            status_code = 200

            def __init__(self, url):
                self.url_path = url.split(runner_module.get_backend_url())[-1]

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
                                "_id": "test-run-id",
                                "status": "passed",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                        ],
                    }
                raise ValueError(f"Unexpected URL path: {self.url_path}")

        # Collected rather than asserted inline: run() wraps everything in a broad
        # except, which would swallow the AssertionError.
        posted_bodies = []

        def fake_post(url, json=None, **kwargs):
            del kwargs
            if url == run_all_url:
                posted_bodies.append(json)
            return FakeResponse(url)

        def fake_get(url, **kwargs):
            del kwargs
            return FakeResponse(url)

        with patch.dict(os.environ, {
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
            "INPUT_TEST_SUITE_ID": "collection-id",
        }, clear=True):
            with patch.object(session, "post", side_effect=fake_post):
                with patch.object(session, "get", side_effect=fake_get):
                    result, msg, _ = runner_module.run(session)
                    self.assertEqual(posted_bodies, [None])
                    self.assertTrue(result)
                    self.assertIn("1 passed, 0 failed", msg)


    def _run_with_statuses(self, statuses: list[str], env: dict) -> tuple[bool, str, list[str]]:
        """Runs the action against a backend whose runs finished with the given statuses."""
        session = requests.Session()

        class FakeResponse:
            """Fake response for the test run and test suite run endpoints."""
            status_code = 201

            def __init__(self, url):
                self.url_path = url.split(runner_module.get_backend_url())[-1]
                if self.url_path != "/test-run/test-case-id":
                    self.status_code = 200

            def json(self):
                """Return a JSON response."""
                if self.url_path == "/auth/login_service_account":
                    return {"auth_token": "123"}
                if self.url_path == "/test-run/test-case-id":
                    return "test-run-id-0"
                if self.url_path == "/test-run/test-run-id-0":
                    return {"status": statuses[0], "error_message": None}
                if self.url_path == "/test-suites/collection/collection-id/run-all":
                    return "2025-01-01T00:00:00.000Z"
                if self.url_path == "/test-suites/collection/collection-id":
                    return {
                        "test_suite_id": "project-id",
                        "linked_runs": [
                            {
                                "_id": f"test-run-id-{idx}",
                                "status": status,
                                "created_at": "2025-01-01T00:00:00Z",
                            }
                            for idx, status in enumerate(statuses)
                        ],
                    }
                raise ValueError(f"Unexpected URL path: {self.url_path}")

        def fake_request(url, **kwargs):
            del kwargs
            return FakeResponse(url)

        with patch.dict(os.environ, {"INPUT_SERVICE_ACCOUNT_KEY": "test_key", **env}, clear=True):
            with patch.object(session, "post", side_effect=fake_request):
                with patch.object(session, "get", side_effect=fake_request):
                    return runner_module.run(session)

    def test_handle_bulk_test_run_with_not_executed_and_cancelled_runs(self):
        """Test how runs that did not pass or fail affect the collection run result."""
        cases = [
            # (statuses, fail_on_skipped, fail_on_not_runnable, success, msg, failed ids)
            (["passed", "skipped"], "false", "false", True,
             "1 passed, 0 failed, 1 skipped.", []),
            (["passed", "skipped"], "true", "false", False,
             "1 passed, 0 failed, 1 skipped.", []),
            (["passed", "not_runnable"], "true", "false", True,
             "1 passed, 0 failed, 1 not runnable.", []),
            (["passed", "not_runnable"], "false", "true", False,
             "1 passed, 0 failed, 1 not runnable.", []),
            (["passed", "cancelled", "aborted"], "false", "false", False,
             "1 passed, 0 failed, 1 cancelled, 1 aborted.", ["test-run-id-1", "test-run-id-2"]),
        ]
        for statuses, fail_on_skipped, fail_on_not_runnable, success, msg, ids in cases:
            with self.subTest(statuses=statuses, fail_on_skipped=fail_on_skipped,
                              fail_on_not_runnable=fail_on_not_runnable):
                result, output_msg, failed_run_ids = self._run_with_statuses(statuses, {
                    "INPUT_TEST_SUITE_ID": "collection-id",
                    "INPUT_FAIL_ON_SKIPPED": fail_on_skipped,
                    "INPUT_FAIL_ON_NOT_RUNNABLE": fail_on_not_runnable,
                })
                self.assertEqual(result, success)
                self.assertIn(msg, output_msg)
                self.assertEqual(failed_run_ids, ids)

    def test_handle_bulk_test_run_defaults_for_not_executed_runs(self):
        """Test that by default not runnable runs fail the action and skipped runs do not."""
        env = {"INPUT_TEST_SUITE_ID": "collection-id"}
        self.assertTrue(self._run_with_statuses(["passed", "skipped"], env)[0])
        self.assertFalse(self._run_with_statuses(["passed", "not_runnable"], env)[0])

    def test_handle_single_test_run_with_not_executed_and_cancelled_runs(self):
        """Test how a single run that did not pass or fail affects the result."""
        cases = [
            # (status, fail_on_not_runnable, success, msg, failed ids)
            ("not_runnable", "false", True, "Test was not runnable.", []),
            ("not_runnable", "true", False, "Test was not runnable.", []),
            ("cancelled", "false", False, "Test was cancelled.", ["test-run-id-0"]),
            ("aborted", "false", False, "Test was aborted.", ["test-run-id-0"]),
        ]
        for status, fail_on_not_runnable, success, msg, ids in cases:
            with self.subTest(status=status, fail_on_not_runnable=fail_on_not_runnable):
                result, output_msg, failed_run_ids = self._run_with_statuses([status], {
                    "INPUT_TEST_ID": "test-case-id",
                    "INPUT_FAIL_ON_NOT_RUNNABLE": fail_on_not_runnable,
                })
                self.assertEqual(result, success)
                self.assertEqual(output_msg, msg)
                self.assertEqual(failed_run_ids, ids)

    def test_app_override_from_env(self):
        """Test how the app overrides are read into run settings."""
        cases = [
            ({}, None),
            ({"INPUT_APP_FILE_ID_OVERRIDE": "file-id"},
             {"kind": "app_file_id", "app_file_id": "file-id"}),
            ({"INPUT_APP_NAME_OVERRIDE": "My App", "INPUT_APP_PLATFORM_OVERRIDE": "Android"},
             {"kind": "app_tag", "app_name": "My App", "platform": "android", "tag": "latest"}),
            ({"INPUT_APP_NAME_OVERRIDE": "My App", "INPUT_APP_PLATFORM_OVERRIDE": "ios",
              "INPUT_APP_TAG_OVERRIDE": "1.4.3"},
             {"kind": "app_tag", "app_name": "My App", "platform": "ios", "tag": "1.4.3"}),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                with patch.dict(os.environ, env, clear=True):
                    run_settings = runner_module._create_run_settings_from_env()
                self.assertEqual(run_settings.get("mobile_app_override"), expected)

    def test_invalid_app_override_from_env(self):
        """Test that inconsistent app overrides are rejected."""
        cases = [
            {"INPUT_APP_FILE_ID_OVERRIDE": "file-id", "INPUT_APP_NAME_OVERRIDE": "My App"},
            {"INPUT_APP_NAME_OVERRIDE": "My App"},
            {"INPUT_APP_NAME_OVERRIDE": "My App", "INPUT_APP_PLATFORM_OVERRIDE": "windows"},
            {"INPUT_APP_PLATFORM_OVERRIDE": "android"},
            {"INPUT_APP_TAG_OVERRIDE": "latest"},
        ]
        for env in cases:
            with self.subTest(env=env):
                with patch.dict(os.environ, {"INPUT_SERVICE_ACCOUNT_KEY": "test_key", **env},
                                clear=True):
                    result, msg, _ = runner_module.run(requests.Session())
                self.assertFalse(result)
                self.assertTrue(msg.startswith("Failed: "), msg)

    def _run_with_app_upload(self, env: dict) -> tuple[tuple[bool, str, list[str]], dict, list]:
        """Runs the action against a fake backend that accepts an app upload.

        Returns:
            The run's result, its outputs and the (url, kwargs) of each POST request.
        """
        session = requests.Session()
        openapi_spec = self.openapi_spec
        backend_url = runner_module.get_backend_url()

        class FakeResponse:
            """Fake response for the organization, app upload and test run endpoints."""
            text = ""

            def __init__(self, url, method):
                self.url_path = url.split(backend_url)[-1]
                path_template = (
                    self.url_path.replace("org-id", "{org_id}")
                    .replace("test-case-id", "{test_case_id}")
                    .replace("test-run-id", "{test_run_id}")
                )
                if method.lower() not in openapi_spec["paths"].get(path_template, {}):
                    raise ValueError(f"{method} {path_template} is not in the OpenAPI spec")
                self.status_code = 201 if self.url_path in (
                    "/organizations/org-id/app-files", "/test-run/test-case-id") else 200

            def json(self):
                """Return a JSON response."""
                if self.url_path == "/auth/login_service_account":
                    return "jwt-token"
                if self.url_path == "/auth/get-user-organizations":
                    return [{"organization": {"org_id": "org-id", "name": "Org"}}]
                if self.url_path == "/organizations/org-id/app-files":
                    return {
                        "app_file_id": "app-file-id",
                        "app_name": "My App",
                        "file_name": "app.apk",
                    }
                if self.url_path == "/test-run/test-case-id":
                    return "test-run-id"
                if self.url_path == "/test-run/test-run-id":
                    return {"status": "passed"}
                raise ValueError(f"Unexpected URL path: {self.url_path}")

        posts = []

        def fake_post(url, **kwargs):
            files = kwargs.get("files")
            # The file is closed once the upload returns.
            posts.append((url, {
                **kwargs,
                "files": files and {
                    name: (file_name, file.read(), content_type)
                    for name, (file_name, file, content_type) in files.items()
                },
            }))
            return FakeResponse(url, "POST")

        def fake_get(url, **kwargs):
            del kwargs
            return FakeResponse(url, "GET")

        outputs = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            app_file_path = os.path.join(tmp_dir, "app.apk")
            with open(app_file_path, "wb") as app_file:
                app_file.write(b"apk-bytes")
            with patch.dict(os.environ, {
                "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
                "INPUT_APP_FILE_PATH": app_file_path,
                **env,
            }, clear=True):
                with patch.object(session, "post", side_effect=fake_post):
                    with patch.object(session, "get", side_effect=fake_get):
                        result = runner_module.run(session, outputs)
        return result, outputs, posts

    def test_upload_app_file_only(self):
        """Test that the app file is uploaded as a multipart form to the org's app files."""
        (result, msg, _), outputs, posts = self._run_with_app_upload({
            "INPUT_APP_NAME": "My App",
            "INPUT_APP_TAGS": "latest, 1.4.3\nnightly",
        })
        self.assertTrue(result, msg)
        self.assertEqual(msg, "Uploaded app.apk to app My App as app file app-file-id.")
        self.assertEqual(outputs, {"app_file_id": "app-file-id"})

        upload_url, upload_kwargs = posts[-1]
        self.assertEqual(
            upload_url, f"{runner_module.get_backend_url()}/organizations/org-id/app-files")
        self.assertEqual(upload_kwargs["data"], {
            "file_name": "app.apk",
            "app_name": "My App",
            "tags": ["latest", "1.4.3", "nightly"],
        })
        self.assertEqual(
            upload_kwargs["files"], {"file": ("app.apk", b"apk-bytes", "application/octet-stream")})
        self.assertEqual(upload_kwargs["headers"], {"Content-Type": None})

        form_schema = self.openapi_spec["components"]["schemas"][
            "Body_create_app_file_organizations__org_id__app_files_post"]
        self.assertLessEqual(
            {*upload_kwargs["data"], *upload_kwargs["files"]}, form_schema["properties"].keys())

    def test_upload_app_file_tags(self):
        """Test that an upload is tagged latest unless given other tags."""
        cases = [
            ({}, ["latest"]),
            ({"INPUT_APP_TAGS": "1.4.3"}, ["1.4.3"]),
            ({"INPUT_APP_TAGS": ""}, []),
        ]
        for env, expected_tags in cases:
            with self.subTest(env=env):
                (result, msg, _), _, posts = self._run_with_app_upload(env)
                self.assertTrue(result, msg)
                self.assertEqual(posts[-1][1]["data"], {"file_name": "app.apk", "tags": expected_tags})

    def test_upload_app_file_and_run_on_it(self):
        """Test that the tests run on the uploaded app file, unless told to run another app."""
        cases = [
            ({}, {"kind": "app_file_id", "app_file_id": "app-file-id"}),
            ({"INPUT_APP_FILE_ID_OVERRIDE": "other-file-id"},
             {"kind": "app_file_id", "app_file_id": "other-file-id"}),
        ]
        for env, expected_app in cases:
            with self.subTest(env=env):
                (result, msg, _), outputs, posts = self._run_with_app_upload(
                    {"INPUT_TEST_ID": "test-case-id", **env})
                self.assertTrue(result, msg)
                self.assertEqual(
                    msg, "Uploaded app.apk to app My App as app file app-file-id. Test passed!")
                self.assertEqual(outputs, {"app_file_id": "app-file-id"})
                run_url, run_kwargs = posts[-1]
                self.assertEqual(run_url, f"{runner_module.get_backend_url()}/test-run/test-case-id")
                settings = run_kwargs["json"]["settings"]
                self.assertEqual(settings, {"mobile_app_override": expected_app})
                self.assertIn(
                    "mobile_app_override",
                    self.openapi_spec["components"]["schemas"]["RunSettings-Input"]["properties"],
                )

    def test_upload_missing_app_file(self):
        """Test that a missing app file fails the action before anything is run."""
        session = requests.Session()

        class FakeResponse:
            """Fake response for the login endpoint."""
            status_code = 200

            def json(self):
                """Return a JSON response."""
                return "jwt-token"

        with patch.dict(os.environ, {
            "INPUT_SERVICE_ACCOUNT_KEY": "test_key",
            "INPUT_TEST_ID": "test-case-id",
            "INPUT_APP_FILE_PATH": "does/not/exist.apk",
        }, clear=True):
            with patch.object(session, "post", return_value=FakeResponse()) as post:
                result, msg, _ = runner_module.run(session)
        self.assertFalse(result)
        self.assertEqual(msg, "Failed: App file not found: does/not/exist.apk")
        self.assertEqual(post.call_count, 1)  # Only the login.

if __name__ == "__main__":
    unittest.main()
