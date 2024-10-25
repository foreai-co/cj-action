import os
import sys
import time
import requests

# Get input from environment variables
# These ENV vars are set by github actions based on action.yml
test_id = os.getenv("INPUT_TEST_ID", "")
cj_token = os.getenv("INPUT_TOKEN", "")
MAX_FETCHES = 10

def run() -> tuple[bool, str]:
    """Business logic for the action.

    Returns:
        tuple[bool, str]:
            - The first element says whether the test run was successful or not.
            - The second element is a message shown in the Github output.
    """
    if not (test_id and cj_token):
        return False, "Failed: All required fields were not provided."

    response = requests.post(
        f"https://cj-backend.foreai.co/test-run/{test_id}",
        headers = {
            "Authorization": f"Bearer {cj_token}",
            "Content-Type": "application/json"
        })

    if response.status_code != 201:
        # Failure: The test run could not be created
        return False, f"Failed to create test run: {response.json()}"

    test_run_id = response.json()

    for _ in range(MAX_FETCHES):
        run_status_response = requests.get(
            f"https://cj-backend.foreai.co/test-run/{test_run_id}",
            headers={
                "Authorization": f"Bearer {cj_token}",
                "Content-Type": "application/json"
            })
        status = run_status_response.json()["status"]
        if status == "passed":
            return True, "Test passed!"
        if status == "failed":
            return False, run_status_response.json()["error_message"]
        # Wait a few secs.
        time.sleep(10.0)
    return False, "Timed out waiting for test result!"


success, output_msg = run()

if not success:
    sys.exit(output_msg)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output_msg}", file=fh)
