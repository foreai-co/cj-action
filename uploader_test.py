"""Unittest version of tests for the uploader module."""
import os
import tempfile
import unittest
from unittest.mock import patch

import requests

import runner as runner_module
import uploader as uploader_module
from runner_test import fetch_openapi_spec


class UploaderTests(unittest.TestCase):
    """Tests for the uploader module."""

    @classmethod
    def setUpClass(cls):
        """Fetch the OpenAPI spec once for all tests."""
        cls.openapi_spec = fetch_openapi_spec()

    @classmethod
    def tearDownClass(cls):
        """Clean up the OpenAPI spec."""
        cls.openapi_spec = None

    def _upload(
            self, env: dict, org_ids: tuple[str, ...] = ("org-id",)
        ) -> tuple[tuple[bool, str, dict[str, str]], list, list]:
        """Uploads an app file to a fake backend whose service account is in the given orgs.

        Returns:
            The upload's result, the (url, kwargs) of each POST request and the URL of each
            GET request.
        """
        session = requests.Session()
        openapi_spec = self.openapi_spec
        backend_url = runner_module.get_backend_url()

        class FakeResponse:
            """Fake response for the login, organization and app upload endpoints."""
            text = ""

            def __init__(self, url, method):
                self.url_path = url.split(backend_url)[-1]
                path_template = self.url_path.replace("org-id", "{org_id}")
                if method.lower() not in openapi_spec["paths"].get(path_template, {}):
                    raise ValueError(f"{method} {path_template} is not in the OpenAPI spec")
                self.status_code = (
                    201 if self.url_path == "/organizations/org-id/app-files" else 200)

            def json(self):
                """Return a JSON response."""
                if self.url_path == "/auth/login_service_account":
                    return "jwt-token"
                if self.url_path == "/auth/get-user-organizations":
                    return [
                        {"organization": {"org_id": org_id, "name": f"Org {org_id}"}}
                        for org_id in org_ids
                    ]
                if self.url_path == "/organizations/org-id/app-files":
                    return {
                        "app_file_id": "app-file-id",
                        "app_name": "My App",
                        "file_name": "app.apk",
                    }
                raise ValueError(f"Unexpected URL path: {self.url_path}")

        posts = []
        gets = []

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
            gets.append(url)
            return FakeResponse(url, "GET")

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
                        result = uploader_module.upload(session)
        return result, posts, gets

    def test_upload_app_file(self):
        """Test that the app file is uploaded as a multipart form to the org's app files."""
        (result, msg, outputs), posts, _ = self._upload({
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
                (result, msg, _), posts, _ = self._upload(env)
                self.assertTrue(result, msg)
                self.assertEqual(posts[-1][1]["data"], {"file_name": "app.apk", "tags": expected_tags})

    def test_upload_to_organization(self):
        """Test that the upload goes to the given org, else the service account's only one."""
        upload_url = f"{runner_module.get_backend_url()}/organizations/org-id/app-files"
        orgs_url = f"{runner_module.get_backend_url()}/auth/get-user-organizations"

        (result, msg, _), posts, gets = self._upload(
            {"INPUT_ORGANIZATION_ID": "org-id"}, org_ids=("org-id", "other-org-id"))
        self.assertTrue(result, msg)
        self.assertEqual(posts[-1][0], upload_url)
        self.assertNotIn(orgs_url, gets)

        (result, msg, _), posts, gets = self._upload({}, org_ids=("org-id", "other-org-id"))
        self.assertFalse(result)
        self.assertEqual(
            msg,
            "Failed: The service account belongs to 2 organizations, set organization_id to "
            "the one to upload to: Org org-id (org-id), Org other-org-id (other-org-id)",
        )
        self.assertNotIn(upload_url, [url for url, _ in posts])

    def test_invalid_inputs(self):
        """Test that missing inputs fail the upload before anything is sent."""
        cases = [
            ({"INPUT_APP_FILE_PATH": "app.apk"},
             "Failed: Service account key should be provided."),
            ({"INPUT_SERVICE_ACCOUNT_KEY": "test_key"},
             "Failed: app_file_path should be provided."),
            ({"INPUT_SERVICE_ACCOUNT_KEY": "test_key", "INPUT_APP_FILE_PATH": "does/not/exist.apk"},
             "Failed: App file not found: does/not/exist.apk"),
        ]
        for env, expected_msg in cases:
            with self.subTest(env=env):
                session = requests.Session()
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(session, "post") as post:
                        result, msg, outputs = uploader_module.upload(session)
                self.assertFalse(result)
                self.assertEqual(msg, expected_msg)
                self.assertEqual(outputs, {})
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
