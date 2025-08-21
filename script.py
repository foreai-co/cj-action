"""This script is the entry point for the Github action."""
import os
import sys

import requests

import runner


session = requests.Session()
success, output_msg = runner.run(session)

if not success:
    sys.exit(output_msg)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output_msg}", file=fh)
