# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `test_id`: ID of the test to be run.
- `token`: Your secret token to access fore ai Critical Journey.

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
        uses: foreai-co/cj-action@v1.0.4
        id: run_cj
        with:
          test_id: 'my-test-id'
          token: ${{ secrets.CRITICAL_JOURNEY_TOKEN }}
      
      - name: Print CJ Action result
        run: echo "${{ steps.run_cj.outputs.result }}"