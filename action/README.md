# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `instructions`: Instructions for doing the test.

## Outputs

- `result`: The output from the Python script.

## Example Usage

```yaml
name: Run CJ Github Action

on: [push]

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v2
      
      - name: Run CJ Action
        uses: foreai-co/critical-journey@v1.0.0
        with:
          instructions: 'Go to my website'
