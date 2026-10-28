# Security policy

## Reporting

Please report suspected vulnerabilities privately to the repository owner. Do not
include live credentials or sensitive production recordings in a public issue.

## Deployment notes

- Treat the SQLite database as sensitive even when redaction is enabled.
- Add `.flightrecorder.sqlite*` to `.gitignore`; database, WAL and shared-memory
  files must not be committed.
- Git context capture is off by default. Enabling it stores bounded working and
  staged diffs, which can include changes unrelated to the recorded tool calls.
- Keep the timeline server bound to localhost or place it behind authentication.
- Use least-privilege service credentials for recorded agents.
- Review custom tool inputs, outputs and exception formats for project-specific
  secrets before production use.
- Apply retention with `flightrecorder prune`; deletion is explicit via `--yes`.
- Run the MCP adapter over local stdio. Do not expose it through an unauthenticated
  network bridge; its tools can read recordings and append data to the local store.

The recorder never intentionally repeats side effects during replay. A future
adapter that enables live replay must make that behavior explicit and opt-in.

