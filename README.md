# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `test_id`: ID of the test to be run. Either this or `test_suite_id` should be provided.
- `test_suite_id`: ID of the test suite to be run.
- `service_account_key`: Your service account key to access fore ai Critical Journey.
- `wait_timeout_seconds`: (Optional) Maximum number of seconds to wait for the test to complete. Default is 300 seconds. Must be between 30 and 900 seconds (inclusive).
- `website_url_override`: (Optional) Allows overriding the base website URL used during test execution.  
- `variable_overrides`: (Optional) Allows overriding test suite variables for this run. This should be a valid json string mapping each variable definition ID to an override object, e.g. `{ "0b5f...": { "kind": "non_secret", "value": "abc" } }`.
- `browser_type_override`: (Optional) Browser engine to run the test with: 'chromium', 'firefox', or 'webkit'. Defaults to 'chromium' if not specified.
- `app_file_path`: (Optional) Path to a mobile app to upload before running: an `.apk`, an `.ipa` or a `.zip` holding an iOS simulator build. Relative paths are relative to the workspace. With only this set, the action just uploads the app. If `test_id` or `test_suite_id` is also set, the tests run on the uploaded file unless one of the app overrides below is set.
- `app_name`: (Optional) Name of the app to upload the file to. Defaults to the app with the same package or bundle ID, or a new app named after it.
- `app_tags`: (Optional) Tags of the app to point at the uploaded file, separated by commas, e.g. `latest, 1.4.3`. A tag the app already has is moved to the new file. Defaults to `latest`. Setting tags replaces the default, so list `latest` too to keep moving it.
- `app_file_id_override`: (Optional) ID of the app file to run the tests on instead of their own app.
- `app_name_override`: (Optional) Name of the app to run the tests on instead of their own app. Requires `app_platform_override`. Cannot be combined with `app_file_id_override`.
- `app_platform_override`: (Optional) Platform of the app in `app_name_override`: `android` or `ios`.
- `app_tag_override`: (Optional) Tag of the app in `app_name_override` whose file the tests run on. Defaults to `latest`.
- `create_issue_on_failure`: (Optional) If `true`, automatically creates a GitHub issue when the test run fails. The issue includes step traces, error details, test configuration, and a screenshot from the last executed step. Requires `GITHUB_TOKEN` to be available. Default is `false`.
- `fail_on_skipped`: (Optional) If `true`, the action fails when any test in the run was skipped. Default is `false`.
- `fail_on_not_runnable`: (Optional) If `true`, the action fails when any test could not be run, e.g. because it is still generating. Default is `true`.

Cancelled and aborted runs always fail the action.

## Outputs

- `result`: A message that includes information about the status of the run.
- `app_file_id`: ID of the app file uploaded from `app_file_path`, if any.

## Example Usage for running a single test

```yaml
name: Run CJ Github Action

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - name: Run Test
        uses: foreai-co/cj-action@v1
        id: run_cj
        with:
          test_id: 'my-test-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
      
      - name: Print result
        run: echo "${{ steps.run_cj.outputs.result }}"
```

## Example Usage for running a test suite

```yaml
name: Run CJ Github Action

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - name: Run Test Suite
        uses: foreai-co/cj-action@v1
        id: run_cj
        with:
          test_suite_id: 'my-test-suite-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
          wait_timeout_seconds: 360  # = 6 minutes
          # Override the website url using this optional field.
          website_url_override: 'https://beta-dev.my-awesome.com/2'
          # Override test parameters using this optional field. Provide valid json string.
          variable_overrides: '{ "3f2504e0-4f89-11d3-9a0c-0305e82c3301" : { "kind" : "non_secret", "value" : "value1" } }'

      - name: Print result
        run: echo "${{ steps.run_cj.outputs.result }}"
```

## Example Usage with automatic GitHub issue creation on failure

When `create_issue_on_failure` is enabled, the action uses the default `GITHUB_TOKEN` provided automatically by GitHub Actions — no manual secret configuration required. If your repository uses restrictive default permissions, add `issues: write` to the job permissions.

```yaml
name: Run CJ Github Action

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    permissions:
      issues: write  # Required to create GitHub issues on failure
    steps:
      - name: Run Test Suite
        uses: foreai-co/cj-action@v1
        id: run_cj
        with:
          test_suite_id: 'my-test-suite-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
          create_issue_on_failure: 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Print result
        run: echo "${{ steps.run_cj.outputs.result }}"
```

## Example Usage for uploading a mobile app and testing it

```yaml
name: Build and test the app

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build APK
        run: ./gradlew assembleDebug

      - name: Upload the app and run the test suite on it
        uses: foreai-co/cj-action@v1
        id: run_cj
        with:
          test_suite_id: 'my-test-suite-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
          app_file_path: 'app/build/outputs/apk/debug/app-debug.apk'
          app_name: 'My App'
          app_tags: 'latest, ${{ github.sha }}'

      - name: Print the uploaded app file
        run: echo "${{ steps.run_cj.outputs.app_file_id }}"
```

Optionally, to run tests on an app uploaded earlier, point them at one of its tags instead. This is only needed to run another app or tag than the tests' own: tests that use their app's `latest` tag run on the newest file tagged `latest` without any app override.

```yaml
      - name: Run the test suite on the app's staging build
        uses: foreai-co/cj-action@v1
        with:
          test_suite_id: 'my-test-suite-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
          app_name_override: 'My App'
          app_platform_override: 'android'
          app_tag_override: 'staging'
```
