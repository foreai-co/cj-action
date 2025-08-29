# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `test_id`: ID of the test to be run. Either this or `test_suite_id` should be provided.
- `test_suite_id`: ID of the test suite to be run.
- `service_account_key`: Your service account key to access fore ai Critical Journey.
- `wait_timeout_seconds`: (Optional) Maximum number of seconds to wait for the test to complete. Default is 300 seconds. Must be between 30 and 900 seconds (inclusive).
- `website_url_override`: (Optional) Allows overriding the base website URL used during test execution.  
- `params_override`: (Optional) Allows overriding default parameter values defined in the test suite, so that tests can be run with custom parameter values. This should be a valid json string and all keys and values are also strings.
- `browser_type_override`: (Optional) Browser to use for the test: 'chrome', 'firefox', or 'webkit'. Default is 'chrome'.

## Outputs

- `result`: A message that includes information about the status of the run.

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
          params_override: '{ "param1" : "value1", "param2" : "value2" }'
      
      - name: Print result
        run: echo "${{ steps.run_cj.outputs.result }}"
```
