# InfectionIQ — System Architecture

> AI-powered surgical infection prevention through real-time computer vision monitoring of hand hygiene compliance.

---

## 1. High-Level Overview

```
                           +---------------------+
                           |   Operating Room     |
                           |                      |
                           |  [Camera]            |
                           +--------|------------+
                                    | RTSP / USB video
                                    v
                     +-----------------------------+
                     |      CV Module (Edge)        |
                     |  YOLOv8 + MediaPipe + FSM    |
                     |  Runs on Jetson / GPU host   |
                     +-------|---------------------+
                             | HTTP POST events (entry, exit, touch, sanitize)
                             | + heartbeat every 30s
                             v
+----------+    +-----------------------------------+    +------------+
|          |    |        FastAPI Backend             |    |            |
| Postgres |<-->|  REST API  |  WebSocket  |  Sched  |<-->|   Redis    |
|  (data)  |    |  /api/v1   |  /ws        |  tasks  |    |  (pubsub)  |
+----------+    +------|----------|--------|---------+    +------------+
                       |          |        |
          +------------+    +-----+        +--------+
          v                 v                       v
   +-----------+    +-----------+            +-----------+
   | React SPA |    | Grafana   |            | Prometheus|
   | Dashboard |    | :3001     |            | :9090     |
   | :80/:443  |    +-----------+            +-----------+
   +-----------+
```

**Six Docker services** compose the production stack:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| backend | Custom (Python 3.11) | 8000 | FastAPI API + WebSocket + scheduler |
| frontend | Custom (Node 20 build + nginx) | 80, 443 | React SPA + reverse proxy |
| postgres | postgres:16-alpine | 5432 | Primary data store |
| redis | redis:7-alpine | 6379 | PubSub, caching, session state |
| prometheus | prom/prometheus:v2.53.0 | 9090 | Metrics collection (30-day retention) |
| grafana | grafana/grafana:11.1.0 | 3001 | Dashboards + alerting UI |

---

## 2. CV Module — What Runs on the Camera Host

**Location:** `cv_module/`

The CV module is a standalone Python process that runs on an edge device (NVIDIA Jetson, GPU workstation, or any machine with a camera feed). It processes video frames in real time and publishes compliance events to the backend over HTTP.

### 2.1 Frame-by-Frame Pipeline

Every frame passes through 5 stages in sequence:

```
Frame (BGR, 1920x1080)
  |
  |  Stage 1: PERSON DETECTION
  |  Model: YOLOv8n (ultralytics)
  |  - Detects class 0 (person) at >= 50% confidence
  |  - Built-in tracker assigns persistent track_id per person
  |  - Fallback: OpenCV HOG detector if YOLO unavailable
  |  Output: List of (track_id, bbox, confidence)
  |
  v
  |  Stage 2: HAND TRACKING
  |  Model: MediaPipe Hands (Tasks API or Solutions API)
  |  - Crops each person's bounding box
  |  - Detects up to 2 hands per person (21 landmarks each)
  |  - Transforms landmarks from ROI coords back to full frame
  |  Output: Per-person list of (landmarks[], handedness, confidence)
  |
  v
  |  Stage 3: GESTURE CLASSIFICATION
  |  Algorithm: Multi-feature sliding window scorer
  |  - Maintains 30-frame history per person
  |  - Extracts 4 features from the window:
  |      palm_distance   — distance between left/right palms (closer = rubbing)
  |      palm_variance   — how much distance varies (rubbing oscillation)
  |      avg_motion      — average palm movement between frames
  |      oscillation_cnt — direction changes in palm distance (back-and-forth)
  |  - Weighted score: 0.30*palm_close + 0.20*variance + 0.20*motion + 0.30*oscillation
  |  - Must exceed 0.70 for >= 3 seconds with 2 hands visible >= 60% of frames
  |  Output: is_sanitizing (bool), score (0-1), feature breakdown
  |
  v
  |  Stage 4: ZONE DETECTION
  |  Algorithm: Ray-casting point-in-polygon
  |  - Maps palm center coordinates to OR zones:
  |      DOOR (risk 1) — entry/exit point
  |      SANITIZER (risk 0) — hand sanitizer location
  |      NON_STERILE (risk 3) — general OR area
  |      STERILE (risk 7) — sterile field boundary
  |      CRITICAL (risk 10) — surgical field
  |  - Zones are configurable polygons (normalized 0-1 coordinates)
  |  Output: zone name per hand position
  |
  v
  |  Stage 5: STATE MACHINE + EVENT PUBLISHING
  |  ContaminationFSM tracks each person's hygiene state:
  |
  |    UNKNOWN ──sanitize──> CLEAN ──touch non-sterile──> POTENTIALLY_CONTAMINATED
  |      ^                    |                              |
  |      |                    | (expires 5 min)              | touch sterile/critical
  |      |                    v                              v
  |      +──────────────── UNKNOWN                    CONTAMINATED ──> ALERT!
  |
  |  Events published via HTTP POST with retry + SQLite buffer:
  |    ENTRY     → POST /api/v1/compliance/entry
  |    EXIT      → POST /api/v1/compliance/exit
  |    TOUCH     → POST /api/v1/compliance/touch
  |    SANITIZE  → POST /api/v1/compliance/sanitize
  |
  v
Display annotated frame (bounding boxes, states, zones overlay)
```

### 2.2 Event Publisher Resilience

```
Event → HTTP POST attempt
        |
        +-- Success → done
        |
        +-- Fail → retry with exponential backoff (2s, 4s, 8s)
                |
                +-- All retries fail → buffer to local SQLite (cv_events_buffer.db)
                                        |
                                        +-- Periodic flush_buffer() retries all
                                        +-- Events deleted after 3 max retries
```

### 2.3 Heartbeat

Every 30 seconds, the CV module POSTs to `/api/v1/cameras/heartbeat`:
```json
{
  "camera_id": "cam-OR-1-1",
  "or_number": "OR-1",
  "status": "ONLINE",
  "fps": 28.5,
  "resolution": "1920x1080"
}
```
If the backend doesn't receive a heartbeat within 60 seconds, the **camera_health_check** scheduler task marks the camera OFFLINE and fires a `CAMERA_OFFLINE` alert.

### 2.4 Calibration Mode

Run with `--calibrate` flag:
1. Pipeline runs normally but records gesture feature vectors
2. Operator presses `s` (sanitizing) or `n` (not sanitizing) to label each observation
3. Press `q` to save labeled session as JSON
4. Upload session to `POST /api/v1/calibration/sessions`
5. Run threshold sweep: `POST /api/v1/calibration/sessions/{id}/sweep`
6. Apply best thresholds: `POST /api/v1/calibration/sessions/{id}/apply` (creates new immutable profile version)

---

## 3. Backend — What Runs in the API Server

**Location:** `backend/`
**Framework:** FastAPI (async) + SQLAlchemy (async) + Redis

### 3.1 Request Lifecycle

Every HTTP request passes through the middleware stack in this order:

```
Client Request
  |
  v
[1] MetricsMiddleware        — Start timer, record request
  |
  v
[2] TenantMiddleware         — Extract X-Tenant-ID header → request.state.tenant_id
  |                            Dev/test: defaults to 00000000-...-000001
  |                            Production: rejects API calls without tenant header
  v
[3] SecurityHeadersMiddleware — Adds X-Content-Type-Options, X-Frame-Options,
  |                            X-XSS-Protection, Referrer-Policy, HSTS
  v
[4] RateLimitMiddleware       — 120 requests/min per IP (skips /health, /docs, /metrics)
  |                            Returns 429 with Retry-After header if exceeded
  v
[5] AuditMiddleware           — Logs POST/PUT/PATCH/DELETE to AuditLog table
  |                            Records: user_id, method, path, IP, timestamp
  v
[6] CORSMiddleware            — Standard CORS headers from settings.CORS_ORIGINS
  |
  v
FastAPI Router → Handler → Response
  |
  v
[MetricsMiddleware]          — Record duration + status code to Prometheus
  |
  v
Client Response
```

### 3.2 API Surface (50+ Endpoints)

```
/api/v1/
  auth/
    POST /register              — Create account (email, password, full_name)
    POST /login                 — Get access + refresh tokens
    POST /refresh               — Refresh access token
    GET  /me                    — Current user profile
    PUT  /me                    — Update profile
    POST /change-password       — Change password

  cases/
    POST /                      — Create surgical case (captures active gesture profile)
    GET  /active                — List in-progress cases
    GET  /{case_id}             — Case detail + risk score
    PATCH /{case_id}            — Update case
    POST /{case_id}/start       — Start case (SCHEDULED → IN_PROGRESS)
    POST /{case_id}/end         — End case (→ COMPLETED)
    GET  /{case_id}/compliance  — Compliance breakdown (entries, touches, alerts)

  compliance/                   ← CV module pushes events here
    POST /entry                 — Person entered OR
    POST /exit                  — Person exited OR
    POST /touch                 — Person touched a zone
    POST /sanitize              — Person sanitized hands

  alerts/
    GET  /                      — All alerts (paginated)
    GET  /active                — Unresolved alerts
    POST /{id}/acknowledge      — Acknowledge alert
    POST /{id}/resolve          — Resolve alert

  analytics/
    GET  /dashboard             — Live dashboard metrics
    GET  /trends?days=N         — Compliance trend data
    GET  /violations            — Violation breakdown

  cameras/
    GET  /                      — List registered cameras
    GET  /{id}                  — Camera detail
    GET  /{id}/config           — Camera zone/threshold config
    POST /heartbeat             — Camera heartbeat (from CV module)
    GET  /health/summary        — Fleet health overview

  calibration/
    GET  /sessions              — List calibration sessions
    POST /sessions              — Upload calibration session
    POST /sessions/{id}/samples — Add samples (batch)
    POST /sessions/{id}/sweep   — Run threshold sweep (rate limited: 5/min)
    POST /sessions/{id}/apply   — Apply thresholds (creates new profile version)
    GET  /profiles/{name}/versions — List all versions of a profile

  staff/                        — CRUD for staff members
  dispensers/                   — Dispenser status + alerts
  consent/                      — HIPAA consent management
  fhir/                         — FHIR R4 resources (Procedure, Practitioner, etc.)
  sso/                          — SAML SSO (login, ACS, metadata, logout)
  reports/                      — CSV exports (compliance, cases, alerts)
  roi/                          — ROI calculator
  pricing/                      — Pricing tiers
  validation/                   — Clinical validation sessions

/ws/
  case/{case_id}/live           — WebSocket: live events for a case
  or/{or_number}/live           — WebSocket: live events for an OR
  alerts                        — WebSocket: all alerts
  dashboard                     — WebSocket: dashboard metric updates

/                               — Root health check
/health                         — Component health (DB, Redis, scheduler, cameras)
/metrics                        — Prometheus metrics (12 metric families)
```

### 3.3 Data Flow: CV Event → Dashboard

This is the complete path from a camera detecting a hand hygiene event to the dashboard updating:

```
1. CV Module detects sanitization gesture
   |
2. POST /api/v1/compliance/entry  {or_number, person_track_id, compliant: true, ...}
   |
3. Backend ComplianceService:
   |  a) INSERT into entry_exit_events table (Postgres)
   |  b) RedisPubSub.publish_case_event(case_id, "ENTRY", data)
   |  c) RedisPubSub.publish_or_event(or_number, "ENTRY", data)
   |
4. Redis pub/sub broadcasts on channels:
   |  - infectioniq:case:{case_id}
   |  - infectioniq:or:{or_number}
   |
5. WebSocket redis_listener() (running in background):
   |  - Subscribes to relevant channels
   |  - Receives message from Redis
   |  - ConnectionManager.broadcast() to all connected clients on that channel
   |
6. Frontend useWebSocket hook receives JSON message
   |
7. React component updates:
   |  - appStore.addAlert() if violation
   |  - Re-render compliance counters, live feed, status indicators
   |
8. Dashboard shows updated compliance rate in real time
```

### 3.4 Risk Prediction Engine

When a surgical case is created, the system calculates an SSI (Surgical Site Infection) risk score:

```
Case Created
  |
  v
RiskService.predict_risk(case)
  |
  |  Feature Extraction (queries last 7-90 days of data):
  |    team_compliance_7d     — Team hand hygiene rate (7-day avg)
  |    team_compliance_30d    — Team hand hygiene rate (30-day avg)
  |    team_infection_count   — Infections in last 90 days
  |    surgeon_compliance     — Surgeon's personal compliance (30d)
  |    duration               — Expected surgery duration (hours)
  |    complexity_score       — Procedure complexity (1-10)
  |    wound_class            — CLEAN / CLEAN_CONTAMINATED / CONTAMINATED / DIRTY
  |    implant_flag           — Implant present (higher infection risk)
  |    emergency_flag         — Emergency surgery
  |    night_shift            — Surgery during night hours
  |    weekend                — Weekend surgery
  |
  v
Weighted Score Calculation (0-100):
  team_infection_count:  18% weight
  team_compliance:       15% weight
  duration:              12% weight
  surgeon_compliance:    11% weight
  wound_class:           10% weight
  complexity:             8% weight
  implant_flag:           7% weight
  emergency_flag:         6% weight
  team_compliance_30d:    5% weight
  temporal factors:       8% weight
  |
  v
Risk Level:
  0-25   → LOW
  26-50  → MODERATE
  51-75  → HIGH
  76-100 → CRITICAL
  |
  v
Output: {score, risk_level, top_5_factors, top_5_recommendations}
  |
  v
Stored in risk_scores table, returned with case response
```

### 3.5 Background Scheduler (4 Tasks)

```
TaskScheduler (runs in asyncio event loop, checks every 10s)
  |
  +-- daily_report         (every 24h)  — Generate compliance summary, publish to dashboard
  +-- audit_cleanup        (every 24h)  — Delete audit logs older than AUDIT_RETENTION_DAYS
  +-- dispenser_check      (every 5min) — Check dispenser levels, alert if < 20%
  +-- camera_health_check  (every 60s)  — Detect offline cameras, fire CAMERA_OFFLINE alerts
```

Each task execution is instrumented with Prometheus:
- `infectioniq_scheduled_task_duration_seconds` (histogram)
- `infectioniq_scheduled_task_failures_total` (counter)

### 3.6 Alert Routing (5 Channels)

When any part of the system generates an alert:

```
alert_router.route_alert({type, severity, message, ...})
  |
  |  Severity determines channels (configurable rules):
  |    INFO     → [WebSocket]
  |    HIGH     → [WebSocket, Email]
  |    CRITICAL → [WebSocket, Email, PagerDuty]
  |
  +→ WEBSOCKET  — RedisPubSub → WebSocket → Frontend toast/badge
  +→ EMAIL      — SMTP with HTML template (sender, recipients from config)
  +→ PAGERDUTY  — Events API v2 (trigger incident)
  +→ SMS        — Configurable webhook (Twilio, MessageBird, etc.)
  +→ WEBHOOK    — Generic POST with HMAC-SHA256 signature
  |
  v
Each send increments Prometheus counter:
  infectioniq_alerts_sent_total{alert_type, severity, channel}
  infectioniq_alerts_failed_total{alert_type, channel}  (on error)
```

### 3.7 Multi-Tenant Isolation

```
Request arrives
  |
  v
TenantMiddleware extracts X-Tenant-ID header (or subdomain)
  |
  +-- Found → set request.state.tenant_id
  +-- Not found:
       +-- Dev/Test → default org (00000000-...-000001)
       +-- Production → 400 "X-Tenant-ID header required"
  |
  v
get_current_user() validates:
  user.organization_id == request.state.tenant_id
  (superusers bypass this check)
  |
  v
Queries can use get_tenant_query_filter(Model, org_id)
  → adds WHERE model.organization_id = :org_id
```

**Models with organization_id FK:**
Staff, SurgicalCase, GestureProfile, GestureCalibrationSession, User

### 3.8 GestureProfile Versioning

Profiles are **immutable** — applying new thresholds always creates a new version:

```
POST /calibration/sessions/{id}/apply
  |
  v
Query: SELECT MAX(version) FROM gesture_profiles WHERE name = :name
  |
  v
INSERT new row with version = max + 1
  (never UPDATE existing rows)
  |
  v
SurgicalCase created → captures gesture_profile_id of latest version
  → You can always trace which thresholds were active during any case
```

---

## 4. Frontend — What Runs in the Browser

**Location:** `frontend/`
**Stack:** React 18 + TypeScript + Zustand + React Router v6

### 4.1 Page Routing

```
/login                    → LoginPage (public)
/sso-callback             → SSOCallbackPage (public)
                          ↓ (ProtectedRoute checks authStore.isAuthenticated)
/                         → DashboardPage (live metrics, alerts, compliance)
/case/:caseId             → CasePage (single case detail + live event feed)
/analytics                → AnalyticsPage (trends, violations, reports)
/staff                    → StaffPage (staff management)
/dispensers               → DispensersPage (dispenser levels + alerts)
/calibration              → ZoneCalibrationPage (zone polygon editor)
/gesture-calibration      → GestureCalibrationPage (threshold tuning)
/roi                      → ROICalculatorPage
/pricing                  → PricingPage
```

### 4.2 State Management

```
authStore (Zustand + localStorage persistence)
  |-- user, accessToken, refreshToken, isAuthenticated
  |-- login(), register(), logout(), fetchUser()
  |-- setTokensFromSSO() for SAML callback

appStore (Zustand, in-memory)
  |-- activeCases[], alerts[], metrics, dispensers[]
  |-- wsConnected flag
  |-- addAlert() — prepends + limits to 50
  |-- acknowledgeAlert(id)
```

### 4.3 WebSocket Connection

```
useWebSocket('/case/123/live', {
  onMessage: (data) => { /* update UI */ },
  autoReconnect: true   // 3-second retry interval
})
  |
  v
Connects to: ws://host/ws/case/123/live?token=<jwt>
  |
  v
Receives JSON messages (entry events, alerts, state changes)
  |
  v
React re-renders affected components
```

### 4.4 Build & Serving

```
Multi-stage Docker build:
  Stage 1 (node:20-alpine):  npm ci → npm run build → /app/dist
  Stage 2 (nginx:alpine):     Copy dist → nginx serves at :80/:443

Nginx routing:
  /            → SPA (index.html fallback)
  /api/*       → Proxy to backend:8000 (10s connect, 30s read)
  /ws/*        → WebSocket proxy to backend:8000 (1hr timeout)
  /assets/*    → Static files (1-year cache, immutable)

Security:
  HTTP → 301 redirect to HTTPS
  HSTS: max-age=31536000
  CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff
  API rate limit: 30 req/s burst 20
```

---

## 5. Monitoring — What Watches Everything

### 5.1 Prometheus Metrics (12 Families)

| Metric | Type | Labels | What It Measures |
|--------|------|--------|------------------|
| `infectioniq_http_requests_total` | Counter | method, endpoint, status | Every HTTP request |
| `infectioniq_http_request_duration_seconds` | Histogram | method, endpoint | Request latency distribution |
| `infectioniq_websocket_connections_active` | Gauge | — | Live WebSocket count |
| `infectioniq_alerts_sent_total` | Counter | alert_type, severity, channel | Successful alert deliveries |
| `infectioniq_alerts_failed_total` | Counter | alert_type, channel | Failed alert deliveries |
| `infectioniq_cameras_registered_total` | Gauge | — | Total cameras in registry |
| `infectioniq_cameras_online` | Gauge | — | Cameras with recent heartbeat |
| `infectioniq_cameras_offline` | Gauge | — | Stale cameras (no heartbeat > 60s) |
| `infectioniq_camera_heartbeat_age_seconds` | Gauge | camera_id, or_number | Seconds since last heartbeat |
| `infectioniq_cases_active` | Gauge | — | Cases currently IN_PROGRESS |
| `infectioniq_scheduled_task_duration_seconds` | Histogram | task_name | Background task execution time |
| `infectioniq_scheduled_task_failures_total` | Counter | task_name | Background task failures |

### 5.2 Grafana Dashboard (16 Panels)

```
Row 1: HTTP Traffic
  [Request Rate (RPS)]  [Response Time p50/p95/p99]
  [Requests by Endpoint Top 10]  [Error Rate by Endpoint]

Row 2: Camera Fleet
  [Online stat]  [Offline stat (red>0)]  [Total stat]  [Heartbeat Age table]

Row 3: Alerts & Operations
  [Alerts by Type (stacked)]  [Alert Failures by Channel]
  [Severity pie]  [Channel pie]  [WS connections]  [Active cases]

Row 4: Background Scheduler
  [Task Duration p95]  [Task Failures rate]

Row 5: Endpoint Latency
  [Bar gauge: p95 latency for top 15 endpoints, color-coded]
```

### 5.3 Health Endpoint (`GET /health`)

Returns component-level health:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": 1700000000.0,
  "components": {
    "database":  {"status": "connected"},
    "redis":     {"status": "connected"},
    "scheduler": {"tasks": [{"name": "daily_report", "is_running": false, ...}, ...]},
    "cameras":   {"total": 8, "online": 7, "offline": 1, "health_percent": 87.5}
  }
}
```

---

## 6. Security Layers

```
Internet
  |
  v
[Nginx] — HTTPS termination, HSTS, CSP, rate limit (30 req/s)
  |
  v
[FastAPI Middleware Stack]
  |-- SecurityHeadersMiddleware (X-Frame-Options, X-XSS-Protection, etc.)
  |-- RateLimitMiddleware (120 req/min per IP, per-endpoint limits)
  |-- TenantMiddleware (org isolation)
  |-- AuditMiddleware (HIPAA audit trail for mutating requests)
  |
  v
[Authentication]
  |-- JWT tokens (access: 30min, refresh: 7d)
  |-- SAML SSO for enterprise
  |-- Password policy: 8+ chars, uppercase, digit, special char
  |-- Tenant validation: user.org_id must match X-Tenant-ID
  |
  v
[Authorization]
  |-- Role-based: ADMIN, MANAGER, NURSE, SURGEON, TECHNICIAN, VIEWER
  |-- Superuser bypass for cross-tenant operations
  |
  v
[Data Protection]
  |-- PHI encryption at rest (Fernet, PHI_ENCRYPTION_KEY)
  |-- Config validation at startup (rejects weak secrets, SQLite in prod)
  |-- Consent management (DATA_COLLECTION, AI_MONITORING, VIDEO_RECORDING, etc.)
  |-- Audit log retention: 90 days default, configurable
```

---

## 7. Database Schema (Key Tables)

```
organizations (multi-tenant root)
  |
  +--< users (email, password_hash, role, organization_id)
  +--< staff (name, role, department, organization_id)
  +--< surgical_cases (or_number, procedure, surgeon_id, gesture_profile_id, organization_id)
  |      +--< entry_exit_events (person_track_id, compliant, timestamp)
  |      +--< touch_events (zone, hand, state_before, state_after)
  |      +--< alerts (type, severity, message, acknowledged, resolved)
  |      +--< risk_scores (score, risk_level, factors, recommendations)
  |      +--< infection_outcomes (infection_detected, organism, ssi_date)
  |
  +--< gesture_profiles (name, or_number, version, thresholds, is_default, organization_id)
  |      +--< gesture_calibration_sessions → gesture_calibration_samples
  |
  +--< dispensers → dispenser_statuses → dispense_events
  +--< audit_logs (user_id, action, path, ip, timestamp)
  +--< patient_consents (patient_id, consent_type, status, granted_by)
  +--< validation_sessions → validation_observations
```

---

## 8. How to Run Each Component

### Development (local)

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install && npm run dev

# Terminal 3: CV Module (with webcam)
cd cv_module
python src/main.py --source 0 --backend http://localhost:8000 --or-number OR-1

# Terminal 3 alt: CV Module (with video file)
python src/main.py --video test_surgery.mp4 --backend http://localhost:8000 --or-number OR-1
```

### Docker (production-like)

```bash
docker-compose up --build -d

# Verify:
curl http://localhost:8000/health    # Backend
curl http://localhost:9090/-/healthy # Prometheus
curl http://localhost:3001/api/health # Grafana (login: admin / infectioniq)

# CV module runs on the camera host, pointed at Docker backend:
python cv_module/src/main.py --source rtsp://camera-ip/stream --backend http://server-ip:8000 --or-number OR-1
```

### Load Testing

```bash
cd backend
# Smoke (10 users, 1 min)
locust -f tests/locustfile.py --headless -u 10 -r 5 -t 60s --host http://localhost:8000

# Standard (50 users, 5 min)
locust -f tests/locustfile.py --headless -u 50 -r 10 -t 5m --host http://localhost:8000

# Interactive (browser UI at localhost:8089)
locust -f tests/locustfile.py --host http://localhost:8000
```
