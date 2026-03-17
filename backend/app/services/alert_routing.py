"""
Alert Routing Service
Configurable alert dispatching to email, pager, WebSocket, SMS, and webhooks.
"""

import asyncio
import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum

import httpx

from app.core.redis import RedisPubSub
from app.config import settings

logger = logging.getLogger(__name__)


class AlertChannel(str, Enum):
    WEBSOCKET = "WEBSOCKET"
    EMAIL = "EMAIL"
    PAGER = "PAGER"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"


@dataclass
class RoutingRule:
    severity_min: str
    channels: List[AlertChannel]
    recipients: List[str] = field(default_factory=list)
    or_numbers: Optional[List[str]] = None


DEFAULT_RULES: List[RoutingRule] = [
    RoutingRule(severity_min="INFO", channels=[AlertChannel.WEBSOCKET]),
    RoutingRule(severity_min="HIGH", channels=[AlertChannel.WEBSOCKET, AlertChannel.EMAIL]),
    RoutingRule(severity_min="CRITICAL", channels=[AlertChannel.WEBSOCKET, AlertChannel.EMAIL, AlertChannel.PAGER]),
]

SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class AlertRouter:
    def __init__(self, rules: Optional[List[RoutingRule]] = None):
        self.rules = rules or DEFAULT_RULES
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    def get_channels(self, severity: str, or_number: Optional[str] = None) -> List[AlertChannel]:
        channels = set()
        sev_level = SEVERITY_ORDER.get(severity, 0)
        for rule in self.rules:
            rule_level = SEVERITY_ORDER.get(rule.severity_min, 0)
            if sev_level >= rule_level:
                if rule.or_numbers is None or (or_number and or_number in rule.or_numbers):
                    channels.update(rule.channels)
        return list(channels)

    async def route_alert(self, alert_data: dict):
        severity = alert_data.get("severity", "INFO")
        or_number = alert_data.get("or_number")
        channels = self.get_channels(severity, or_number)

        alert_type = alert_data.get("type", "unknown")
        for channel in channels:
            try:
                if channel == AlertChannel.WEBSOCKET:
                    await self._send_websocket(alert_data)
                elif channel == AlertChannel.EMAIL:
                    await self._send_email(alert_data)
                elif channel == AlertChannel.PAGER:
                    await self._send_pager(alert_data)
                elif channel == AlertChannel.SMS:
                    await self._send_sms(alert_data)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook(alert_data)
                # Prometheus: count successful sends
                from app.core.metrics import alerts_sent_total
                alerts_sent_total.labels(
                    alert_type=alert_type, severity=severity, channel=channel.value
                ).inc()
            except Exception as e:
                logger.error(f"Failed to route alert via {channel}: {e}")
                from app.core.metrics import alerts_failed_total
                alerts_failed_total.labels(alert_type=alert_type, channel=channel.value).inc()

    async def _send_websocket(self, alert_data: dict):
        await RedisPubSub.publish_alert(alert_data)

    async def _send_email(self, alert_data: dict):
        """Send alert via SMTP email"""
        if not settings.SMTP_HOST:
            logger.debug("[EMAIL] SMTP not configured, skipping")
            return
        if not settings.ALERT_EMAIL_RECIPIENTS:
            logger.debug("[EMAIL] No recipients configured, skipping")
            return

        severity = alert_data.get("severity", "INFO")
        message = alert_data.get("message", "No message")
        case_id = alert_data.get("case_id", "N/A")
        timestamp = alert_data.get("timestamp", datetime.utcnow().isoformat())

        subject = f"[InfectionIQ {severity}] {message[:80]}"
        html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;">
<div style="background:{'#dc2626' if severity=='CRITICAL' else '#f59e0b' if severity=='HIGH' else '#3b82f6'};
            color:white;padding:16px;border-radius:8px 8px 0 0;">
<h2 style="margin:0;">InfectionIQ Alert — {severity}</h2></div>
<div style="border:1px solid #e5e7eb;padding:20px;border-radius:0 0 8px 8px;">
<p><strong>Message:</strong> {message}</p>
<p><strong>Case ID:</strong> {case_id}</p>
<p><strong>Time:</strong> {timestamp}</p>
<p><strong>OR:</strong> {alert_data.get('or_number', 'N/A')}</p>
<hr style="border:none;border-top:1px solid #e5e7eb;">
<p style="color:#6b7280;font-size:12px;">Automated alert from InfectionIQ. Do not reply.</p>
</div></div>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = ", ".join(settings.ALERT_EMAIL_RECIPIENTS)
        msg.attach(MIMEText(message, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        def _send():
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, settings.ALERT_EMAIL_RECIPIENTS, msg.as_string())

        await asyncio.to_thread(_send)
        logger.info(f"[EMAIL] Sent alert to {len(settings.ALERT_EMAIL_RECIPIENTS)} recipients")

    async def _send_pager(self, alert_data: dict):
        """Create PagerDuty incident via Events API v2"""
        if not settings.PAGERDUTY_ROUTING_KEY:
            logger.debug("[PAGER] PagerDuty not configured, skipping")
            return

        severity_map = {"CRITICAL": "critical", "HIGH": "error", "MEDIUM": "warning", "LOW": "info", "INFO": "info"}
        payload = {
            "routing_key": settings.PAGERDUTY_ROUTING_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": alert_data.get("message", "InfectionIQ Alert"),
                "source": f"InfectionIQ OR:{alert_data.get('or_number', 'unknown')}",
                "severity": severity_map.get(alert_data.get("severity", "INFO"), "info"),
                "custom_details": {
                    "case_id": alert_data.get("case_id"),
                    "or_number": alert_data.get("or_number"),
                    "alert_type": alert_data.get("type"),
                }
            }
        }
        client = await self._get_http_client()
        resp = await client.post("https://events.pagerduty.com/v2/enqueue", json=payload)
        resp.raise_for_status()
        logger.info(f"[PAGER] PagerDuty incident created")

    async def _send_sms(self, alert_data: dict):
        """Send SMS via configurable webhook (Twilio, MessageBird, etc.)"""
        if not settings.SMS_WEBHOOK_URL:
            logger.debug("[SMS] Webhook not configured, skipping")
            return

        payload = {
            "message": f"[InfectionIQ {alert_data.get('severity')}] {alert_data.get('message', '')}",
            "severity": alert_data.get("severity"),
            "case_id": alert_data.get("case_id"),
            "timestamp": alert_data.get("timestamp", datetime.utcnow().isoformat()),
        }
        headers = {}
        if settings.SMS_WEBHOOK_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {settings.SMS_WEBHOOK_AUTH_TOKEN}"

        client = await self._get_http_client()
        resp = await client.post(settings.SMS_WEBHOOK_URL, json=payload, headers=headers)
        resp.raise_for_status()
        logger.info("[SMS] Alert sent via webhook")

    async def _send_webhook(self, alert_data: dict):
        """Send alert to configured webhook URL with HMAC signature"""
        if not settings.WEBHOOK_ALERT_URL:
            logger.debug("[WEBHOOK] URL not configured, skipping")
            return

        headers = {"Content-Type": "application/json"}
        if settings.WEBHOOK_ALERT_SECRET:
            import hashlib
            import hmac
            body = json.dumps(alert_data, default=str)
            sig = hmac.new(settings.WEBHOOK_ALERT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Signature-SHA256"] = sig

        client = await self._get_http_client()
        resp = await client.post(settings.WEBHOOK_ALERT_URL, json=alert_data, headers=headers)
        resp.raise_for_status()
        logger.info(f"[WEBHOOK] Alert posted to webhook")

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


alert_router = AlertRouter()
