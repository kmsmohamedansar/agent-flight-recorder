# Contributing

Issues and focused pull requests are welcome. Describe the problem, expected behavior, and steps to reproduce it using synthetic data. Do not include real recordings, credentials, personal information, or private repository diffs.

For a local development check, use Python 3.9 or newer and run:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m flightrecorder demo-agent
```

The optional MCP adapter requires Python 3.10 or newer. Please include regression tests for behavior changes, update the documentation and changelog when relevant, and explain any privacy or compatibility trade-offs. See [SECURITY.md](SECURITY.md) for private vulnerability reporting; do not post sensitive details in a public issue.
