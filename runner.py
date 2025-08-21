"""This script is the entry point for the Github action."""
import json
import os
import time
from math import ceil

import requests

# Get input from environment variables
# These ENV vars are set by github actions based on action.yml
TEST_ID = os.getenv("INPUT_TEST_ID", "")
COLLECTION_ID = os.getenv("INPUT_TEST_SUITE_ID", "")
SERVICE_ACCOUNT_KEY = os.getenv("INPUT_SERVICE_ACCOUNT_KEY", "")
WEBSITE_URL_OVERRIDE = os.getenv("INPUT_WEBSITE_URL_OVERRIDE", "")
PARAMS_OVERRIDE = os.getenv("INPUT_PARAMS_OVERRIDE", "")

WAIT_TIMEOUT_SECONDS = int(os.getenv("INPUT_WAIT_TIMEOUT_SECONDS", "100"))
assert 30 <= WAIT_TIMEOUT_SECONDS <= 900, "WAIT_TIMEOUT_SECONDS must be between 30 and 900 seconds"
POLL_EVERY_SECONDS = 10.0
MAX_FETCHES = ceil(WAIT_TIMEOUT_SECONDS / POLL_EVERY_SECONDS)

BACKEND_URL = "https://cj-backend.foreai.co"

def _get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def _create_run_settings_from_env() -> dict:
    """Creates run settings from environment variables."""
    run_settings = {}
    if WEBSITE_URL_OVERRIDE:
        run_settings["website_url_override"] = WEBSITE_URL_OVERRIDE
    if PARAMS_OVERRIDE:
        try:
            run_settings["parameter_overrides"] = json.loads(PARAMS_OVERRIDE)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in params_override: {e}") from e
    return run_settings

def _login_service_account(session: requests.Session) -> bool:
    """Logs in the service account and updates session headers."""
    session.headers.update(_get_headers(SERVICE_ACCOUNT_KEY))
    response = session.post(f"{BACKEND_URL}/auth/login_service_account")

    if response.status_code != 200:
        return False

    try:
        jwt_token = response.json()
        session.headers.update(_get_headers(jwt_token))
        return True
    except requests.JSONDecodeError:
        return False


def _poll_for_status(session: requests.Session, url: str) -> dict | None:
    """Polls for test run status until it completes or times out."""
    for _ in range(MAX_FETCHES):
        response = session.get(url)

        if response.status_code != 200:
            return None

        try:
            run_status = response.json()
            if run_status.get("status") in {"passed", "failed"}:
                return run_status
        except requests.JSONDecodeError:
            return None

        time.sleep(POLL_EVERY_SECONDS)

    return None  # Timed out


def _handle_single_test_run(
        session: requests.Session, test_case_id: str, run_settings: dict) -> tuple[bool, str]:
    """Handles running a single test case."""
    json_payload = {}
    if len(run_settings.keys()) > 0:
        json_payload["settings"] = run_settings
    response = session.post(f"{BACKEND_URL}/test-run/{test_case_id}", json=json_payload)

    if response.status_code != 201:
        return False, f"Failed to create test run: {response.json()}"

    test_run_id = response.json()
    run_status = _poll_for_status(
        session, f"{BACKEND_URL}/test-run/{test_run_id}")

    if not run_status:
        return False, "Timed out waiting for test result!"

    if run_status["status"] == "passed":
        return True, "Test passed!"
    return False, run_status["error_message"]


def _get_latest_group_run_statuses(run_response: dict, collection_id: str) -> tuple[bool, dict]:
    linked_runs = run_response.get("linked_runs", [])

    project_id = run_response.get("test_suite_id")
    final_link = f"https://cj.foreai.co/collections/{project_id}/{collection_id}"

    if not linked_runs:
        raise ValueError("No linked runs found in the response")

    # Find the max timestamp
    max_time = max(run["created_at"] for run in linked_runs)

    # Keep only runs that match the max timestamp
    latest_runs = [run for run in linked_runs if run["created_at"] == max_time]

    # Count passed vs failed
    status_counts = {"passed": 0, "failed": 0, "final_link": final_link}
    for latest_run in latest_runs:
        if latest_run["status"] == "passed":
            status_counts["passed"] += 1
        if latest_run["status"] == "failed":
            status_counts["failed"] += 1

    if status_counts["passed"] + status_counts["failed"] != len(latest_runs):
        return False, status_counts

    return True, status_counts


def _handle_bulk_test_run(
        session: requests.Session, collection_id: str, run_settings: dict) -> tuple[bool, str]:
    """Handles running a full test suite collection."""
    response = session.post(
        f"{BACKEND_URL}/test-suites/collection/{collection_id}/run-all",
        json=run_settings)

    if response.status_code != 200:
        return False, f"Failed to create test suite run: {response.json()}"

    for _ in range(MAX_FETCHES):
        response = session.get(
            f"{BACKEND_URL}/test-suites/collection/{collection_id}")

        if response.status_code != 200:
            print(response.json())
            return False, "Error fetching test suite status."

        try:
            run_status_json = response.json()
            is_finished, group_status = _get_latest_group_run_statuses(
                run_status_json, collection_id)

            if not is_finished:
                time.sleep(POLL_EVERY_SECONDS)
                continue

            msg = f"{group_status['passed']} passed, {group_status['failed']} failed."
            msg += f" See status here: {group_status['final_link']}"

            return group_status["failed"] == 0, msg

        except requests.JSONDecodeError:
            time.sleep(POLL_EVERY_SECONDS)
            continue

    return False, "Timed out waiting for test suite result."


def run(session: requests.Session) -> tuple[bool, str]:
    """Business logic for the action.
    Args:
        session: requests.Session object.

    Returns:
        Tuple[bool, str]: 
            - First element: Whether the test run was successful.
            - Second element: Message shown in the GitHub output.
    """
    if not SERVICE_ACCOUNT_KEY:
        return False, "Failed: Service account key should be provided."

    try:
        run_settings = _create_run_settings_from_env()
    except ValueError as e:
        return False, f"Failed: {e}"

    try:
        if not _login_service_account(session):
            return False, "Failed to login service account."

        if TEST_ID:
            return _handle_single_test_run(session, TEST_ID, run_settings)

        if not COLLECTION_ID:
            return False, "Failed: Either test_id or test_suite_id should be provided."

        return _handle_bulk_test_run(session, COLLECTION_ID, run_settings)

    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, f"Failed: {e}"

    finally:
        session.close()
