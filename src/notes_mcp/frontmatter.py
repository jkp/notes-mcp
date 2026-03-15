"""YAML frontmatter parsing and serialization for Markdown notes."""

import re
from typing import Any

import yaml

from notes_mcp.models import Frontmatter

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_KNOWN_FIELDS = {"title", "para", "tags", "related", "updated"}


def parse_frontmatter(content: str) -> tuple[Frontmatter, str]:
    """Split a note into frontmatter and body.

    Returns (Frontmatter, body_text). If no frontmatter block is found,
    returns default Frontmatter and the full content as body.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return Frontmatter(), content

    raw: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
    body = content[match.end() :]

    # Extract related links as plain strings (they may be [[wiki links]])
    related_raw = raw.pop("related", [])
    if isinstance(related_raw, list):
        related = [str(r) for r in related_raw]
    else:
        related = []

    extra = {k: v for k, v in raw.items() if k not in _KNOWN_FIELDS}

    fm = Frontmatter(
        title=raw.get("title"),
        para=raw.get("para"),
        tags=raw.get("tags", []),
        related=related,
        updated=str(raw["updated"]) if raw.get("updated") is not None else None,
        extra=extra,
    )
    return fm, body


def serialize_frontmatter(fm: Frontmatter, body: str) -> str:
    """Rebuild full note content from frontmatter and body."""
    data: dict[str, Any] = {}
    if fm.title:
        data["title"] = fm.title
    if fm.para:
        data["para"] = fm.para
    if fm.tags:
        data["tags"] = fm.tags
    if fm.related:
        data["related"] = fm.related
    if fm.updated:
        data["updated"] = fm.updated
    data.update(fm.extra)

    yaml_str = yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    return f"---\n{yaml_str}---\n{body}"


def update_fields(content: str, updates: dict[str, Any]) -> str:
    """Update specific frontmatter fields, preserving body and unknown fields."""
    fm, body = parse_frontmatter(content)

    for key, value in updates.items():
        if key in _KNOWN_FIELDS:
            setattr(fm, key, value)
        else:
            fm.extra[key] = value

    return serialize_frontmatter(fm, body)
