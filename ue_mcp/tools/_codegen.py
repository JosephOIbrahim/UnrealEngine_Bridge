"""Shared code generation snippets for UE5 MCP tools.

These functions generate Python code strings that are executed in the UE5 editor.
They eliminate duplication of common patterns across tool modules.
"""
from __future__ import annotations


def find_actor_by_label_snippet(safe_label_expr: str) -> str:
    """Generate Python code that finds a level actor by its label.

    Sets local variable ``actor`` to the found actor or ``None``.
    Caller must handle the ``None`` case with its own error message.

    Args:
        safe_label_expr: Python expression evaluating to the label string.
            Must be safe for embedding in generated code.  Typically a
            quoted string like ``'"MyActor"'``.

    Returns:
        Multi-line Python code string.  After execution the local
        variable ``actor`` is either the matching actor or ``None``.
    """
    return (
        f"subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
        f"actors = subsystem.get_all_level_actors()\n"
        f"actor = None\n"
        f"for a in actors:\n"
        f"    if a.get_actor_label() == {safe_label_expr}:\n"
        f"        actor = a\n"
        f"        break\n"
    )
