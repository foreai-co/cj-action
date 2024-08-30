import os
from datetime import datetime

# Get input from environment variables
instructions = os.getenv("INPUT_INSTRUCTIONS", "")

# Perform some processing
output = f"Input received: {instructions}. Current time is {datetime.now()}."

# Print the output
print(output)

# Set the output for the GitHub Action
with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
    print(f"result={output}", file=fh)
