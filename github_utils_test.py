"""Tests for the github_utils module."""
import os
import unittest
from unittest.mock import patch

import requests

import github_utils as github_utils_module


class CreateGithubIssueTests(unittest.TestCase):
    """Integration-level tests for create_github_issue_for_run."""

    def test_skips_when_github_token_missing(self):
        """Prints a warning and returns early when GITHUB_TOKEN is not set."""
        session = requests.Session()
        with patch.dict(os.environ, {}, clear=True):
            with patch("builtins.print") as mock_print:
                github_utils_module.create_github_issue_for_run(session, "run-id")
                mock_print.assert_called_once_with(
                    "Warning: GITHUB_TOKEN is not set; cannot create issue.")

    def test_skips_when_github_repository_missing(self):
        """Prints a warning and returns early when GITHUB_REPOSITORY is not set."""
        session = requests.Session()
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=True):
            with patch("builtins.print") as mock_print:
                github_utils_module.create_github_issue_for_run(session, "run-id")
                mock_print.assert_called_once_with(
                    "Warning: GITHUB_REPOSITORY is not set; cannot create issue.")

    def test_skips_when_run_details_unavailable(self):
        """Prints a warning and returns early when run details cannot be fetched."""
        session = requests.Session()
        env = {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "org/repo"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(
                github_utils_module, "_fetch_run_details", return_value=None
            ):
                with patch("builtins.print") as mock_print:
                    github_utils_module.create_github_issue_for_run(session, "run-id")
                    mock_print.assert_called_once_with(
                        "Warning: Could not fetch details for run run-id; "
                        "skipping issue creation.")

    def test_orchestrates_helpers_and_posts_issue(self):
        """Builds the issue title and body from run details and calls _post_github_issue."""
        session = requests.Session()
        env = {
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPOSITORY": "org/repo",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_RUN_ID": "999",
            "GITHUB_SHA": "abc1234def",
            "GITHUB_REF": "refs/heads/main",
        }
        run_details = {
            "status": "failed",
            "user_friendly_error": "Button not found",
            "error_message": "ElementNotFound",
            "failing_step_index": 0,
            "created_at": "2025-01-01T00:00:00Z",
            "steps": [{"action_name": "Click", "success": False, "trace": []}],
            "settings": {},
            "test_case_id": "test-case-id",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(
                github_utils_module, "_fetch_run_details", return_value=run_details
            ):
                with patch.object(
                    github_utils_module, "_post_github_issue"
                ) as mock_post:
                    github_utils_module.create_github_issue_for_run(session, "run-id")
                    mock_post.assert_called_once()
                    title, body = mock_post.call_args[0][2], mock_post.call_args[0][3]
                    self.assertIn("Button not found", title)
                    self.assertIn("run-id", body)
                    self.assertIn("abc1234", body)
                    self.assertIn("main", body)


if __name__ == "__main__":
    unittest.main()
