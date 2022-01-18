# Contributing to Thermal Comfort
Everybody is invited and welcome to contribute to Thermal Comfort.

## Report bugs using Github's [issues](https://github.com/dolezsa/thermal_comfort/issues)
We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/dolezsa/thermal_comfort/issues/new/choose).

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports. I'm not even kidding.

## Pull Requests
1. Fork the repo and create your branch from `master`.
2. Make sure you have pre-commit installed and run `pre-commit install`.
3. If you've added code that should be tested, add tests.
4. If you've changed APIs, update the documentation.
5. Ensure the [test suite](#test-suite) passes.
6. Make sure your code [lints](#style-guideline).
7. Issue that pull request!

## Test Suite
 1. Setup local tests:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.test.txt
```
2. Run local tests:
```bash
source venv/bin/activate
pytest
```

## Style Guideline
We use [home assistants style guideline](https://developers.home-assistant.io/docs/development_guidelines).

## Contributor Credits
You can add yourself to [CREDITS.md](CREDITS.md) in your PR. Otherwise you will be added before our next release.
