"""Utilities for creating GitHub issues from test run failures."""
import base64
import os
import uuid

import requests

from runner import BACKEND_URL


def _make_screenshot_branch_name() -> str:
    return f"foreai-screenshot-{uuid.uuid4().hex[:12]}"


def _create_branch(github_token: str, repo: str, branch_name: str, sha: str) -> None:
    """Create a branch from the given SHA."""
    requests.post(
        f"https://api.github.com/repos/{repo}/git/refs",
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        timeout=10,
    )


def _delete_branch(github_token: str, repo: str, branch_name: str) -> None:
    """Delete a branch."""
    requests.delete(
        f"https://api.github.com/repos/{repo}/git/refs/heads/{branch_name}",
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )


def upload_screenshot_to_repo(
    image_bytes: bytes,
    image_id: str,
    github_token: str,
    repo: str,
    branch_name: str,
) -> str | None:
    """Upload screenshot to the given branch and return a permanent raw URL (via commit SHA)."""
    path = f"attachments/{image_id}.png"
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "message": f"Add screenshot {image_id}",
            "content": base64.b64encode(image_bytes).decode(),
            "branch": branch_name,
        },
        timeout=30,
    )
    if resp.status_code != 201:
        print(f"Warning: Failed to upload screenshot ({resp.json()})")
        return None
    commit_sha = resp.json()["commit"]["sha"]
    owner, repo_name = repo.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{repo_name}/{commit_sha}/{path}"


def _fetch_run_details(session: requests.Session, test_run_id: str) -> dict | None:
    """Fetches detailed information about a test run from the foreai API."""
    response = session.get(f"{BACKEND_URL}/test-run/{test_run_id}")
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except requests.JSONDecodeError:
        return None


def _get_screenshot_bytes(session: requests.Session, steps: list) -> tuple[bytes, str, bool]:
    """Returns (image_bytes, image_id, success) for the screenshot from the last step."""
    if not steps:
        return b"", "", False
    trace = steps[-1].get("trace", [])
    image_id = trace[0].get("screenshot_id") if trace else None
    if not image_id:
        return b"", "", False
    url_response = session.get(f"{BACKEND_URL}/images/run/{image_id}")
    if url_response.status_code != 200:
        return b"", "", False
    blobstore_url = url_response.text.strip('"')
    img_response = requests.get(blobstore_url, timeout=10)
    if img_response.status_code != 200:
        return b"", "", False
    return img_response.content, image_id, True


def post_image_comment(
    permanent_url: str,
    filename: str,
    github_token: str,
    repo: str,
    issue_number: int,
    alt_text: str = "",
) -> str | None:
    """Post a comment on the GitHub issue embedding the image."""
    owner, repo_name = repo.split("/", 1)
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}/comments"

    alt = alt_text or filename
    comment_header = f"Screenshot: {filename}"
    body = f'{comment_header}\n<img width="800" height="480" alt="{alt}" src="{permanent_url}">'

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    resp = requests.post(api_url, headers=headers, json={"body": body}, timeout=30)
    resp.raise_for_status()
    comment = resp.json()
    print(f"  Comment posted: {comment['html_url']}")
    return comment["html_url"]


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

{steps_md}
---
*This issue was automatically created by the Critical Journey GitHub Actions workflow.*"""


def _post_github_issue(
    github_token: str,
    github_repository: str,
    title: str,
    body: str,
) -> int | None:
    """Posts a new issue to the GitHub API and returns the issue number."""
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
        issue = response.json()
        print(f"Issue created: {issue.get('html_url')}")
        return issue.get("number")
    print(f"Warning: Failed to create issue ({response.status_code}): {response.text}")
    return None
    

def _create_github_issue_for_run(
    session: requests.Session,
    test_run_id: str,
    github_token: str,
    github_repository: str,
    screenshot_branch: str,
    github_sha: str,
    github_ref: str,
    github_run_id: str,
    github_server_url: str,
) -> None:
    """Creates a GitHub issue with full details of a failed test run."""
    run_details = _fetch_run_details(session, test_run_id)
    if not run_details:
        print(
            f"Warning: Could not fetch details for run {test_run_id}; skipping issue creation.")
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
    )
    issue_number = _post_github_issue(
        github_token, github_repository, issue_title, issue_body)

    if issue_number:
        image_bytes, image_id, has_screenshot = _get_screenshot_bytes(
            session, steps)
        if has_screenshot:
            try:
                github_url = upload_screenshot_to_repo(
                    image_bytes=image_bytes,
                    image_id=image_id,
                    github_token=github_token,
                    repo=github_repository,
                    branch_name=screenshot_branch,
                )
                if github_url:
                    post_image_comment(
                        permanent_url=github_url,
                        filename=image_id,
                        github_token=github_token,
                        repo=github_repository,
                        issue_number=issue_number,
                        alt_text="Trace Screenshot",
                    )
            except Exception as e:
                print(f"Warning: Failed to post screenshot comment: {e}")


def create_github_issues_for_runs(session: requests.Session, failed_run_ids: list[str]) -> None:
    """Creates GitHub issues for all failed runs, sharing a single temporary screenshot branch."""
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
        print("Warning: GITHUB_REPOSITORY is not set; cannot create issues.")
        return
    if not github_sha:
        print("Warning: GITHUB_SHA is not set; cannot create screenshot branch.")
        return

    screenshot_branch = _make_screenshot_branch_name()
    _create_branch(github_token, github_repository, screenshot_branch, github_sha)
    try:
        for test_run_id in failed_run_ids:
            _create_github_issue_for_run(
                session, test_run_id, github_token, github_repository, screenshot_branch,
                github_sha, github_ref, github_run_id, github_server_url,
            )
    finally:
        _delete_branch(github_token, github_repository, screenshot_branch)
