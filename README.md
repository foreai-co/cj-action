# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `test_id`: ID of the test to be run.
- `service_account_key`: Your service account key to access fore ai Critical Journey.

## Outputs

- `result`: A message that includes information about the status of the run.

## Example Usage

```yaml
name: Run CJ Github Action

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - name: Run CJ Action
        uses: foreai-co/cj-action@v1
        id: run_cj
        with:
          test_id: 'my-test-id'
          service_account_key: ${{ secrets.CRITICAL_JOURNEY_SERVICE_ACCOUNT_KEY }}
      
      - name: Print CJ Action result
        run: echo "${{ steps.run_cj.outputs.result }}"
```
