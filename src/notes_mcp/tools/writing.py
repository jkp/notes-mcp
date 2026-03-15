"""Write and update notes tools."""

from typing import Any

import structlog

from notes_mcp.frontmatter import update_fields
from notes_mcp.server import mcp, settings
from notes_mcp.vault import PathSecurityError
from notes_mcp.vault import read_note as vault_read_note
from notes_mcp.vault import write_note as vault_write_note

logger = structlog.get_logger()


@mcp.tool(
    annotations={"destructiveHint": False, "title": "Write Note"}
)
async def write_note(path: str, content: str) -> dict[str, Any]:
    """Create or update a note. Content should include YAML frontmatter.

    The `updated` field is set automatically to today's date.

    Args:
        path: Relative path within the vault (e.g., "Projects/my-project/notes.md")
        content: Full note content (frontmatter + body)
    """
    logger.info("tool.write_note", path=path)
    try:
        note = vault_write_note(settings.vault, path, content)
    except PathSecurityError as e:
        return {"error": str(e)}

    return {
        "path": note.path,
        "title": note.title,
        "updated": note.frontmatter.updated,
    }


@mcp.tool(
    annotations={"destructiveHint": False, "title": "Update Frontmatter"}
)
async def update_frontmatter(path: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update specific frontmatter fields without changing the note body.

    Args:
        path: Relative path within the vault
        fields: Key-value pairs to update in frontmatter
    """
    logger.info("tool.update_frontmatter", path=path, fields=list(fields.keys()))

    note = vault_read_note(settings.vault, path)
    if note is None:
        return {"error": f"Note not found: {path}"}

    # Read the raw content to preserve formatting
    full_path = settings.vault / path
    raw_content = full_path.read_text(encoding="utf-8")
    updated_content = update_fields(raw_content, fields)

    result = vault_write_note(settings.vault, path, updated_content)
    return {
        "path": result.path,
        "title": result.title,
        "frontmatter": result.frontmatter.model_dump(),
    }
