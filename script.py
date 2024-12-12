import os
import sys
import time

import requests

# Get input from environment variables
# These ENV vars are set by github actions based on action.yml
test_id = os.getenv("INPUT_TEST_ID", "")
service_account_key = os.getenv("INPUT_SERVICE_ACCOUNT_KEY", "")
MAX_FETCHES = 10
POLL_EVERY_SECONDS = 10.0
BACKEND_URL = "https://cj-backend.foreai.co"

def _get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def run() -> tuple[bool, str]:
    """Business logic for the action.

    Returns:
        tuple[bool, str]:
            - The first element says whether the test run was successful or not.
            - The second element is a message shown in the Github output.
    """
    if not (test_id and service_account_key):
        return False, "Failed: All required fields were not provided."

    # Login the serive account
    response = requests.post(f"{BACKEND_URL}/auth/login_service_account",
                             headers=_get_headers(service_account_key))
    if response.status_code != 200:
        return False, f"Failed to login service account: {response.json()}"

    jwt_token = response.text.replace('"', "")
    headers = _get_headers(jwt_token)    

    response = requests.post(f"{BACKEND_URL}/test-run/{test_id}",
                             headers=headers)

    if response.status_code != 201:
        # Failure: The test run could not be created
        return False, f"Failed to create test run: {response.json()}"

    test_run_id = response.json()

    for _ in range(MAX_FETCHES):
        run_status_response = requests.get(
            f"{BACKEND_URL}/test-run/{test_run_id}", headers=headers)
        run_status_response_json = run_status_response.json()
        status = run_status_response_json["status"]
        if status == "passed":
            return True, "Test passed!"
        if status == "failed":
            return False, run_status_response_json["error_message"]

        time.sleep(POLL_EVERY_SECONDS)
    return False, "Timed out waiting for test result!"


success, output_msg = run()

if not success:
    sys.exit(output_msg)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output_msg}", file=fh)
