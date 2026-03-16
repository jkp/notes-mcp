"""Tests for NTFY push notification processor."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from notes_mcp.ntfy import (
    NOTIFICATION_RULES,
    NtfyNotifier,
    NtfyProcessor,
)


@pytest.fixture
def notifier():
    return NtfyNotifier(url="https://ntfy.sh/test-topic")


@pytest.fixture
def processor(notifier):
    return NtfyProcessor(notifier)


class TestNtfyNotifier:
    @patch("notes_mcp.ntfy.urlopen")
    async def test_send_posts_to_url(self, mock_urlopen, notifier):
        mock_urlopen.return_value = MagicMock()
        await notifier.send(
            title="Test", message="Something broke", priority="high", tags="warning"
        )
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.sh/test-topic"
        assert req.get_header("X-title") == "Test"
        assert req.get_header("X-priority") == "high"
        assert req.get_header("X-tags") == "warning"
        assert req.data == b"Something broke"

    @patch("notes_mcp.ntfy.urlopen")
    async def test_send_with_separate_topic(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        n = NtfyNotifier(url="https://ntfy.sh", topic="my-alerts")
        await n.send(title="T", message="M")
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.sh/my-alerts"

    @patch("notes_mcp.ntfy.urlopen")
    async def test_send_swallows_exceptions(self, mock_urlopen, notifier):
        mock_urlopen.side_effect = Exception("network error")
        await notifier.send(title="T", message="M")

    @patch("notes_mcp.ntfy.urlopen")
    async def test_send_default_priority(self, mock_urlopen, notifier):
        mock_urlopen.return_value = MagicMock()
        await notifier.send(title="T", message="M")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-priority") == "default"


class TestNtfyProcessor:
    def test_matching_event_triggers_notification(self, processor):
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {"event": "server.vault_not_found", "level": "warning"}
            result = processor(None, "warning", event_dict)
            assert result is event_dict
            mock_send.assert_called_once()

    def test_non_matching_event_passes_through(self, processor):
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {"event": "server.starting", "level": "info"}
            result = processor(None, "info", event_dict)
            assert result is event_dict
            mock_send.assert_not_called()

    def test_debounce_suppresses_repeat(self, processor):
        # Add a rule with debounce for testing
        processor.rules["test.debounced"] = NOTIFICATION_RULES.get(
            "test.debounced",
            type(list(NOTIFICATION_RULES.values())[0])(debounce_s=600),
        )
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {"event": "test.debounced", "level": "error"}
            processor(None, "error", event_dict)
            assert mock_send.call_count == 1
            processor(None, "error", event_dict)
            assert mock_send.call_count == 1

    def test_debounce_allows_after_window(self, processor):
        processor.rules["test.debounced"] = type(list(NOTIFICATION_RULES.values())[0])(
            debounce_s=600,
        )
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {"event": "test.debounced", "level": "error"}
            processor(None, "error", event_dict)
            assert mock_send.call_count == 1
            processor._last_sent["test.debounced"] = time.monotonic() - 700
            processor(None, "error", event_dict)
            assert mock_send.call_count == 2

    def test_zero_debounce_sends_every_time(self, processor):
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {"event": "server.vault_not_found", "level": "warning"}
            processor(None, "warning", event_dict)
            processor(None, "warning", event_dict)
            assert mock_send.call_count == 2

    def test_message_formatting_includes_error(self, processor):
        with patch.object(processor, "_schedule_send") as mock_send:
            event_dict = {
                "event": "server.vault_not_found",
                "level": "warning",
                "path": "/data/vault",
            }
            processor(None, "warning", event_dict)
            message = mock_send.call_args[0][1]
            assert "/data/vault" in message


class TestNotificationRules:
    def test_all_rules_have_valid_priorities(self):
        valid = {"urgent", "high", "default", "low", "min"}
        for event, rule in NOTIFICATION_RULES.items():
            assert rule.priority in valid, f"{event} has invalid priority {rule.priority}"

    def test_server_ready_exists(self):
        assert "server.ready" in NOTIFICATION_RULES
        assert NOTIFICATION_RULES["server.ready"].debounce_s == 0

    def test_vault_not_found_is_urgent(self):
        rule = NOTIFICATION_RULES["server.vault_not_found"]
        assert rule.priority == "urgent"


class TestIntegration:
    @patch("notes_mcp.ntfy.urlopen")
    async def test_end_to_end_notification(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        notifier = NtfyNotifier(url="https://ntfy.sh/test")
        processor = NtfyProcessor(notifier)

        event_dict = {"event": "server.vault_not_found", "level": "warning"}
        processor(None, "warning", event_dict)

        await asyncio.sleep(0.1)

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-priority") == "urgent"
