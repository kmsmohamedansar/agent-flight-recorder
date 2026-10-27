# Security policy

## Reporting

Please report suspected vulnerabilities privately to the repository owner. Do not
include live credentials or sensitive production recordings in a public issue.

## Deployment notes

- Treat the SQLite database as sensitive even when redaction is enabled.
- Keep the timeline server bound to localhost or place it behind authentication.
- Use least-privilege service credentials for recorded agents.
- Review custom tool inputs, outputs and exception formats for project-specific
  secrets before production use.
- Apply retention with `flightrecorder prune`; deletion is explicit via `--yes`.

The recorder never intentionally repeats side effects during replay. A future
adapter that enables live replay must make that behavior explicit and opt-in.

