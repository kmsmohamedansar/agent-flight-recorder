# Changelog

## Unreleased

- Made Git context capture opt-in and prevented context-capture failures from
  interrupting recorded programs, including non-UTF-8 Git output.
- Added first-class MCP file-change reporting and actionable MCP tool errors.
- Expanded credential redaction, protected new SQLite files with owner-only
  permissions and documented the remaining privacy limits.
- Made count-based pruning apply independently, corrected the OTLP scope version,
  and improved no-suspect and server-start errors.
- Added regression coverage for the independently reported failures.

## 1.1.0 — 2026-10-27

- Added an optional MCP 2.x stdio server for Codex and other MCP clients.
- Added recording, inspection, comparison, export and investigation MCP tools.
- Added a portable local Codex plugin example with a recording skill.
- Added a deterministic failure-localization benchmark and CI coverage.

## 1.0.0 — 2026-10-27

- Published under the `flightrecorder-ai` distribution name to avoid a collision
  with an unrelated package.
- Added synchronous and asynchronous tool instrumentation.
- Added bounded file snapshots and automatic diffs.
- Added credential redaction, retention controls and schema versioning.
- Added deterministic output replay and run comparison.
- Added real filesystem/subprocess demonstration workflow.
- Added native JSON and OTLP/JSON export.
- Added local searchable timeline UI and API.
- Added Git context capture, CI and end-to-end tests.

