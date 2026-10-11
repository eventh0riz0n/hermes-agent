"""Context-loss boundaries: tool results just left the model-visible context.

Sibling of ``agent/conversation_compression.py`` (the facade, which re-exports both names). Every
"already delivered" tracker advances here together: the read dedup caches and the loop guardrail's
context generation. This module must never import the facade at module level (import cycle).
"""

from __future__ import annotations

import contextlib
from typing import Any, Optional


def _reset_read_dedup_caches(task_id: str, *, session_id: str = "") -> None:
    """Advance the file-read and skill_view repeat-read dedup to a fresh generation after a boundary.
    The mtime map is kept: the first read of each unchanged key returns full content compaction may have
    omitted; later reads return stubs, and stub-hit counters restart at the same boundary (#84857).
    The computer_use screenshot dedup is session-keyed and forgets its last frame for the same reason.
    """
    with contextlib.suppress(Exception):
        from tools.file_tools_read_tracking import reset_file_dedup
        reset_file_dedup(task_id)
    if session_id:
        with contextlib.suppress(Exception):
            from tools.computer_use.tool import reset_screenshot_dedup
            reset_screenshot_dedup(session_id)
    with contextlib.suppress(Exception):
        from tools.skills_tool import reset_skill_view_dedup
        reset_skill_view_dedup(task_id)


def mark_context_loss_boundary(agent: Any, task_id: Optional[str], *, reset_read_caches: bool = True) -> None:
    """Tool results just left the model-visible context: advance every "already delivered" tracker together.

    The single hook for compaction, committed prune, micro-compaction splice, native checkpoint and
    compression-child adoption. The read dedup caches serve full content again, and the loop guardrail
    starts a new context generation so the first re-read is not counted as a repeat (#109683).
    ``reset_read_caches=False`` leaves the read caches alone (callers without a task id: a ``None`` reset
    would clear every task's); the guardrail generation still advances.
    """
    if reset_read_caches:
        _reset_read_dedup_caches(task_id, session_id=getattr(agent, "session_id", None) or "")
    guardrails = getattr(agent, "_tool_guardrails", None)
    note_boundary = getattr(guardrails, "note_context_boundary", None)
    if callable(note_boundary):
        note_boundary()
