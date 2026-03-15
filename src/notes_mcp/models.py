"""Pydantic models for notes, search results, and link info."""

from pydantic import BaseModel, Field


class Frontmatter(BaseModel):
    """YAML frontmatter metadata for a note."""

    title: str | None = None
    para: str | None = None
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    updated: str | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class Note(BaseModel):
    """A complete note with metadata and content."""

    path: str
    title: str
    frontmatter: Frontmatter
    content: str


class SearchHit(BaseModel):
    """A search result from ripgrep."""

    path: str
    line_number: int
    snippet: str
    match_count: int = 1


class LinkInfo(BaseModel):
    """Information about a linked note."""

    path: str
    title: str
    snippet: str | None = None


class NoteListEntry(BaseModel):
    """Summary metadata for listing notes."""

    path: str
    title: str
    para: str | None = None
    tags: list[str] = Field(default_factory=list)
    updated: str | None = None
