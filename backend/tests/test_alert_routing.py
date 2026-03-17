"""Tests for alert routing service (channel selection, severity ordering)"""

import pytest
from app.services.alert_routing import (
    AlertRouter,
    AlertChannel,
    RoutingRule,
    SEVERITY_ORDER,
    DEFAULT_RULES,
)


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

def test_severity_order_values():
    assert SEVERITY_ORDER["INFO"] < SEVERITY_ORDER["LOW"]
    assert SEVERITY_ORDER["LOW"] < SEVERITY_ORDER["MEDIUM"]
    assert SEVERITY_ORDER["MEDIUM"] < SEVERITY_ORDER["HIGH"]
    assert SEVERITY_ORDER["HIGH"] < SEVERITY_ORDER["CRITICAL"]


def test_default_rules_exist():
    assert len(DEFAULT_RULES) >= 3


# ---------------------------------------------------------------------------
# Channel selection logic
# ---------------------------------------------------------------------------

class TestGetChannels:
    def setup_method(self):
        self.router = AlertRouter()

    def test_info_gets_websocket_only(self):
        channels = self.router.get_channels("INFO")
        assert AlertChannel.WEBSOCKET in channels
        assert AlertChannel.EMAIL not in channels
        assert AlertChannel.PAGER not in channels

    def test_high_gets_websocket_and_email(self):
        channels = self.router.get_channels("HIGH")
        assert AlertChannel.WEBSOCKET in channels
        assert AlertChannel.EMAIL in channels
        assert AlertChannel.PAGER not in channels

    def test_critical_gets_websocket_email_pager(self):
        channels = self.router.get_channels("CRITICAL")
        assert AlertChannel.WEBSOCKET in channels
        assert AlertChannel.EMAIL in channels
        assert AlertChannel.PAGER in channels

    def test_medium_inherits_lower_rules(self):
        channels = self.router.get_channels("MEDIUM")
        assert AlertChannel.WEBSOCKET in channels
        assert AlertChannel.EMAIL not in channels

    def test_low_inherits_info_rules(self):
        channels = self.router.get_channels("LOW")
        assert AlertChannel.WEBSOCKET in channels

    def test_or_number_filtering_match(self):
        rules = [
            RoutingRule(
                severity_min="INFO",
                channels=[AlertChannel.SMS],
                or_numbers=["OR-1", "OR-2"],
            ),
        ]
        router = AlertRouter(rules=rules)
        assert AlertChannel.SMS in router.get_channels("INFO", or_number="OR-1")
        assert AlertChannel.SMS in router.get_channels("INFO", or_number="OR-2")

    def test_or_number_filtering_no_match(self):
        rules = [
            RoutingRule(
                severity_min="INFO",
                channels=[AlertChannel.SMS],
                or_numbers=["OR-1", "OR-2"],
            ),
        ]
        router = AlertRouter(rules=rules)
        assert AlertChannel.SMS not in router.get_channels("INFO", or_number="OR-99")

    def test_or_number_none_matches_all(self):
        rules = [
            RoutingRule(severity_min="INFO", channels=[AlertChannel.SMS]),
        ]
        router = AlertRouter(rules=rules)
        assert AlertChannel.SMS in router.get_channels("INFO", or_number="OR-99")

    def test_unknown_severity_treated_as_zero(self):
        channels = self.router.get_channels("NONEXISTENT")
        assert AlertChannel.WEBSOCKET in channels

    def test_custom_rules_override_defaults(self):
        rules = [
            RoutingRule(severity_min="LOW", channels=[AlertChannel.WEBHOOK]),
        ]
        router = AlertRouter(rules=rules)
        channels = router.get_channels("LOW")
        assert AlertChannel.WEBHOOK in channels
        assert AlertChannel.WEBSOCKET not in channels

    def test_multiple_rules_accumulate_channels(self):
        rules = [
            RoutingRule(severity_min="INFO", channels=[AlertChannel.WEBSOCKET]),
            RoutingRule(severity_min="INFO", channels=[AlertChannel.EMAIL]),
        ]
        router = AlertRouter(rules=rules)
        channels = router.get_channels("INFO")
        assert AlertChannel.WEBSOCKET in channels
        assert AlertChannel.EMAIL in channels

    def test_empty_list_rules_falls_back_to_defaults(self):
        # Empty list is falsy → AlertRouter uses DEFAULT_RULES
        router = AlertRouter(rules=[])
        channels = router.get_channels("CRITICAL")
        assert AlertChannel.WEBSOCKET in channels


# ---------------------------------------------------------------------------
# RoutingRule construction
# ---------------------------------------------------------------------------

class TestRoutingRule:
    def test_default_recipients(self):
        rule = RoutingRule(severity_min="INFO", channels=[AlertChannel.EMAIL])
        assert rule.recipients == []

    def test_default_or_numbers_is_none(self):
        rule = RoutingRule(severity_min="INFO", channels=[AlertChannel.EMAIL])
        assert rule.or_numbers is None

    def test_custom_recipients(self):
        rule = RoutingRule(
            severity_min="HIGH",
            channels=[AlertChannel.EMAIL],
            recipients=["admin@test.com"],
        )
        assert "admin@test.com" in rule.recipients


# ---------------------------------------------------------------------------
# AlertChannel enum values
# ---------------------------------------------------------------------------

class TestAlertChannel:
    def test_all_channels_exist(self):
        assert AlertChannel.WEBSOCKET == "WEBSOCKET"
        assert AlertChannel.EMAIL == "EMAIL"
        assert AlertChannel.PAGER == "PAGER"
        assert AlertChannel.SMS == "SMS"
        assert AlertChannel.WEBHOOK == "WEBHOOK"

    def test_channel_count(self):
        assert len(AlertChannel) == 5


# ---------------------------------------------------------------------------
# AlertRouter lifecycle
# ---------------------------------------------------------------------------

class TestAlertRouterLifecycle:
    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        router = AlertRouter()
        await router.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_get_http_client_creates_client(self):
        router = AlertRouter()
        client = await router._get_http_client()
        assert client is not None
        assert not client.is_closed
        await client.aclose()

    @pytest.mark.asyncio
    async def test_get_http_client_reuses_existing(self):
        router = AlertRouter()
        client1 = await router._get_http_client()
        client2 = await router._get_http_client()
        assert client1 is client2
        await client1.aclose()

    @pytest.mark.asyncio
    async def test_route_alert_skips_unconfigured_channels(self):
        """With no SMTP/PagerDuty/SMS/webhook configured, only websocket fires."""
        router = AlertRouter()
        # Just verify it doesn't raise — channels check config and skip
        await router.route_alert({"severity": "CRITICAL", "message": "test"})
        await router.close()
