"""Read and list notes tools."""

from typing import Any

import structlog

from notes_mcp.server import mcp, settings
from notes_mcp.vault import list_notes as vault_list_notes
from notes_mcp.vault import read_note as vault_read_note

logger = structlog.get_logger()


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Read Note"}
)
async def read_note(path: str) -> dict[str, Any]:
    """Read a note's full content and metadata.

    Args:
        path: Relative path within the vault (e.g., "Projects/my-project/tasks.md")
    """
    logger.info("tool.read_note", path=path)
    note = vault_read_note(settings.vault, path)
    if note is None:
        return {"error": f"Note not found: {path}"}

    return {
        "path": note.path,
        "title": note.title,
        "frontmatter": note.frontmatter.model_dump(),
        "content": note.content,
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "List Notes"}
)
async def list_notes(path: str = "") -> list[dict[str, Any]]:
    """List notes in a directory with their metadata.

    Args:
        path: Relative directory path (empty string for vault root)
    """
    logger.info("tool.list_notes", path=path)
    entries = vault_list_notes(settings.vault, path)
    return [e.model_dump() for e in entries]
