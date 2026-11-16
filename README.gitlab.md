# Critical Journey GitLab CI/CD Component

This GitLab CI/CD component runs the Critical Journey script inside a Docker container.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `test_id` | No* | | ID of the test to be run. Either this or `collection_id` should be provided. |
| `collection_id` | No* | | ID of the collection to be run. |
| `test_suite_id` | No | | Older name of `collection_id`, kept for existing pipelines. Despite its name it takes the ID of a collection. If both are set, `collection_id` is used. |
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
    inputs:
      test_id: "my-test-id"
      service_account_key: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
```

## Example Usage for running a collection
```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/critical-journey@<version>
    inputs:
      collection_id: "my-collection-id"
      service_account_key: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
      wait_timeout_seconds: "360"
      website_url_override: "https://beta-dev.my-awesome.com/2"
      variable_overrides: '{ "3f2504e0-4f89-11d3-9a0c-0305e82c3301": { "kind": "non_secret", "value": "value1" } }'
```

## Example Usage with automatic GitLab issue creation on failure
Requires a `GITLAB_TOKEN` CI/CD variable.
```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/critical-journey@<version>
    inputs:
      collection_id: "my-collection-id"
      service_account_key: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
      create_issue_on_failure: "true"
```

## Upload app component

`gitlab.com/foreai-co/cj-action/upload-app` uploads a mobile app to Critical Journey.

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `service_account_key` | Yes | | Your service account key to access fore.ai Critical Journey. |
| `app_file_path` | Yes | | Path to the app to upload: an `.apk`, an `.ipa` or a `.zip` holding an iOS simulator build. The file name may only hold lowercase letters, digits and underscores, plus one dot before the extension, and be at most 100 characters long, e.g. `my_app_1_4_3.apk`. |
| `app_name` | No | | Name of the app to upload the file to. Defaults to the app with the same package or bundle ID, or a new app named after it. |
| `app_tags` | No | `latest` | Tags of the app to point at the uploaded file, separated by commas, e.g. `latest, 1.4.3`. Setting tags replaces the default, so list `latest` too to keep moving it. |
| `organization_id` | No | | ID of the organization to upload the app to. Needed only if the service account belongs to more than one. |

```yaml
include:
  - component: gitlab.com/foreai-co/cj-action/upload-app@<version>
    inputs:
      service_account_key: $CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY
      app_file_path: "my_app.apk"
      app_name: "My App"
      app_tags: "latest, $CI_COMMIT_SHORT_SHA"
```

The tests of the Critical Journey component then run on the upload if they use the app's `latest` tag; set `app_name_override` and `app_platform_override` to run them on another app or tag.
