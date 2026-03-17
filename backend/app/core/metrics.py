"""
Prometheus Metrics Definitions for InfectionIQ

All application metrics are defined here as a single source of truth.
Import individual metrics where needed.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "infectioniq_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "infectioniq_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

websocket_connections_active = Gauge(
    "infectioniq_websocket_connections_active",
    "Currently active WebSocket connections",
)

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

alerts_sent_total = Counter(
    "infectioniq_alerts_sent_total",
    "Total alerts routed successfully",
    ["alert_type", "severity", "channel"],
)

alerts_failed_total = Counter(
    "infectioniq_alerts_failed_total",
    "Total alert routing failures",
    ["alert_type", "channel"],
)

# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

cameras_registered_total = Gauge(
    "infectioniq_cameras_registered_total",
    "Total cameras in the heartbeat registry",
)

cameras_online = Gauge(
    "infectioniq_cameras_online",
    "Number of cameras with ONLINE status",
)

cameras_offline = Gauge(
    "infectioniq_cameras_offline",
    "Number of cameras with OFFLINE status",
)

camera_heartbeat_age_seconds = Gauge(
    "infectioniq_camera_heartbeat_age_seconds",
    "Seconds since last heartbeat per camera",
    ["camera_id", "or_number"],
)

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

cases_active = Gauge(
    "infectioniq_cases_active",
    "Number of surgical cases currently IN_PROGRESS",
)

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduled_task_duration_seconds = Histogram(
    "infectioniq_scheduled_task_duration_seconds",
    "Duration of scheduled background tasks",
    ["task_name"],
)

scheduled_task_failures_total = Counter(
    "infectioniq_scheduled_task_failures_total",
    "Total scheduled task failures",
    ["task_name"],
)

# ---------------------------------------------------------------------------
# App info
# ---------------------------------------------------------------------------

app_info = Info(
    "infectioniq_app",
    "InfectionIQ application metadata",
)

def _init_app_info():
    from app.config import settings
    app_info.info({"version": settings.APP_VERSION, "service": "infectioniq-backend"})

_init_app_info()
