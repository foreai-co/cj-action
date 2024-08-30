import os
import requests

# Get input from environment variables
website = os.getenv("INPUT_WEBSITE", "")
test_name = os.getenv("INPUT_TEST_NAME", "")
cj_token = os.getenv("INPUT_CJ_TOKEN", "")
instructions = os.getenv("INPUT_INSTRUCTIONS", "")

def run():
    if not (website and test_name and cj_token and instructions):
        return "Failed: All required fields were not provided."

    response = requests.post(
        "https://cj-backend.foreai.co/test-case/",
        headers={
            "Authorization": f"Bearer {cj_token}"},
        json = {
            "website": website,
            "name": test_name,
            "description": instructions,
        },
        headers = {
            "Authorization": f"Bearer {cj_token}",
            "Content-Type": "application/json"
        })

    if response.status_code == 201:
        # Success: The test case was created successfully
        return f"Test successfully generated. Visit: https://cj.foreai.co/{response.text}"
    else:
        return f"Failed to create test case: {response.json()}"

output = run()

print(output)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output}", file=fh)
