"""Small instrumentation API for agent actions."""

from __future__ import annotations

import traceback
import uuid
import functools
import inspect
import os
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Type, TypeVar, cast

from .files import changes, snapshot
from .git import git_state
from .store import SQLiteStore


Function = TypeVar("Function", bound=Callable[..., Any])


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepCapture(AbstractContextManager):
    def __init__(
        self,
        run: "RunSession",
        name: str,
        kind: str,
        input: Any,
        metadata: Optional[Dict[str, Any]],
        watch_paths: Optional[Iterable[str]],
    ) -> None:
        self.run = run
        self.name = name
        self.kind = kind
        self.input = input
        self.output: Any = None
        self.metadata = dict(metadata or {})
        self.watch_paths = list(watch_paths or [])
        self.changes: List[Dict[str, Any]] = []
        self._before: Dict[str, Optional[str]] = {}
        self.started_at = ""

    def __enter__(self) -> "StepCapture":
        self.started_at = now()
        if self.watch_paths:
            self._before = snapshot(self.watch_paths)
        return self

    def set_output(self, output: Any) -> Any:
        self.output = output
        return output

    def add_change(
        self, path: str, before: Optional[str], after: Optional[str]
    ) -> None:
        self.changes.append({"path": path, "before": before, "after": after})

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        if self.watch_paths:
            for path, change in changes(
                self._before, snapshot(self.watch_paths)
            ).items():
                self.add_change(path, change["before"], change["after"])
        metadata = dict(self.metadata)
        if self.changes:
            metadata["changes"] = self.changes
        error = None
        if exc is not None:
            error = "".join(traceback.format_exception_only(exc_type, exc)).strip()
        self.run._record(
            name=self.name,
            kind=self.kind,
            input=self.input,
            output=self.output,
            status="failed" if exc else "ok",
            error=error,
            metadata=metadata,
            started_at=self.started_at or now(),
        )
        return False


class RunSession(AbstractContextManager):
    def __init__(
        self,
        store: SQLiteStore,
        name: str,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capture_git: bool = False,
    ) -> None:
        self.store = store
        self.id = run_id or "run-" + uuid.uuid4().hex[:8]
        self.name = name
        self.metadata = dict(metadata or {})
        self.capture_git = capture_git
        self.started_at = now()
        self._closed = False
        self._has_failure = False

    def __enter__(self) -> "RunSession":
        if self.capture_git:
            workspace = str(self.metadata.get("workspace") or os.getcwd())
            try:
                state = git_state(workspace)
            except Exception:
                state = None
            if state is not None:
                self.metadata["git_before"] = state
        self.store.create_run(self.id, self.name, self.started_at, self.metadata)
        return self

    def step(
        self,
        name: str,
        *,
        kind: str = "tool",
        input: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        watch_paths: Optional[Iterable[str]] = None,
    ) -> StepCapture:
        return StepCapture(self, name, kind, input, metadata, watch_paths)

    def wrap_tool(
        self,
        function: Function,
        *,
        name: Optional[str] = None,
        kind: str = "tool",
        watch_paths: Optional[Iterable[str]] = None,
    ) -> Function:
        """Wrap a sync or async tool and record every invocation."""
        tool_name = name or function.__name__
        metadata = {
            "callable": "%s.%s" % (function.__module__, function.__qualname__)
        }

        def inputs(args: Any, kwargs: Any) -> Dict[str, Any]:
            try:
                bound = inspect.signature(function).bind_partial(*args, **kwargs)
                bound.apply_defaults()
                return dict(bound.arguments)
            except (TypeError, ValueError):
                return {"args": args, "kwargs": kwargs}

        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.step(
                    tool_name,
                    kind=kind,
                    input=inputs(args, kwargs),
                    metadata=metadata,
                    watch_paths=watch_paths,
                ) as step:
                    return step.set_output(await function(*args, **kwargs))

            return cast(Function, async_wrapper)

        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self.step(
                tool_name,
                kind=kind,
                input=inputs(args, kwargs),
                metadata=metadata,
                watch_paths=watch_paths,
            ) as step:
                return step.set_output(function(*args, **kwargs))

        return cast(Function, wrapper)

    def record(
        self,
        name: str,
        *,
        kind: str = "tool",
        input: Any = None,
        output: Any = None,
        status: str = "ok",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            name=name,
            kind=kind,
            input=input,
            output=output,
            status=status,
            error=error,
            metadata=dict(metadata or {}),
            started_at=now(),
        )

    def _record(self, **step: Any) -> None:
        if step.get("status") == "failed":
            self._has_failure = True
        step.update(run_id=self.id, finished_at=now())
        self.store.add_step(step)

    def finish(self, status: str = "ok") -> None:
        if not self._closed:
            if status == "ok" and self._has_failure:
                status = "failed"
            if self.capture_git:
                workspace = str(self.metadata.get("workspace") or os.getcwd())
                try:
                    state = git_state(workspace)
                except Exception:
                    state = None
                if state is not None:
                    self.metadata["git_after"] = state
                    self.store.update_run_metadata(self.id, self.metadata)
            self.store.finish_run(self.id, status, now())
            self._closed = True

    def __exit__(self, exc_type: Any, exc: Any, exc_tb: Any) -> bool:
        self.finish("failed" if exc else "ok")
        return False


class FlightRecorder:
    def __init__(
        self, db_path: str = ".flightrecorder.sqlite", *, capture_git: bool = False
    ) -> None:
        self.store = SQLiteStore(db_path)
        self.capture_git = capture_git

    def run(
        self,
        name: str,
        *,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capture_git: Optional[bool] = None,
    ) -> RunSession:
        should_capture_git = self.capture_git if capture_git is None else capture_git
        return RunSession(self.store, name, run_id, metadata, should_capture_git)

