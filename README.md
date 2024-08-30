# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `website`: The web url to test.
- `test-name`: A name to identify the test.
- `instructions`: Instructions for doing the test.
- `cj-token`: Your secret token to access fore ai Critical Journey.

## Outputs

- `result`: The URL where you can view the test results.

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
        uses: foreai-co/critical-journey@v1.0.2
        with:
          instructions: 'Go to my website and try logging in.'
          website: 'https://staging.my_website.com'
          test-name: 'Login test'
          cj-token: ${{ secrets.CRITICAL_JOURNEY_TOKEN }}
