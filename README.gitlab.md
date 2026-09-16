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
| `create_issue_on_failure` | No | `false` | If `true`, automatically creates a GitLab issue when the test run fails. Requires `GITLAB_TOKEN` to be available. |

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
