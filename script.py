"""This script is the entry point for the Github action."""
import os
import sys

import requests

import github_utils
import runner


with requests.Session() as session:
    success, output_msg, failed_run_ids = runner.run(session)

    if (not success and failed_run_ids and
        os.getenv("INPUT_CREATE_ISSUE_ON_FAILURE", "false").lower() == "true"):
        github_utils.create_github_issues_for_runs(session, failed_run_ids)


def escape_github_output(value: str) -> str:
    """Escape special characters for GitHub Actions output."""
    value = value.replace("%", "%25")
    value = value.replace("\r", "%0D")
    value = value.replace("\n", "%0A")
    return value

# Set the output for the GitHub Action - even for failures.
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={escape_github_output(output_msg)}", file=fh)

if not success:
    sys.exit(output_msg)
