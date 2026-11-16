"""Sets the outputs of an action."""
import os


def escape_github_output(value: str) -> str:
    """Escape special characters for GitHub Actions output."""
    value = value.replace("%", "%25")
    value = value.replace("\r", "%0D")
    value = value.replace("\n", "%0A")
    return value


def set_outputs(outputs: dict[str, str]) -> None:
    """Sets the outputs on GitHub, or prints them elsewhere, e.g. on GitLab.

    The ``result`` output is printed as is, as the message of the run.
    """
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            for name, value in outputs.items():
                print(f"{name}={escape_github_output(value)}", file=fh)
        return
    for name, value in outputs.items():
        if name == "result":
            print(escape_github_output(value))
        else:
            print(f"{name}={escape_github_output(value)}")
