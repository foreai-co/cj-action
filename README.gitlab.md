# Critical Journey GitLab CI/CD Component

This GitLab CI/CD component runs the Critical Journey script inside a Docker container.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `test_id` | No* | | ID of the test to be run. Either this or `test_suite_id` should be provided. |
| `test_suite_id` | No* | | ID of the test suite to be run. |
| `service_account_key` | Yes | | Your service account key to access fore.ai Critical Journey. |
| `wait_timeout_seconds` | No | `300` | Maximum seconds to wait for the test to complete. Must be between 30 and 900. |
| `website_url_override` | No | | Overrides the base website URL used during test execution. |
| `variable_overrides` | No | | Overrides test suite variables. Must be a valid JSON string keyed by variable definition ID, each value an override object. |
| `browser_type_override` | No | `chromium` | Browser engine to run the test with: `chromium`, `firefox`, or `webkit`. |
| `app_file_id_override` | No | | ID of the app file to run the tests on instead of their own app. |
| `app_name_override` | No | | Name of the app to run the tests on instead of their own app. Requires `app_platform_override`. |
| `app_platform_override` | No | | Platform of the app in `app_name_override`: `android` or `ios`. |
| `app_tag_override` | No | `latest` | Tag of the app in `app_name_override` whose file the tests run on. |
| `create_issue_on_failure` | No | `false` | If `true`, automatically creates a GitLab issue when the test run fails. Requires `GITLAB_TOKEN` to be available. |
| `fail_on_skipped` | No | `false` | If `true`, the job fails when any test in the run was skipped. |
| `fail_on_not_runnable` | No | `true` | If `true`, the job fails when any test could not be run, e.g. because it is still generating. |

Cancelled and aborted runs always fail the job.

## Example Usage for running a single test
```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/critical-journey@<version>

run-critical-journey:
  variables:
    TEST_ID: "my-test-id"
    SERVICE_ACCOUNT_KEY: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
```

## Example Usage for running a test suite
```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/critical-journey@<version>

run-critical-journey:
  variables:
    TEST_SUITE_ID: "my-test-suite-id"
    SERVICE_ACCOUNT_KEY: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
    WAIT_TIMEOUT_SECONDS: "360"
    WEBSITE_URL_OVERRIDE: "https://beta-dev.my-awesome.com/2"
    VARIABLE_OVERRIDES: '{ "3f2504e0-4f89-11d3-9a0c-0305e82c3301": { "kind": "non_secret", "value": "value1" } }'
```

## Example Usage with automatic GitLab issue creation on failure
```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/critical-journey@<version>

run-critical-journey:
  variables:
    TEST_SUITE_ID: "my-test-suite-id"
    SERVICE_ACCOUNT_KEY: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
    CREATE_ISSUE_ON_FAILURE: "true"
    GITLAB_TOKEN: $GITLAB_TOKEN
```

## Upload app component

`gitlab.com/foreai-co/cj-action/upload-app` uploads a mobile app to Critical Journey.

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `service_account_key` | Yes | | Your service account key to access fore.ai Critical Journey. |
| `app_file_path` | Yes | | Path to the app to upload: an `.apk`, an `.ipa` or a `.zip` holding an iOS simulator build. |
| `app_name` | No | | Name of the app to upload the file to. Defaults to the app with the same package or bundle ID, or a new app named after it. |
| `app_tags` | No | `latest` | Tags of the app to point at the uploaded file, separated by commas, e.g. `latest, 1.4.3`. Setting tags replaces the default, so list `latest` too to keep moving it. |

```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/upload-app@<version>
    inputs:
      service_account_key: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
      app_file_path: "app/build/outputs/apk/debug/app-debug.apk"
      app_name: "My App"
      app_tags: "latest, $CI_COMMIT_SHORT_SHA"
```

The tests of the Critical Journey component then run on the upload if they use the app's `latest` tag; set `app_name_override` and `app_platform_override` to run them on another app or tag.
