# Agent Flight Recorder — project case study

Agent Flight Recorder is a local debugging tool for AI agent workflows. It records tool actions, results, errors, file changes and Git context in SQLite, then helps answer a practical question after a failure: *which earlier change is worth looking at first, and why?*

I designed and released the project as a solo, open-source Python package. I used Codex as a coding collaborator, reviewed the behavior through tests and live runs, and connected its MCP interface to my Codex workspace. Version 1.1.0 is available as `flightrecorder-ai` on PyPI; the core supports Python 3.9+ and has no third-party runtime dependencies. The optional MCP adapter supports Python 3.10+.

## The problem

An agent can read a file, make several edits, call tools and run tests before it fails. The final error often identifies *what* broke but does not preserve the sequence that led there. A plain transcript is difficult to search, and a Git diff alone misses the tool outputs and failures that happened along the way.

I wanted a small local recorder that could keep this evidence together and make the first debugging pass explainable. It does not claim to prove causation. It ranks a suspect change and shows the recorded evidence and diff so a developer can judge it.

## How it works

1. A Python agent wraps synchronous or asynchronous tools with `FlightRecorder`, or an MCP client explicitly sends recording steps to the local server.
2. Each run stores ordered actions, timestamps, inputs, outputs, errors and metadata in SQLite. Watched text files get bounded before-and-after snapshots; Git state is captured when a repository is available.
3. When a step fails, the investigator ranks earlier file changes using implicated paths, filenames in the error, removed-code vocabulary and time order. It returns the leading suspect with its diff and reasons.
4. The CLI, local web view and MCP tools read the same recordings. Comparison finds the first recorded difference between two runs; replay supplies recorded tool outputs to deterministic tests without repeating side effects.

## A real failure from the demo workflow

The payment demo starts with a guard that rejects a second charge. A simulated agent edit removes the guard. The next regression test fails with `payment_service.py accepted a duplicate payment`.

```diff
 def charge(already_paid):
-    if already_paid:
-        raise DuplicatePayment("already paid")
     return "charged"
```

The investigator points to that edit because it precedes the failing test and the failure names the changed file. I restored those two lines in the local demo workspace, recorded the inspection, edit and test as a new run, and got `duplicate payment rejected` with exit code 0. Comparing the runs showed the opposite edits and the failed-versus-passed test result. The demo workspace is ignored by Git; the fix was a demonstration of the investigation workflow, not a source-code patch to the package.

## Design choices

- **Local SQLite storage.** A run can be inspected without an account or hosted service. Retention is an explicit dry run until `--yes` is supplied.
- **One analysis path.** The CLI, web API and MCP service share the storage and investigation code, so they do not produce different answers for the same run.
- **Bounded capture and redaction.** Common credential patterns are redacted before persistence, and captured values and files are size limited. Heuristics cannot guarantee that every secret is removed; recordings must be reviewed before sharing.
- **Explicit MCP recording.** The MCP server exposes recording and inspection tools, but cannot intercept an agent's built-in file or terminal actions. The client must send meaningful steps.
- **Narrow replay claim.** Replay returns recorded tool outputs and errors. It does not reproduce a model's internal choices or the state of an external service.

## What I verified

- The published `flightrecorder-ai==1.1.0` installed in a clean Python 3.9 environment. Its CLI, `demo-agent` workflow and localization benchmark ran successfully.
- A clean Python 3.12 installation with the MCP extra passed all 17 repository tests, including a stdio MCP client/server smoke test.
- The localization benchmark passed its five deterministic reference cases. These cases protect known ranking behavior; they are not a measured real-world accuracy rate.
- The local Codex MCP connection successfully listed, inspected, investigated and compared recordings, and recorded the successful repair run.

## Limits and next questions

The product is a beta. A developer must instrument tools or explicitly report MCP steps. Redaction is heuristic. The investigator offers a ranked lead, not a causal proof. The current five-case benchmark is too small and synthetic to establish effectiveness across agent frameworks and real projects. The next useful evidence is independent first-time use and real failure traces, followed by targeted changes to setup, capture coverage and investigation quality.

## Try it

```bash
python -m pip install flightrecorder-ai
flightrecorder demo-agent
flightrecorder runs
flightrecorder investigate
flightrecorder benchmark
```

For MCP on Python 3.10+, install `flightrecorder-ai[mcp]` and run `flightrecorder-mcp --db /absolute/path/to/recordings.sqlite`. See the [README](README.md), [architecture](ARCHITECTURE.md), [security notes](SECURITY.md), [PyPI package](https://pypi.org/project/flightrecorder-ai/) and [v1.1.0 release](https://github.com/kmsmohamedansar/agent-flight-recorder/releases/tag/v1.1.0).
