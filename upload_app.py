"""This script is the entry point for the upload-app action."""
import sys

import requests

import github_output
import uploader


with requests.Session() as session:
    success, output_msg, outputs = uploader.upload(session)

# Set the output - even for failures.
github_output.set_outputs({**outputs, "result": output_msg})

if not success:
    sys.exit(output_msg)
