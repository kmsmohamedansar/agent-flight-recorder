# Architecture

Agent Flight Recorder is split into five layers:

1. **Instrumentation** — `RunSession`, `StepCapture` and `wrap_tool` observe agent
   actions without changing their normal exception behavior.
2. **Evidence storage** — `SQLiteStore` persists redacted runs and ordered steps.
   Schema changes are tracked with SQLite's `user_version`.
3. **Analysis** — investigation ranks causal suspects, comparison locates the
   first cross-run divergence, and replay returns recorded outputs.
4. **Presentation** — the CLI, native JSON/OTLP export and local web interface all
   consume the same store and analysis functions.
5. **Agent adapters** — `FlightRecorderService` exposes protocol-independent
   operations; the optional MCP server registers those operations as stdio tools.

The dependency direction is inward: presentation depends on analysis and storage;
instrumentation depends only on bounded file/Git capture and storage. The web
API's routing is independent of its HTTP transport so it can be tested without a
listening socket.

## Data model

A run owns ordered steps. Each step contains its operation type, timestamps,
status, redacted inputs and outputs, an optional error, and metadata such as file
changes. Runs contain agent metadata and before/after Git state when a repository
is discoverable.

## Integration boundary

Framework adapters should call `run.wrap_tool()` rather than writing directly to
SQLite. This keeps redaction, failure handling, snapshots and future schema changes
centralized. Adapters may attach framework-specific trace identifiers in metadata.

The MCP process is deliberately local and explicit. It does not intercept another
agent's tools; the client calls `start_recording`, `record_step`, and
`finish_recording`. Read-only tools use the same store and investigation code as
the CLI, avoiding a second analysis implementation.

