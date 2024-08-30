# Critical Journey Github Action

This GitHub Action runs the critical journey script inside a Docker container.

## Inputs

- `url`: URL of the website under test.
- `name`: A unique name to identify the test.
- `instructions`: The instructions to test in natural language.
- `token`: Your secret token to access fore ai Critical Journey.

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
      - name: Run CJ Action
        uses: foreai-co/cj-action@v1.0.4
        with:
          instructions: 'Go to my website and try logging in.'
          url: 'https://staging.my_website.com'
          name: 'Login test'
          token: ${{ secrets.CRITICAL_JOURNEY_TOKEN }}
