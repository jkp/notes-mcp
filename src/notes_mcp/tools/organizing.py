"""PARA organization and link suggestion tools."""

from pathlib import Path
from typing import Any

import structlog

from notes_mcp.frontmatter import parse_frontmatter, update_fields
from notes_mcp.server import mcp, searcher, settings
from notes_mcp.vault import move_note, read_note, write_note

logger = structlog.get_logger()


@mcp.tool(
    annotations={"destructiveHint": False, "title": "Move Note to PARA Bucket"}
)
async def move_note_to_para(path: str, bucket: str) -> dict[str, Any]:
    """Move a note between PARA buckets (Projects, Areas, Resources, Archive).

    Preserves the note's filename but moves it into the target bucket directory.
    Updates the `para` field in frontmatter.

    Args:
        path: Current relative path of the note
        bucket: Target PARA bucket name (Projects, Areas, Resources, or Archive)
    """
    if bucket not in settings.para_buckets:
        return {"error": f"Invalid PARA bucket: {bucket}. Must be one of {settings.para_buckets}"}

    logger.info("tool.move_note_to_para", path=path, bucket=bucket)

    filename = Path(path).name
    new_path = f"{bucket}/{filename}"

    try:
        result_path = move_note(settings.vault, path, new_path)
    except FileNotFoundError as e:
        return {"error": str(e)}

    # Update frontmatter with new PARA bucket
    full_path = settings.vault / result_path
    content = full_path.read_text(encoding="utf-8")
    updated_content = update_fields(content, {"para": bucket.lower()})
    write_note(settings.vault, result_path, updated_content)

    return {"path": result_path, "bucket": bucket}


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Suggest Links"}
)
async def suggest_links(path: str, limit: int = 10) -> list[dict[str, Any]]:
    """Analyse a note and suggest related notes that could be linked.

    Extracts keywords from the note's title, tags, and headings, then
    searches for notes containing those terms. Filters out already-linked notes.

    Args:
        path: Relative path of the note to analyse
        limit: Maximum suggestions to return
    """
    logger.info("tool.suggest_links", path=path)

    note = read_note(settings.vault, path)
    if note is None:
        return [{"error": f"Note not found: {path}"}]

    # Extract search terms from title, tags, and headings
    search_terms: list[str] = []
    if note.frontmatter.title:
        search_terms.append(note.frontmatter.title)
    search_terms.extend(note.frontmatter.tags)

    # Extract headings from body
    for line in note.content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading and len(heading) > 3:
                search_terms.append(heading)

    if not search_terms:
        return []

    # Collect existing outlinks to filter them out
    fm, body = parse_frontmatter(
        (settings.vault / path).read_text(encoding="utf-8")
    )
    from notes_mcp.links import parse_outlinks

    existing_links = set(parse_outlinks(body))
    existing_links.update(fm.related)

    # Search for each term and collect candidates
    candidates: dict[str, dict[str, Any]] = {}
    for term in search_terms[:5]:  # Limit to 5 search terms
        results = await searcher.search(term, limit=10)
        for hit in results:
            if hit.path == path:
                continue
            if hit.path in candidates:
                candidates[hit.path]["match_count"] += hit.match_count
                if term not in candidates[hit.path]["matched_terms"]:
                    candidates[hit.path]["matched_terms"].append(term)
            else:
                candidates[hit.path] = {
                    "path": hit.path,
                    "match_count": hit.match_count,
                    "matched_terms": [term],
                    "snippet": hit.snippet,
                }

    # Filter out already-linked notes
    filtered = []
    for c in candidates.values():
        stem = Path(c["path"]).stem
        if stem not in existing_links and c["path"] not in existing_links:
            # Check by title too
            linked_note = read_note(settings.vault, c["path"])
            if linked_note and linked_note.title not in existing_links:
                filtered.append(c)

    # Sort by match count and return top results
    filtered.sort(key=lambda x: x["match_count"], reverse=True)

    suggestions = []
    for c in filtered[:limit]:
        suggestions.append({
            "path": c["path"],
            "reason": f"matched terms: {', '.join(c['matched_terms'])}",
            "snippet": c["snippet"],
        })

    logger.info("tool.suggest_links.done", path=path, count=len(suggestions))
    return suggestions
