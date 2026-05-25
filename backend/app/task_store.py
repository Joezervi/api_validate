"""In-memory task store for background PO processing jobs.

Status lifecycle:
  "pending"    → task registered, background coroutine not yet started
  "processing" → background coroutine is running
  "done"       → completed successfully; result dict is populated
  "error"      → exception occurred; error string is populated

Trade-off: state is lost on process restart and is not shared across
multiple uvicorn workers. This is acceptable for the current single-
container Docker deployment.
"""

from typing import Any, Literal

TaskStatus = Literal["pending", "processing", "done", "error"]

# Module-level singleton — one dict per process
_tasks: dict[str, dict[str, Any]] = {}


def create_task(task_id: str) -> None:
    """Register a new task in pending state."""
    _tasks[task_id] = {"status": "pending", "result": None, "error": None}


def set_processing(task_id: str) -> None:
    """Mark task as actively running."""
    _tasks[task_id]["status"] = "processing"


def set_done(task_id: str, result: dict) -> None:
    """Mark task as successfully completed and store the result."""
    _tasks[task_id]["status"] = "done"
    _tasks[task_id]["result"] = result


def set_error(task_id: str, error: str) -> None:
    """Mark task as failed and store the error message."""
    _tasks[task_id]["status"] = "error"
    _tasks[task_id]["error"] = error


def get_task(task_id: str) -> dict | None:
    """Return the task dict, or None if the task_id is unknown."""
    return _tasks.get(task_id)


def delete_task(task_id: str) -> None:
    """Remove a completed task to free memory (optional clean-up)."""
    _tasks.pop(task_id, None)
