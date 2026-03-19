"""Write and update notes tools."""

from typing import Any

import structlog

from notes_mcp.frontmatter import update_fields
from notes_mcp.server import mcp, settings
from notes_mcp.vault import PathSecurityError
from notes_mcp.vault import append_to_note as vault_append
from notes_mcp.vault import edit_note as vault_edit
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


@mcp.tool(annotations={"destructiveHint": False, "title": "Edit Note"})
async def edit_note(
    path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
) -> dict[str, Any]:
    """Search and replace text within a note's body content.

    Finds old_text in the note body and replaces it with new_text.
    Fails if old_text is not found. Fails if old_text appears more
    than once unless replace_all=True.

    Does not touch frontmatter — use update_frontmatter for that.

    Args:
        path: Relative path within the vault
        old_text: Exact text to find (must be unique unless replace_all)
        new_text: Replacement text
        replace_all: Replace all occurrences (default: first only, error if ambiguous)
    """
    logger.info("tool.edit_note", path=path)
    try:
        result = vault_edit(settings.vault, path, old_text, new_text, replace_all)
    except PathSecurityError as e:
        return {"error": str(e)}
    except (FileNotFoundError, ValueError) as e:
        return {"error": str(e)}

    return {
        "path": result.path,
        "title": result.title,
        "updated": result.updated,
        "replacements": result.replacements,
    }


@mcp.tool(annotations={"destructiveHint": False, "title": "Append to Note"})
async def append_to_note(
    path: str,
    content: str,
    heading: str | None = None,
) -> dict[str, Any]:
    """Append content to a note, optionally under a specific heading.

    If heading is provided, inserts content at the end of that section
    (before the next heading of the same or higher level).
    If the heading doesn't exist, creates it at the end of the note.
    If no heading is given, appends to the end of the note.

    Args:
        path: Relative path within the vault
        content: Text to append
        heading: Optional heading to append under (e.g., "## Notes")
    """
    logger.info("tool.append_to_note", path=path, heading=heading)
    try:
        note = vault_append(settings.vault, path, content, heading)
    except PathSecurityError as e:
        return {"error": str(e)}
    except FileNotFoundError as e:
        return {"error": str(e)}

    return {
        "path": note.path,
        "title": note.title,
        "updated": note.frontmatter.updated,
    }
