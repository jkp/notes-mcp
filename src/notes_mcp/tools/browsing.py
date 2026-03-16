"""Browsing tools: directory listing, path checking, and metadata retrieval."""

from typing import Any

import structlog

from notes_mcp.server import mcp, settings
from notes_mcp.vault import PathSecurityError
from notes_mcp.vault import list_directory as vault_list_directory
from notes_mcp.vault import path_exists as vault_path_exists
from notes_mcp.vault import read_note as vault_read_note

logger = structlog.get_logger()


def _entry_to_dict(entry) -> dict[str, Any]:
    """Convert a DirectoryEntry to a dict, recursing into children."""
    result: dict[str, Any] = {
        "path": entry.path,
        "name": entry.name,
        "type": entry.type,
    }
    if entry.frontmatter is not None:
        result["frontmatter"] = entry.frontmatter.model_dump()
    if entry.children is not None:
        result["children"] = [_entry_to_dict(c) for c in entry.children]
    return result


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Directory",
    }
)
async def list_directory(
    path: str = "",
    recursive: bool = False,
    include_metadata: bool = True,
) -> list[dict[str, Any]] | dict[str, str]:
    """List files and directories in a vault path.

    Args:
        path: Relative directory path (empty string for vault root)
        recursive: Whether to recurse into subdirectories
        include_metadata: Whether to include frontmatter for .md files
    """
    logger.info("tool.list_directory", path=path, recursive=recursive)
    try:
        entries = vault_list_directory(
            settings.vault,
            path,
            recursive=recursive,
            include_metadata=include_metadata,
        )
        return [_entry_to_dict(e) for e in entries]
    except PathSecurityError:
        return {"error": f"Invalid path: {path}"}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Path Exists",
    }
)
async def path_exists(path: str) -> dict[str, Any]:
    """Check if a path exists within the vault.

    Args:
        path: Relative path within the vault
    """
    logger.info("tool.path_exists", path=path)
    try:
        exists, kind = vault_path_exists(settings.vault, path)
        result: dict[str, Any] = {"exists": exists}
        if kind is not None:
            result["type"] = kind
        return result
    except PathSecurityError:
        return {"exists": False}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Get Metadata",
    }
)
async def get_metadata(
    path: str,
    include_content_preview: bool = False,
) -> dict[str, Any]:
    """Get a note's metadata without full content.

    Args:
        path: Relative path to a .md file
        include_content_preview: Whether to include first 200 chars of body
    """
    logger.info("tool.get_metadata", path=path)
    try:
        note = vault_read_note(settings.vault, path)
    except PathSecurityError:
        return {"error": f"Invalid path: {path}"}

    if note is None:
        return {"error": f"Note not found: {path}"}

    result: dict[str, Any] = {
        "path": note.path,
        "title": note.title,
        "frontmatter": note.frontmatter.model_dump(),
    }
    if include_content_preview:
        result["content_preview"] = note.content[:200]
    return result
