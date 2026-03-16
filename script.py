"""This script is the entry point for the Github action."""
import os
import sys

import requests

import issue_utils
import runner


with requests.Session() as session:
    success, output_msg, failed_run_ids = runner.run(session)

    if (not success and failed_run_ids and
        os.getenv("INPUT_CREATE_ISSUE_ON_FAILURE", "false").lower() == "true"):
        is_github = bool(os.getenv("GITHUB_TOKEN"))
        is_gitlab = bool(os.getenv("INPUT_GITLAB_TOKEN"))
        for failed_run_id in failed_run_ids:
            if is_github:
                issue_utils.create_github_issue_for_run(session, failed_run_id)
            elif is_gitlab:
                issue_utils.create_gitlab_issue_for_run(session, failed_run_id)
            else:
                print("Warning: No token found for issue creation; cannot create issue.")


def escape_github_output(value: str) -> str:
    """Escape special characters for GitHub Actions output."""
    value = value.replace("%", "%25")
    value = value.replace("\r", "%0D")
    value = value.replace("\n", "%0A")
    return value

# Set the output - even for failures.
github_output = os.getenv("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a", encoding="utf-8") as fh:
        print(f"result={escape_github_output(output_msg)}", file=fh)
else:
    print(escape_github_output(output_msg))

if not success:
    sys.exit(output_msg)
