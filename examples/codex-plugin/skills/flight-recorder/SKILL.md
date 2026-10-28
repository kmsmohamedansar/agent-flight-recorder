---
name: flight-recorder
description: Record a local coding-agent workflow and investigate a failure with evidence.
---

Use the `flightrecorder` MCP tools when the user asks to record, inspect, compare,
or investigate an agent run.

For a recorded workflow:

1. Call `start_recording` before beginning the requested work.
2. Call `record_step` after each meaningful tool action. Include file changes in
   the first-class `changes` field when known, and never include credentials or unnecessary
   personal data.
3. Call `finish_recording` even when the work fails.
4. On failure, call `investigate_run` and describe its result as a suspect backed
   by recorded evidence, not as certainty.

The MCP server only sees actions explicitly sent to its tools. It does not
automatically intercept Codex's built-in shell or file tools.
