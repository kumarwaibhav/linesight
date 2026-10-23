# Contributing

Project owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.

1. Create a feature branch and a focused change.
2. Install `python -m pip install -e '.[dev]'`.
3. Run `python -m pytest -q` and `python -m ruff check src tests scripts`.
4. Explain the change, the evidence, and any data/model impact in the PR.

Keep official test data held out from model selection. Change model design using
development images and proxy validation; then freeze a new artifact and label
any repeated evaluations of the same benchmark as development, rather than a
fresh independent test. New camera domains need a new evaluation collection.

Never commit raw dataset images, caches, API keys, event databases or environment
files. Preserve original dataset attribution and licenses. All performance
claims need a saved measurement protocol and machine-readable evidence.
