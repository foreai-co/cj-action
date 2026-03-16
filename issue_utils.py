"""Utilities for creating issues from test run failures."""
import os
import urllib.parse

import requests

from runner import BACKEND_URL


def fetch_run_details(session: requests.Session, test_run_id: str) -> dict | None:
    """Fetches detailed information about a test run from the foreai API."""
    response = session.get(f"{BACKEND_URL}/test-run/{test_run_id}")
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except requests.JSONDecodeError:
        return None


def build_steps_markdown(steps: list) -> str:
    """Returns a markdown list of executed steps."""
    if not steps:
        return "No step information available"
    return "\n".join(
        f"{idx + 1}. **{step.get('action_name', 'Unknown')}** - "
        f"{'✅ Success' if step.get('success') else '❌ Failed'}"
        for idx, step in enumerate(steps)
    )


def build_issue_body(
    run_details: dict,
    test_run_id: str,
    test_id: str,
    commit_sha: str,
    branch: str,
    workflow_url: str,
    steps_md: str,
) -> str:
    """Assembles the full markdown body for an issue."""
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
- **Workflow Run:** {workflow_url}

### Steps Executed

{steps_md}
---
*This issue was automatically created by the Critical Journey action.*"""


def _prepare_issue_content(
    session: requests.Session,
    test_run_id: str,
    workflow_url: str,
    commit_sha: str,
    branch: str,
) -> tuple[str, str] | None:
    """Fetches run details and builds issue title and body. Returns None on failure."""
    run_details = fetch_run_details(session, test_run_id)
    if not run_details:
        print(f"Warning: Could not fetch details for run {test_run_id}; skipping issue creation.")
        return None
    test_id = run_details.get("test_case_id", "")
    short_sha = commit_sha[:7] if commit_sha else ""
    title = f"Test Failed: {run_details.get('user_friendly_error', 'Test execution failed')}"
    body = build_issue_body(
        run_details=run_details,
        test_run_id=test_run_id,
        test_id=test_id,
        commit_sha=short_sha,
        branch=branch,
        workflow_url=workflow_url,
        steps_md=build_steps_markdown(run_details.get("steps", [])),
    )
    return title, body


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


def _post_gitlab_issue(
    gitlab_token: str,
    gitlab_url: str,
    project_id: str,
    title: str,
    body: str,
) -> None:
    """Posts a new issue to the GitLab API and prints the result."""
    encoded_project_id = urllib.parse.quote(project_id, safe="")
    response = requests.post(
        f"{gitlab_url}/api/v4/projects/{encoded_project_id}/issues",
        headers={
            "PRIVATE-TOKEN": gitlab_token,
            "Content-Type": "application/json",
        },
        json={
            "title": title,
            "description": body,
            "labels": "test-failure,foreai",
        },
        timeout=30,
    )
    if response.status_code == 201:
        print(f"GitLab issue created: {response.json().get('web_url')}")
    else:
        print(f"Warning: Failed to create GitLab issue ({response.status_code}): {response.text}")


def create_github_issue_for_run(session: requests.Session, test_run_id: str) -> None:
    """Creates a GitHub issue with full details of a failed test run."""
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

    run_url = (
        f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
        if github_run_id else ""
    )
    branch = github_ref.replace("refs/heads/", "") if github_ref else ""

    content = _prepare_issue_content(session, test_run_id, run_url, github_sha, branch)
    if not content:
        return
    title, body = content
    _post_github_issue(github_token, github_repository, title, body)


def create_gitlab_issue_for_run(session: requests.Session, test_run_id: str) -> None:
    """Creates a GitLab issue with full details of a failed test run."""
    gitlab_token = os.getenv("INPUT_GITLAB_TOKEN", "")
    project_id = os.getenv("INPUT_GITLAB_PROJECT_ID", "")
    gitlab_url = os.getenv("CI_SERVER_URL", "https://gitlab.com").rstrip("/")
    pipeline_url = os.getenv("CI_PIPELINE_URL", "")
    commit_sha = os.getenv("CI_COMMIT_SHA", "")
    branch = os.getenv("CI_COMMIT_REF_NAME", "")

    if not gitlab_token:
        print("Warning: INPUT_GITLAB_TOKEN is not set; cannot create GitLab issue.")
        return
    if not project_id:
        print("Warning: INPUT_GITLAB_PROJECT_ID is not set; cannot create GitLab issue.")
        return

    content = _prepare_issue_content(session, test_run_id, pipeline_url, commit_sha, branch)
    if not content:
        return
    title, body = content
    _post_gitlab_issue(gitlab_token, gitlab_url, project_id, title, body)
