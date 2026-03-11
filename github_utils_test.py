"""Tests for the github_utils module."""
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

import github_utils as github_utils_module


class BuildStepsMarkdownTests(unittest.TestCase):
    def test_empty_steps(self):
        result = github_utils_module._build_steps_markdown([])
        self.assertEqual(result, "No step information available")

    def test_success_and_failure_steps(self):
        steps = [
            {"action_name": "Click", "success": True},
            {"action_name": "Assert", "success": False},
        ]
        result = github_utils_module._build_steps_markdown(steps)
        self.assertIn("1. **Click** - ✅ Success", result)
        self.assertIn("2. **Assert** - ❌ Failed", result)

    def test_missing_action_name(self):
        steps = [{"success": True}]
        result = github_utils_module._build_steps_markdown(steps)
        self.assertIn("**Unknown**", result)


class BuildIssueBodyTests(unittest.TestCase):
    def _make_run_details(self, failing_step_index=None):
        return {
            "status": "failed",
            "user_friendly_error": "Button not found",
            "error_message": "ElementNotFound",
            "failing_step_index": failing_step_index,
            "created_at": "2025-01-01T00:00:00Z",
            "settings": {
                "viewport_width_override": 1280,
                "viewport_height_override": 720,
                "browser_type_override": "chromium",
                "platform": "linux",
                "website_url_override": "https://example.com",
            },
        }

    def test_contains_run_and_test_ids(self):
        body = github_utils_module._build_issue_body(
            run_details=self._make_run_details(),
            test_run_id="run-123",
            test_id="test-456",
            commit_sha="abc1234",
            branch="main",
            run_url="https://github.com/org/repo/actions/runs/99",
            steps_md="1. **Click** - ✅ Success",
        )
        self.assertIn("run-123", body)
        self.assertIn("test-456", body)
        self.assertIn("abc1234", body)
        self.assertIn("main", body)

    def test_failing_step_none_shows_na(self):
        body = github_utils_module._build_issue_body(
            run_details=self._make_run_details(failing_step_index=None),
            test_run_id="r", test_id="t", commit_sha="s",
            branch="b", run_url="u", steps_md="",
        )
        self.assertIn("Failing Step:** N/A", body)

    def test_failing_step_zero_shows_one(self):
        body = github_utils_module._build_issue_body(
            run_details=self._make_run_details(failing_step_index=0),
            test_run_id="r", test_id="t", commit_sha="s",
            branch="b", run_url="u", steps_md="",
        )
        self.assertIn("Failing Step:** 1", body)


class FetchRunDetailsTests(unittest.TestCase):
    def test_returns_json_on_200(self):
        session = MagicMock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = {"status": "failed"}
        result = github_utils_module._fetch_run_details(session, "run-123")
        self.assertEqual(result, {"status": "failed"})

    def test_returns_none_on_non_200(self):
        session = MagicMock()
        session.get.return_value.status_code = 404
        result = github_utils_module._fetch_run_details(session, "run-123")
        self.assertIsNone(result)

    def test_returns_none_on_json_decode_error(self):
        session = MagicMock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.side_effect = requests.JSONDecodeError(
            "bad json", "", 0)
        result = github_utils_module._fetch_run_details(session, "run-123")
        self.assertIsNone(result)


class GetScreenshotBytesTests(unittest.TestCase):
    def test_empty_steps_returns_failure(self):
        session = MagicMock()
        img_bytes, img_id, ok = github_utils_module._get_screenshot_bytes(session, [])
        self.assertFalse(ok)
        self.assertEqual(img_bytes, b"")

    def test_no_screenshot_id_returns_failure(self):
        session = MagicMock()
        steps = [{"trace": [{"screenshot_id": None}]}]
        _, _, ok = github_utils_module._get_screenshot_bytes(session, steps)
        self.assertFalse(ok)

    def test_empty_trace_returns_failure(self):
        session = MagicMock()
        steps = [{"trace": []}]
        _, _, ok = github_utils_module._get_screenshot_bytes(session, steps)
        self.assertFalse(ok)

    def test_url_fetch_failure_returns_failure(self):
        session = MagicMock()
        session.get.return_value.status_code = 500
        steps = [{"trace": [{"screenshot_id": "img-1"}]}]
        _, _, ok = github_utils_module._get_screenshot_bytes(session, steps)
        self.assertFalse(ok)

    def test_blobstore_fetch_failure_returns_failure(self):
        session = MagicMock()
        session.get.return_value.status_code = 200
        session.get.return_value.text = '"https://blobstore/img"'
        with patch("github_utils.requests.get") as mock_get:
            mock_get.return_value.status_code = 403
            steps = [{"trace": [{"screenshot_id": "img-1"}]}]
            _, _, ok = github_utils_module._get_screenshot_bytes(session, steps)
        self.assertFalse(ok)

    def test_success_returns_image_bytes_and_id(self):
        session = MagicMock()
        session.get.return_value.status_code = 200
        session.get.return_value.text = '"https://blobstore/img"'
        with patch("github_utils.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b"PNG_DATA"
            steps = [{"trace": [{"screenshot_id": "img-1"}]}]
            img_bytes, returned_id, ok = github_utils_module._get_screenshot_bytes(session, steps)
        self.assertTrue(ok)
        self.assertEqual(img_bytes, b"PNG_DATA")
        self.assertEqual(returned_id, "img-1")


class UploadScreenshotToRepoTests(unittest.TestCase):
    def test_returns_permanent_url_on_success(self):
        with patch("github_utils.requests.put") as mock_put:
            mock_put.return_value.status_code = 201
            mock_put.return_value.json.return_value = {"commit": {"sha": "deadbeef"}}
            url = github_utils_module.upload_screenshot_to_repo(
                image_bytes=b"PNG",
                image_id="img-1",
                github_token="tok",
                repo="org/myrepo",
                branch_name="foreai-screenshot-abc",
            )
        self.assertIn("deadbeef", url)
        self.assertIn("img-1.png", url)
        self.assertIn("org/myrepo", url)

    def test_returns_none_on_non_201(self):
        with patch("github_utils.requests.put") as mock_put:
            mock_put.return_value.status_code = 422
            mock_put.return_value.json.return_value = {"message": "already exists"}
            url = github_utils_module.upload_screenshot_to_repo(
                image_bytes=b"PNG",
                image_id="img-1",
                github_token="tok",
                repo="org/myrepo",
                branch_name="foreai-screenshot-abc",
            )
        self.assertIsNone(url)


class PostImageCommentTests(unittest.TestCase):
    def test_posts_comment_and_returns_url(self):
        with patch("github_utils.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "html_url": "https://github.com/org/repo/issues/1#comment-1"
            }
            mock_post.return_value.raise_for_status = MagicMock()
            url = github_utils_module.post_image_comment(
                permanent_url="https://raw.githubusercontent.com/org/repo/sha/path.png",
                filename="img-1",
                github_token="tok",
                repo="org/repo",
                issue_number=1,
            )
        self.assertEqual(url, "https://github.com/org/repo/issues/1#comment-1")
        _, kwargs = mock_post.call_args
        self.assertIn("img-1", kwargs["json"]["body"])


class CreateGithubIssuesForRunsTests(unittest.TestCase):
    """Tests for create_github_issues_for_runs (public entry point)."""

    def test_skips_when_github_token_missing(self):
        session = requests.Session()
        with patch.dict(os.environ, {}, clear=True):
            with patch("builtins.print") as mock_print:
                github_utils_module.create_github_issues_for_runs(session, ["run-id"])
                mock_print.assert_called_once_with(
                    "Warning: GITHUB_TOKEN is not set; cannot create issue.")

    def test_skips_when_github_repository_missing(self):
        session = requests.Session()
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True):
            with patch("builtins.print") as mock_print:
                github_utils_module.create_github_issues_for_runs(session, ["run-id"])
                mock_print.assert_called_once_with(
                    "Warning: GITHUB_REPOSITORY is not set; cannot create issues.")

    def test_skips_when_github_sha_missing(self):
        session = requests.Session()
        env = {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "org/repo"}
        with patch.dict(os.environ, env, clear=True):
            with patch("builtins.print") as mock_print:
                github_utils_module.create_github_issues_for_runs(session, ["run-id"])
                mock_print.assert_called_once_with(
                    "Warning: GITHUB_SHA is not set; cannot create screenshot branch.")

    def test_creates_and_deletes_screenshot_branch(self):
        session = requests.Session()
        env = {
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPOSITORY": "org/repo",
            "GITHUB_SHA": "abc1234",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(github_utils_module, "_create_branch") as mock_create:
                with patch.object(github_utils_module, "_delete_branch") as mock_delete:
                    with patch.object(
                        github_utils_module, "_create_github_issue_for_run"
                    ):
                        github_utils_module.create_github_issues_for_runs(session, ["r1"])
            mock_create.assert_called_once()
            mock_delete.assert_called_once()

    def test_deletes_branch_even_on_exception(self):
        session = requests.Session()
        env = {
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPOSITORY": "org/repo",
            "GITHUB_SHA": "abc1234",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(github_utils_module, "_create_branch"):
                with patch.object(github_utils_module, "_delete_branch") as mock_delete:
                    with patch.object(
                        github_utils_module,
                        "_create_github_issue_for_run",
                        side_effect=RuntimeError("boom"),
                    ):
                        with self.assertRaises(RuntimeError):
                            github_utils_module.create_github_issues_for_runs(
                                session, ["r1"])
            mock_delete.assert_called_once()

    def test_calls_create_issue_for_each_run(self):
        session = requests.Session()
        env = {
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPOSITORY": "org/repo",
            "GITHUB_SHA": "abc1234",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(github_utils_module, "_create_branch"):
                with patch.object(github_utils_module, "_delete_branch"):
                    with patch.object(
                        github_utils_module, "_create_github_issue_for_run"
                    ) as mock_create_issue:
                        github_utils_module.create_github_issues_for_runs(
                            session, ["r1", "r2", "r3"])
        self.assertEqual(mock_create_issue.call_count, 3)
        called_run_ids = [call.args[1] for call in mock_create_issue.call_args_list]
        self.assertEqual(called_run_ids, ["r1", "r2", "r3"])


if __name__ == "__main__":
    unittest.main()
