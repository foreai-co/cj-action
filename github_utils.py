"""Utilities for creating GitHub issues from test run failures."""
import base64
import os

import requests

from runner import BACKEND_URL


def _fetch_run_details(session: requests.Session, test_run_id: str) -> dict | None:
    """Fetches detailed information about a test run from the foreai API."""
    response = session.get(f"{BACKEND_URL}/test-run/{test_run_id}")
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except requests.JSONDecodeError:
        return None

def _build_screenshot_markdown(
    session: requests.Session,
    steps: list
) -> str:
    """Returns a markdown screenshot block from the last step, or empty string."""
    if not steps:
        return ""
    trace = steps[-1].get("trace", [])
    image_id = trace[0].get("screenshot_id") if trace else None
    if not image_id:
        return ""
    response = session.get(f"{BACKEND_URL}/images/run/{image_id}")
    if response.status_code != 200:
        return ""
    url = response.text.strip('"')  # API returns URL as a quoted string
    if not url:
        return ""
    return (
        "\n\n"
        f"[Screenshot from failing step]({url})"
    )

def _build_steps_markdown(steps: list) -> str:
    """Returns a markdown list of executed steps."""
    if not steps:
        return "No step information available"
    return "\n".join(
        f"{idx + 1}. **{step.get('action_name', 'Unknown')}** - "
        f"{'✅ Success' if step.get('success') else '❌ Failed'}"
        for idx, step in enumerate(steps)
    )


def _build_issue_body(
    run_details: dict,
    test_run_id: str,
    test_id: str,
    commit_sha: str,
    branch: str,
    run_url: str,
    steps_md: str,
    screenshot_markdown: str,
) -> str:
    """Assembles the full markdown body for the GitHub issue."""
    details_url = f"https://app.foreai.co/test-cases/details/{test_id}/runs?run={test_run_id}"
    settings = run_details.get("settings", {})
    viewport = (
        f"{settings.get('viewport_width_override', 'N/A')}"
        f"x{settings.get('viewport_height_override', 'N/A')}"
    )
    failing_step = run_details.get("failing_step_index")
    failing_step_str = str(failing_step + 1) if failing_step is not None else "N/A"
    created_at = run_details.get("created_at", "N/A")

    return f"""## Test Failure Report

**🔗 View Details:** {details_url}
**Test ID:** `{test_id}`
**Run ID:** `{test_run_id}`
**Status:** {run_details.get('status', 'N/A')}
**Failed at:** {created_at}
**Failing Step:** {failing_step_str}

### Error Details

**User-Friendly Error:**
```
{run_details.get('user_friendly_error', 'N/A')}
```

**Full Error Message:**
```
{run_details.get('error_message', 'N/A')}
```

### Test Configuration

- **Website URL Override:** {settings.get('website_url_override') or 'None'}
- **Browser:** {settings.get('browser_type_override') or 'Unknown'}
- **Viewport:** {viewport}
- **Platform:** {settings.get('platform') or 'Unknown'}

### Workflow Details

- **Commit:** {commit_sha}
- **Branch:** {branch}
- **Workflow Run:** {run_url}

### Steps Executed

{steps_md}{screenshot_markdown}
---
*This issue was automatically created by the Critical Journey GitHub Actions workflow.*"""


def _post_github_issue(
    github_token: str,
    github_repository: str,
    title: str,
    body: str,
) -> None:
    """Posts a new issue to the GitHub API and prints the result."""
    response = requests.post(
        f"https://api.github.com/repos/{github_repository}/issues",
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "title": title,
            "body": body,
            "labels": ["test-failure", "foreai"],
        },
        timeout=30,
    )
    if response.status_code == 201:
        print(f"Issue created: {response.json().get('html_url')}")
    else:
        print(f"Warning: Failed to create issue ({response.status_code}): {response.text}")


def create_github_issue_for_run(session: requests.Session, test_run_id: str) -> None:
    """Creates a GitHub issue with full details of a failed test run.

    Reads GITHUB_TOKEN, GITHUB_REPOSITORY, and standard GitHub Actions
    environment variables to build a rich issue body including step traces and
    a screenshot from the last executed step.
    """
    github_token = os.getenv("GITHUB_TOKEN", "")
    github_repository = os.getenv("GITHUB_REPOSITORY", "")
    github_server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    github_sha = os.getenv("GITHUB_SHA", "")
    github_ref = os.getenv("GITHUB_REF", "")

    if not github_token:
        print("Warning: GITHUB_TOKEN is not set; cannot create issue.")
        return
    if not github_repository:
        print("Warning: GITHUB_REPOSITORY is not set; cannot create issue.")
        return

    run_details = _fetch_run_details(session, test_run_id)
    if not run_details:
        print(f"Warning: Could not fetch details for run {test_run_id}; skipping issue creation.")
        return

    test_id = run_details.get("test_case_id", "")
    run_url = (
        f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
        if github_run_id else ""
    )
    commit_sha = github_sha[:7] if github_sha else ""
    branch = github_ref.replace("refs/heads/", "") if github_ref else ""

    steps = run_details.get("steps", [])
    issue_title = f"Test Failed: {run_details.get('user_friendly_error', 'Test execution failed')}"
    issue_body = _build_issue_body(
        run_details=run_details,
        test_run_id=test_run_id,
        test_id=test_id,
        commit_sha=commit_sha,
        branch=branch,
        run_url=run_url,
        steps_md=_build_steps_markdown(steps),
        screenshot_markdown=_build_screenshot_markdown(session, steps),
    )
    _post_github_issue(github_token, github_repository, issue_title, issue_body)
