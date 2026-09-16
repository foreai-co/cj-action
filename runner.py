"""This script is the entry point for the Github action."""
import datetime
import json
import os
import time
from math import ceil

import requests

DEFAULT_BACKEND_URL = "https://cj-backend.foreai.co"
DEFAULT_APP_URL = "https://app.foreai.co"


def get_backend_url() -> str:
    """Returns the backend URL, honouring an optional override.

    The default should be used in almost all cases; the override exists for
    internal purposes only.
    """
    return os.getenv("INPUT_BACKEND_URL_OVERRIDE", "").strip().rstrip("/") or DEFAULT_BACKEND_URL


def get_app_url() -> str:
    """Returns the app URL used to build result links, honouring an optional override.

    Must be kept consistent with the backend URL, otherwise the reported links
    point at an environment that does not know the referenced IDs.
    """
    return os.getenv("INPUT_APP_URL_OVERRIDE", "").strip().rstrip("/") or DEFAULT_APP_URL


def _get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def _create_run_settings_from_env() -> dict:
    """Creates run settings from environment variables."""
    run_settings = {}
    website_url_override = os.getenv("INPUT_WEBSITE_URL_OVERRIDE", "")
    variable_overrides = os.getenv("INPUT_VARIABLE_OVERRIDES", "")
    if website_url_override:
        run_settings["website_url_override"] = website_url_override
    if variable_overrides:
        try:
            run_settings["variable_overrides"] = json.loads(variable_overrides)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in variable_overrides: {e}") from e
    browser_type_override = os.getenv("INPUT_BROWSER_TYPE_OVERRIDE", "")
    if browser_type_override:
        run_settings["browser_type_override"] = browser_type_override.lower()
    return run_settings

def _login_service_account(session: requests.Session, service_account_key: str) -> bool:
    """Logs in the service account and updates session headers."""
    session.headers.update(_get_headers(service_account_key))
    response = session.post(f"{get_backend_url()}/auth/login_service_account")

    if response.status_code != 200:
        return False

    try:
        jwt_token = response.json()
        session.headers.update(_get_headers(jwt_token))
        return True
    except requests.JSONDecodeError:
        return False


def _poll_for_status(
        session: requests.Session,
        url: str,
        max_fetches: int,
        poll_every_seconds: float
    ) -> dict | None:
    """Polls for test run status until it completes or times out."""
    for _ in range(max_fetches):
        response = session.get(url)

        if response.status_code != 200:
            return None

        try:
            run_status = response.json()
            if run_status.get("status") in {"passed", "failed"}:
                return run_status
        except requests.JSONDecodeError:
            return None

        time.sleep(poll_every_seconds)

    return None  # Timed out


def _handle_single_test_run(
        session: requests.Session,
        test_case_id: str,
        run_settings: dict,
        max_fetches: int,
        poll_every_seconds: float
    ) -> tuple[bool, str, list[str]]:
    """Handles running a single test case."""
    json_payload = {}
    if len(run_settings.keys()) > 0:
        json_payload["settings"] = run_settings
    response = session.post(f"{get_backend_url()}/test-run/{test_case_id}", json=json_payload)

    if response.status_code != 201:
        return False, f"Failed to create test run: {response.json()}", []

    test_run_id = response.json()
    run_status = _poll_for_status(
        session, f"{get_backend_url()}/test-run/{test_run_id}", max_fetches, poll_every_seconds)

    if not run_status:
        return False, "Timed out waiting for test result!", []

    if run_status["status"] == "passed":
        return True, "Test passed!", []
    return False, run_status["error_message"], [test_run_id]


def _get_latest_group_run_statuses(
        run_response: dict,
        collection_id: str,
        created_at: str
    ) -> tuple[bool, dict]:
    """Gets the latest group run statuses."""
    linked_runs = run_response.get("linked_runs", [])

    project_id = run_response.get("test_suite_id")
    final_link = f"{get_app_url()}/collections/{project_id}/{collection_id}"
    final_link += f"?created_at={created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"

    if not linked_runs:
        raise ValueError("No linked runs found in the response")

    target_runs = [
        run for run in linked_runs
        if datetime.datetime.fromisoformat(run["created_at"]) == created_at
    ]

    if not target_runs:
        raise ValueError("No target run found in the response")

    status_counts = {"passed": 0, "failed": 0, "failed_run_ids": [], "final_link": final_link}
    for target_run in target_runs:
        if target_run["status"] == "passed":
            status_counts["passed"] += 1
        if target_run["status"] == "failed":
            status_counts["failed"] += 1
            status_counts["failed_run_ids"].append(target_run["_id"])

    if status_counts["passed"] + status_counts["failed"] != len(target_runs):
        return False, status_counts

    return True, status_counts


def _handle_bulk_test_run(
        session: requests.Session,
        collection_id: str,
        run_settings: dict,
        max_fetches: int,
        poll_every_seconds: float
    ) -> tuple[bool, str, list[str]]:
    """Handles running a full test suite collection."""
    response = session.post(
        f"{get_backend_url()}/test-suites/collection/{collection_id}/run-all",
        json=run_settings)
    
    response_json = response.json()

    if response.status_code != 200:
        return False, f"Failed to create test suite run: {response_json}", []

    try:
        created_at = datetime.datetime.fromisoformat(response_json)
    except ValueError:
        return False, "Invalid timestamp format in response", []

    for _ in range(max_fetches):
        response = session.get(
            f"{get_backend_url()}/test-suites/collection/{collection_id}")

        if response.status_code != 200:
            print(response.json())
            return False, "Error fetching test suite status.", []

        try:
            run_status_json = response.json()
            is_finished, group_status = _get_latest_group_run_statuses(
                run_response=run_status_json,
                collection_id=collection_id,
                created_at=created_at,
            )

            if not is_finished:
                time.sleep(poll_every_seconds)
                continue

            msg = f"{group_status['passed']} passed, {group_status['failed']} failed."
            msg += f" See status here: {group_status['final_link']}"

            return group_status["failed"] == 0, msg, group_status["failed_run_ids"]

        except requests.JSONDecodeError:
            time.sleep(poll_every_seconds)
            continue

    return False, "Timed out waiting for test suite result.", []


def run(session: requests.Session) -> tuple[bool, str, list[str]]:
    """Business logic for the action.
    Args:
        session: requests.Session object. The caller is responsible for closing it.

    Returns:
        Tuple[bool, str, list[str]]:
            - First element: Whether the test run was successful.
            - Second element: Message shown in the GitHub output.
            - Third element: List of failed test run IDs (empty if all passed or on error).
    """
    test_id = os.getenv("INPUT_TEST_ID", "")
    collection_id = os.getenv("INPUT_TEST_SUITE_ID", "")
    service_account_key = os.getenv("INPUT_SERVICE_ACCOUNT_KEY", "")

    wait_timeout_seconds = int(os.getenv("INPUT_WAIT_TIMEOUT_SECONDS", "300"))
    assert 30 <= wait_timeout_seconds <= 900, (
        "WAIT_TIMEOUT_SECONDS must be between 30 and 900 seconds"
    )
    poll_every_seconds = 10.0
    max_fetches = ceil(wait_timeout_seconds / poll_every_seconds)

    if not service_account_key:
        return False, "Failed: Service account key should be provided.", []

    try:
        run_settings = _create_run_settings_from_env()
    except ValueError as e:
        return False, f"Failed: {e}", []

    try:
        if not _login_service_account(session, service_account_key):
            return False, "Failed to login service account.", []

        if test_id:
            return _handle_single_test_run(
                session=session,
                test_case_id=test_id,
                run_settings=run_settings,
                max_fetches=max_fetches,
                poll_every_seconds=poll_every_seconds,
            )

        if not collection_id:
            return False, "Failed: Either test_id or test_suite_id should be provided.", []

        return _handle_bulk_test_run(
            session=session,
            collection_id=collection_id,
            run_settings=run_settings,
            max_fetches=max_fetches,
            poll_every_seconds=poll_every_seconds,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, f"Failed: {e}", []
