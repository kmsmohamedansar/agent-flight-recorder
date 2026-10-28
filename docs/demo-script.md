# Flight Recorder demo: failure to evidence

This script is for a 60–90 second screen recording. Use a temporary directory so the run and SQLite file are disposable. Show only the demo files and outputs; review the recording before sharing it.

## Prepare

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install flightrecorder-ai
```

## Record the demo

1. **0–10 seconds — The question.** Say: “An agent edited a payment check and the test failed. Which edit caused it?”
2. **10–30 seconds — Create the evidence.** Run `flightrecorder demo-agent`. Show the failing test and the investigator's first suspect. Explain that this command intentionally creates a bad edit as a repeatable example.
3. **30–50 seconds — Show the exact change.** Hold on the two removed lines in the diff: the `already_paid` check and `DuplicatePayment` exception. Say: “The test reports a duplicate was accepted, and this edit removed the rejection path.”
4. **50–65 seconds — Inspect the timeline.** Run `flightrecorder runs`, then `flightrecorder show RUN_ID` using the ID printed by `demo-agent`. Show the read, edit and test in order.
5. **65–80 seconds — Explain the limit.** Say: “This is a ranked lead backed by the recorded error and diff. It does not prove that every failure has one cause.”
6. **80–90 seconds — Call to action.** Show the repository URL and `pip install flightrecorder-ai`.

Optional follow-up: show the Codex MCP workflow with one failing run and one repaired run, then `compare_recordings`. Keep it separate from the short public demo because MCP captures only the steps the agent reports.

## Suggested caption

“Agent Flight Recorder keeps a local timeline of agent tool calls, file changes and test failures. This demo removes a duplicate-payment guard; the tool identifies the edit, shows its diff and explains the evidence. Open source, Python 3.9+, with an optional MCP adapter for Codex. Demo failure is intentional. [GitHub](https://github.com/kmsmohamedansar/agent-flight-recorder) · [PyPI](https://pypi.org/project/flightrecorder-ai/)”
