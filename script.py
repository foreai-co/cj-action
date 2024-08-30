import os
import sys
import requests

# Get input from environment variables
# These ENV vars are set by github actions based on action.yml
url = os.getenv("INPUT_URL", "")
test_name = os.getenv("INPUT_TEST_NAME", "")
cj_token = os.getenv("INPUT_CJ_TOKEN", "")
instructions = os.getenv("INPUT_INSTRUCTIONS", "")

def run() -> tuple[bool, str]:
    """Business logic for the action.

    Returns:
        tuple[bool, str]:
            - The first element says whether the test creation was success or not.
            - The second element is a message shown in the Github output.
    """
    if not (url and test_name and cj_token and instructions):
        return False, "Failed: All required fields were not provided."

    response = requests.post(
        "https://cj-backend.foreai.co/test-case/",
        json = {
            "website": url,
            "name": test_name,
            "description": instructions,
        },
        headers = {
            "Authorization": f"Bearer {cj_token}",
            "Content-Type": "application/json"
        })

    if response.status_code == 201:
        # Success: The test case was created successfully
        msg = f"Test successfully generated. Visit: https://cj.foreai.co/{response.json()}"
        return True, msg
    return False, f"Failed to create test case: {response.json()}"

success, output_msg = run()

if not success:
    sys.exit(output_msg)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output_msg}", file=fh)
