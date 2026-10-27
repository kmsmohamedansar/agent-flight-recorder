# Agent Flight Recorder

A local black-box recorder for AI agents. It captures tool calls, results,
exceptions, file changes and Git context in SQLite, then connects failures to the
recorded evidence that most likely caused them.

The runtime has no third-party dependencies and supports Python 3.9+.

The PyPI distribution is named `flightrecorder-ai`; the Python import and command
remain `flightrecorder`.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install flightrecorder-ai

# Synthetic example from the product brief
flightrecorder demo
flightrecorder investigate run-1042

# Real files, wrapped tools and a subprocess test
flightrecorder demo-agent

# Local searchable timeline
flightrecorder serve
```

Open <http://127.0.0.1:8765> after starting the server. The project supports the
older pip bundled with some system Python installations; upgrading pip is optional.

## Instrument an agent

Wrap existing synchronous or asynchronous tools:

```python
from flightrecorder import FlightRecorder

recorder = FlightRecorder(".flightrecorder.sqlite")

with recorder.run("Fix payment bug", metadata={"workspace": "."}) as run:
    search = run.wrap_tool(search_code)
    edit = run.wrap_tool(edit_file, watch_paths=["src"])
    test = run.wrap_tool(run_tests, kind="test")

    matches = search("payment validation")
    edit("src/payment.py", replacement)
    test("tests/test_payment.py")
```

Arguments, return values and exceptions are captured automatically. Watched text
files are snapshotted before and after a call. Exceptions are recorded and then
re-raised, so instrumentation does not change control flow.

For lower-level integrations, `run.step(...)` and `run.record(...)` are also
available. `ReplayTape` feeds recorded outputs back to deterministic tests without
repeating side effects.

## Commands

| Command | Purpose |
| --- | --- |
| `init` | Initialize the SQLite database |
| `demo` | Record the synthetic payment failure |
| `demo-agent` | Execute a real file-edit and subprocess-test workflow |
| `runs` | List recent recordings |
| `show [run-id]` | Display a timeline |
| `investigate [run-id]` | Rank the first suspect change and show its evidence |
| `replay [run-id]` | Display the side-effect-free replay tape |
| `compare LEFT RIGHT` | Find the first meaningful divergence between runs |
| `export [run-id]` | Export native JSON or OTLP/JSON spans |
| `serve` | Start the local searchable timeline UI |
| `prune` | Preview or apply the retention policy |

All commands accept `--db PATH` before the command name. Commands accepting an
optional run ID use the latest run when it is omitted.

```bash
flightrecorder compare run-yesterday run-today --json
flightrecorder export run-today --format otlp --output trace.json
flightrecorder prune --older-than-days 30 --keep-latest 100
flightrecorder prune --older-than-days 30 --keep-latest 100 --yes
```

Retention is always a dry-run unless `--yes` is supplied.

## Investigation model

The investigator is deliberately explainable. It finds the first failed step,
ranks earlier file changes using explicit implicated paths, filenames mentioned in
the failure, removed-code vocabulary and temporal proximity, then returns its diff
and evidence. It reports a suspect—not unsupported certainty.

Exact model reproduction is not promised. Replay returns previously recorded tool
outputs and errors without calling live services; nondeterministic model behavior
and changed external systems remain outside that guarantee.

## Security and privacy

Common credential keys, inline passwords and bearer tokens are redacted before
SQLite persistence, including exception text and captured file content. Git and
file capture are bounded to one megabyte per value; binary files and common build
directories are skipped.

No heuristic filter is perfect. Test the redaction policy for your environment
before recording production or personal data. The web server binds to
`127.0.0.1` by default and has no authentication; do not expose it publicly.

See [SECURITY.md](SECURITY.md) for responsible disclosure and deployment notes.

## Development

```bash
python -m unittest discover -s tests -v
python -m flightrecorder demo-agent
```

CI runs the suite on Python 3.9, 3.12 and 3.13. Architecture and integration
boundaries are described in [ARCHITECTURE.md](ARCHITECTURE.md).

