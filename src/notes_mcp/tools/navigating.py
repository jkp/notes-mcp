"""Navigation tools for wiki link traversal."""

from typing import Any

import structlog

from notes_mcp.links import get_backlinks as links_get_backlinks
from notes_mcp.links import get_outlinks as links_get_outlinks
from notes_mcp.server import mcp, settings

logger = structlog.get_logger()


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Get Backlinks"}
)
async def get_backlinks(path: str) -> list[dict[str, Any]]:
    """Find all notes that link TO this note via wiki links.

    Args:
        path: Relative path of the target note
    """
    logger.info("tool.get_backlinks", path=path)
    results = await links_get_backlinks(settings.vault, settings.rg_bin, path)
    logger.info("tool.get_backlinks.done", path=path, count=len(results))
    return [r.model_dump() for r in results]


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Get Outlinks"}
)
async def get_outlinks(path: str) -> list[dict[str, Any]]:
    """Parse and resolve all wiki links FROM this note.

    Args:
        path: Relative path of the source note
    """
    logger.info("tool.get_outlinks", path=path)
    results = links_get_outlinks(settings.vault, path)
    logger.info("tool.get_outlinks.done", path=path, count=len(results))
    return [r.model_dump() for r in results]
