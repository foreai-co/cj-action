"""Business logic for the upload-app action."""
import os
import re

import requests

import runner


def _get_app_tags_from_env() -> list[str]:
    """Reads the tags to point at the uploaded app file, separated by commas or newlines.

    Defaults to the latest tag, so tests that run on it pick up the upload.
    """
    tags = os.getenv("INPUT_APP_TAGS", runner.DEFAULT_APP_TAG)
    return [tag.strip() for tag in re.split(r"[,\n]", tags) if tag.strip()]


def _get_org_id(session: requests.Session) -> str:
    """Returns the organization to upload to: the given one, else the service account's only one."""
    org_id = os.getenv("INPUT_ORGANIZATION_ID", "").strip()
    if org_id:
        return org_id
    response = session.get(f"{runner.get_backend_url()}/auth/get-user-organizations")
    if response.status_code != 200:
        raise ValueError(f"Failed to get the service account's organization: {response.text}")
    orgs = [details["organization"] for details in response.json()]
    if len(orgs) != 1:
        org_list = ", ".join(f"{org['name']} ({org['org_id']})" for org in orgs)
        raise ValueError(
            f"The service account belongs to {len(orgs)} organizations, set organization_id "
            f"to the one to upload to: {org_list}"
        )
    return orgs[0]["org_id"]


def _upload_app_file(
        session: requests.Session,
        app_file_path: str,
        app_name: str,
        tags: list[str]
    ) -> dict:
    """Uploads an app file (.apk, .ipa or a zipped iOS simulator build) to the org's apps.

    Without an app name, the backend files it under the app with the same package or
    bundle id, or a new app named after it.

    Returns:
        The uploaded app file.
    """
    org_id = _get_org_id(session)
    file_name = os.path.basename(app_file_path)
    form = {"file_name": file_name, "tags": tags}
    if app_name:
        form["app_name"] = app_name
    with open(app_file_path, "rb") as app_file:
        response = session.post(
            f"{runner.get_backend_url()}/organizations/{org_id}/app-files",
            data=form,
            files={"file": (file_name, app_file, "application/octet-stream")},
            # The session sends JSON by default; None drops its Content-Type so that
            # requests sets the multipart one.
            headers={"Content-Type": None},
        )
    if response.status_code != 201:
        raise ValueError(f"Failed to upload app file: {response.text}")
    return response.json()


def upload(session: requests.Session) -> tuple[bool, str, dict[str, str]]:
    """Uploads the app file the action is given.

    Args:
        session: requests.Session object. The caller is responsible for closing it.

    Returns:
        Tuple[bool, str, dict[str, str]]:
            - First element: Whether the upload was successful.
            - Second element: Message shown in the output.
            - Third element: The action's other outputs, i.e. the ``app_file_id``.
    """
    service_account_key = os.getenv("INPUT_SERVICE_ACCOUNT_KEY", "")
    app_file_path = os.getenv("INPUT_APP_FILE_PATH", "").strip()

    if not service_account_key:
        return False, "Failed: Service account key should be provided.", {}
    if not app_file_path:
        return False, "Failed: app_file_path should be provided.", {}
    if not os.path.isfile(app_file_path):
        return False, f"Failed: App file not found: {app_file_path}", {}

    try:
        if not runner.login_service_account(session, service_account_key):
            return False, "Failed to login service account.", {}

        app_file = _upload_app_file(
            session,
            app_file_path,
            app_name=os.getenv("INPUT_APP_NAME", "").strip(),
            tags=_get_app_tags_from_env(),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, f"Failed: {e}", {}

    msg = (
        f"Uploaded {app_file['file_name']} to app {app_file['app_name']} "
        f"as app file {app_file['app_file_id']}."
    )
    return True, msg, {"app_file_id": app_file["app_file_id"]}
