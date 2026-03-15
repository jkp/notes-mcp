"""Search tool using ripgrep."""

from typing import Any

import structlog

from notes_mcp.server import mcp, searcher

logger = structlog.get_logger()


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Search Notes"}
)
async def search_notes(
    query: str, path: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Full-text search across the knowledge base using ripgrep.

    Args:
        query: Search text (regex supported)
        path: Optional subdirectory to scope search (e.g., "Projects/")
        limit: Maximum results to return
    """
    logger.info("tool.search_notes", query=query, path=path, limit=limit)
    results = await searcher.search(query, path=path, limit=limit)
    logger.info("tool.search_notes.done", query=query, count=len(results))
    return [r.model_dump() for r in results]
