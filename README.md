# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `test_id`: ID of the test to be run. Either this or `test_suite_id` should be provided.
- `test_suite_id`: ID of the test suite to be run.
- `service_account_key`: Your service account key to access fore ai Critical Journey.
- `wait_timeout_seconds`: (Optional) Maximum number of seconds to wait for the test to complete. Default is 100 seconds. Must be between 10 and 900 seconds.

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
        uses: foreai-co/cj-action@v1.0.9
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
        uses: foreai-co/cj-action@v1.0.9
        id: run_cj
        with:
          test_suite_id: 'my-test-suite-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
          wait_timeout_seconds: 300  # = 5 minutes
      
      - name: Print result
        run: echo "${{ steps.run_cj.outputs.result }}"
```
