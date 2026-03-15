"""Tests for frontmatter parsing and serialization."""

from notes_mcp.frontmatter import parse_frontmatter, serialize_frontmatter, update_fields
from notes_mcp.models import Frontmatter


class TestParseFrontmatter:
    def test_parse_full_frontmatter(self) -> None:
        content = (
            "---\n"
            "title: Test Note\n"
            "para: projects\n"
            "tags: [ai, ml]\n"
            "related:\n"
            "  - '[[Other Note]]'\n"
            "updated: '2026-03-14'\n"
            "---\n"
            "Body content here.\n"
        )
        fm, body = parse_frontmatter(content)
        assert fm.title == "Test Note"
        assert fm.para == "projects"
        assert fm.tags == ["ai", "ml"]
        assert fm.related == ["[[Other Note]]"]
        assert fm.updated == "2026-03-14"
        assert body == "Body content here.\n"

    def test_parse_no_frontmatter(self) -> None:
        content = "Just plain text, no frontmatter.\n"
        fm, body = parse_frontmatter(content)
        assert fm.title is None
        assert fm.tags == []
        assert body == content

    def test_parse_partial_frontmatter(self) -> None:
        content = "---\ntitle: Minimal\n---\nBody.\n"
        fm, body = parse_frontmatter(content)
        assert fm.title == "Minimal"
        assert fm.para is None
        assert fm.tags == []
        assert body == "Body.\n"

    def test_preserves_unknown_fields(self) -> None:
        content = "---\ntitle: Test\ncustom_field: hello\npriority: high\n---\nBody.\n"
        fm, body = parse_frontmatter(content)
        assert fm.title == "Test"
        assert fm.extra == {"custom_field": "hello", "priority": "high"}

    def test_parse_date_as_string(self) -> None:
        content = "---\ntitle: Test\nupdated: 2026-03-14\n---\nBody.\n"
        fm, _ = parse_frontmatter(content)
        assert fm.updated == "2026-03-14"
        assert isinstance(fm.updated, str)


class TestSerializeFrontmatter:
    def test_round_trip(self) -> None:
        fm = Frontmatter(
            title="Test",
            para="projects",
            tags=["a", "b"],
            related=["[[Other]]"],
            updated="2026-03-14",
        )
        body = "Some body content.\n"
        result = serialize_frontmatter(fm, body)
        fm2, body2 = parse_frontmatter(result)
        assert fm2.title == fm.title
        assert fm2.para == fm.para
        assert fm2.tags == fm.tags
        assert fm2.related == fm.related
        assert body2 == body

    def test_omits_empty_fields(self) -> None:
        fm = Frontmatter(title="Minimal")
        result = serialize_frontmatter(fm, "Body.\n")
        assert "tags:" not in result
        assert "related:" not in result
        assert "para:" not in result

    def test_preserves_extra_fields(self) -> None:
        fm = Frontmatter(title="Test", extra={"custom": "value"})
        result = serialize_frontmatter(fm, "Body.\n")
        assert "custom: value" in result


class TestUpdateFields:
    def test_updates_known_fields(self) -> None:
        content = "---\ntitle: Old\npara: projects\n---\nBody.\n"
        result = update_fields(content, {"title": "New", "para": "archive"})
        fm, _ = parse_frontmatter(result)
        assert fm.title == "New"
        assert fm.para == "archive"

    def test_preserves_body(self) -> None:
        content = "---\ntitle: Test\n---\nImportant body content.\n"
        result = update_fields(content, {"tags": ["new-tag"]})
        _, body = parse_frontmatter(result)
        assert body == "Important body content.\n"

    def test_adds_extra_fields(self) -> None:
        content = "---\ntitle: Test\n---\nBody.\n"
        result = update_fields(content, {"custom": "value"})
        fm, _ = parse_frontmatter(result)
        assert fm.extra == {"custom": "value"}
