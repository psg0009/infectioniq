"""
InfectionIQ Load Test Suite
============================
Comprehensive load tests covering all API surface areas.

Quick smoke test (1 min, 10 users):
  locust -f tests/locustfile.py --headless -u 10 -r 5 -t 60s --host http://localhost:8000

Standard load test (5 min, 50 users):
  locust -f tests/locustfile.py --headless -u 50 -r 10 -t 5m --host http://localhost:8000 --csv=tests/loadtest_results

Stress test (10 min, 200 users):
  locust -f tests/locustfile.py --headless -u 200 -r 25 -t 10m --host http://localhost:8000 --csv=tests/stress_results

Web UI mode:
  locust -f tests/locustfile.py --host http://localhost:8000
  Then open http://localhost:8089
"""

from locust import HttpUser, task, between, tag, events
import json
import random
import uuid
import time


# Shared state across users
_created_case_ids: list = []
_or_numbers = [f"OR-{i}" for i in range(1, 9)]
_procedure_types = [
    "TOTAL_KNEE_REPLACEMENT", "HIP_ARTHROPLASTY", "SPINAL_FUSION",
    "APPENDECTOMY", "CORONARY_BYPASS", "LAPAROSCOPIC_CHOLECYSTECTOMY",
]
_wound_classes = ["CLEAN", "CLEAN_CONTAMINATED", "CONTAMINATED"]

DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"


# ── Helper ──────────────────────────────────────────────────────────────────

def _auth_headers(token, tenant=DEFAULT_TENANT):
    h = {"X-Tenant-ID": tenant}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ── User Classes ────────────────────────────────────────────────────────────

class DashboardViewer(HttpUser):
    """
    Simulates a nurse/manager who primarily monitors the dashboard,
    checks alerts, and reviews compliance data.  High-frequency reads.
    """
    weight = 5
    wait_time = between(0.5, 2)

    def on_start(self):
        rand = random.randint(100_000, 999_999)
        self.email = f"viewer_{rand}@loadtest.infectioniq.dev"
        self.password = "LoadTest!2025"
        self.tenant = DEFAULT_TENANT

        resp = self.client.post("/api/v1/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": f"Viewer {rand}",
        }, headers={"X-Tenant-ID": self.tenant})

        if resp.status_code == 201:
            self.token = resp.json().get("access_token")
        else:
            resp = self.client.post("/api/v1/auth/login", json={
                "email": self.email,
                "password": self.password,
            }, headers={"X-Tenant-ID": self.tenant})
            self.token = resp.json().get("access_token") if resp.ok else None

        self.headers = _auth_headers(self.token, self.tenant)

    # ── Dashboard reads (heaviest traffic) ──────────────────────────────

    @task(10)
    @tag("dashboard", "read")
    def dashboard_metrics(self):
        self.client.get("/api/v1/analytics/dashboard", headers=self.headers)

    @task(6)
    @tag("dashboard", "read")
    def analytics_trends(self):
        days = random.choice([7, 14, 30])
        self.client.get(f"/api/v1/analytics/trends?days={days}", headers=self.headers)

    @task(4)
    @tag("dashboard", "read")
    def analytics_violations(self):
        self.client.get("/api/v1/analytics/violations", headers=self.headers)

    # ── Alerts ──────────────────────────────────────────────────────────

    @task(5)
    @tag("alerts", "read")
    def list_alerts(self):
        self.client.get("/api/v1/alerts/", headers=self.headers)

    @task(3)
    @tag("alerts", "read")
    def active_alerts(self):
        self.client.get("/api/v1/alerts/active", headers=self.headers)

    # ── Staff / dispensers ──────────────────────────────────────────────

    @task(3)
    @tag("staff", "read")
    def list_staff(self):
        self.client.get("/api/v1/staff/", headers=self.headers)

    @task(3)
    @tag("dispensers", "read")
    def list_dispensers(self):
        self.client.get("/api/v1/dispensers/", headers=self.headers)

    @task(2)
    @tag("dispensers", "read")
    def dispenser_alerts(self):
        self.client.get("/api/v1/dispensers/alerts/active", headers=self.headers)

    # ── Reports ─────────────────────────────────────────────────────────

    @task(1)
    @tag("reports", "read")
    def report_summary(self):
        self.client.get("/api/v1/reports/summary", headers=self.headers)

    @task(1)
    @tag("reports", "read")
    def compliance_csv(self):
        self.client.get("/api/v1/reports/compliance/csv", headers=self.headers)

    # ── Health / infra ──────────────────────────────────────────────────

    @task(2)
    @tag("health")
    def health_check(self):
        self.client.get("/health")

    @task(1)
    @tag("health")
    def root(self):
        self.client.get("/")

    @task(1)
    @tag("profile", "read")
    def user_profile(self):
        self.client.get("/api/v1/auth/me", headers=self.headers)


class SurgicalOperator(HttpUser):
    """
    Simulates a charge nurse or surgeon who creates cases,
    logs compliance events, and interacts with cameras.  Mix of reads & writes.
    """
    weight = 3
    wait_time = between(1, 3)

    def on_start(self):
        rand = random.randint(100_000, 999_999)
        self.email = f"operator_{rand}@loadtest.infectioniq.dev"
        self.password = "LoadTest!2025"
        self.tenant = DEFAULT_TENANT

        resp = self.client.post("/api/v1/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": f"Operator {rand}",
        }, headers={"X-Tenant-ID": self.tenant})

        if resp.status_code == 201:
            self.token = resp.json().get("access_token")
        else:
            resp = self.client.post("/api/v1/auth/login", json={
                "email": self.email,
                "password": self.password,
            }, headers={"X-Tenant-ID": self.tenant})
            self.token = resp.json().get("access_token") if resp.ok else None

        self.headers = _auth_headers(self.token, self.tenant)
        self.my_case_ids: list = []

    # ── Case lifecycle ──────────────────────────────────────────────────

    @task(3)
    @tag("cases", "write")
    def create_case(self):
        or_num = random.choice(_or_numbers)
        resp = self.client.post("/api/v1/cases/", json={
            "or_number": or_num,
            "start_time": "2025-06-15T08:00:00",
            "procedure_type": random.choice(_procedure_types),
            "procedure_code": f"CPT-{random.randint(10000, 99999)}",
            "surgeon_id": str(uuid.uuid4()),
            "patient_id": f"PAT-{random.randint(1000, 9999)}",
            "wound_class": random.choice(_wound_classes),
            "expected_duration_hrs": round(random.uniform(0.5, 6.0), 1),
            "complexity_score": round(random.uniform(1.0, 10.0), 1),
            "implant_flag": random.choice([True, False]),
            "emergency_flag": False,
        }, headers=self.headers)

        if resp.ok:
            case_id = resp.json().get("id")
            if case_id:
                self.my_case_ids.append(case_id)
                _created_case_ids.append(case_id)

    @task(4)
    @tag("cases", "read")
    def get_active_cases(self):
        self.client.get("/api/v1/cases/active", headers=self.headers)

    @task(2)
    @tag("cases", "read")
    def get_case_detail(self):
        if self.my_case_ids:
            cid = random.choice(self.my_case_ids)
            self.client.get(f"/api/v1/cases/{cid}", headers=self.headers)

    @task(2)
    @tag("cases", "read")
    def get_case_compliance(self):
        if self.my_case_ids:
            cid = random.choice(self.my_case_ids)
            self.client.get(f"/api/v1/cases/{cid}/compliance", headers=self.headers)

    # ── Compliance events ───────────────────────────────────────────────

    @task(4)
    @tag("compliance", "write")
    def log_entry_event(self):
        self.client.post("/api/v1/compliance/entry", json={
            "or_number": random.choice(_or_numbers),
            "person_track_id": random.randint(1, 50),
            "compliant": random.random() > 0.15,
            "confidence": round(random.uniform(0.7, 1.0), 2),
        }, headers=self.headers)

    @task(2)
    @tag("compliance", "write")
    def log_sanitize_event(self):
        self.client.post("/api/v1/compliance/sanitize", json={
            "or_number": random.choice(_or_numbers),
            "person_track_id": random.randint(1, 50),
            "dispenser_id": str(uuid.uuid4()),
        }, headers=self.headers)

    # ── Camera heartbeats ───────────────────────────────────────────────

    @task(3)
    @tag("cameras", "write")
    def camera_heartbeat(self):
        or_num = random.choice(_or_numbers)
        self.client.post("/api/v1/cameras/heartbeat", json={
            "camera_id": f"cam-{or_num}-{random.randint(1, 3)}",
            "or_number": or_num,
            "status": "ONLINE",
            "fps": round(random.uniform(25, 30), 1),
            "resolution": "1920x1080",
        }, headers=self.headers)

    @task(2)
    @tag("cameras", "read")
    def camera_health_summary(self):
        self.client.get("/api/v1/cameras/health/summary", headers=self.headers)

    @task(1)
    @tag("cameras", "read")
    def list_cameras(self):
        self.client.get("/api/v1/cameras/", headers=self.headers)


class IntegrationUser(HttpUser):
    """
    Simulates external integrations: FHIR queries, ROI calculator,
    pricing page, SSO, consent management, and calibration reads.
    Low-frequency, bursty traffic.
    """
    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        rand = random.randint(100_000, 999_999)
        self.email = f"integrator_{rand}@loadtest.infectioniq.dev"
        self.password = "LoadTest!2025"
        self.tenant = DEFAULT_TENANT

        resp = self.client.post("/api/v1/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": f"Integrator {rand}",
        }, headers={"X-Tenant-ID": self.tenant})

        if resp.status_code == 201:
            self.token = resp.json().get("access_token")
        else:
            resp = self.client.post("/api/v1/auth/login", json={
                "email": self.email,
                "password": self.password,
            }, headers={"X-Tenant-ID": self.tenant})
            self.token = resp.json().get("access_token") if resp.ok else None

        self.headers = _auth_headers(self.token, self.tenant)

    # ── FHIR ────────────────────────────────────────────────────────────

    @task(3)
    @tag("fhir", "read")
    def fhir_metadata(self):
        self.client.get("/api/v1/fhir/metadata", headers=self.headers)

    @task(1)
    @tag("fhir", "read")
    def fhir_procedure(self):
        if _created_case_ids:
            cid = random.choice(_created_case_ids)
            self.client.get(f"/api/v1/fhir/Procedure/{cid}", headers=self.headers,
                            name="/api/v1/fhir/Procedure/{case_id}")

    # ── ROI / Pricing ───────────────────────────────────────────────────

    @task(2)
    @tag("roi", "read")
    def roi_calculate(self):
        self.client.post("/api/v1/roi/calculate", json={
            "num_ors": random.randint(2, 20),
            "avg_cases_per_or_per_day": random.randint(3, 10),
            "current_ssi_rate": round(random.uniform(1.0, 5.0), 1),
            "avg_cost_per_ssi": random.choice([20000, 25000, 30000, 40000]),
        }, headers=self.headers)

    @task(2)
    @tag("pricing", "read")
    def pricing_tiers(self):
        self.client.get("/api/v1/pricing/", headers=self.headers)

    # ── Consent ─────────────────────────────────────────────────────────

    @task(2)
    @tag("consent", "write")
    def record_consent(self):
        patient_id = f"PAT-{random.randint(1000, 9999)}"
        self.client.post("/api/v1/consent/", json={
            "patient_id": patient_id,
            "consent_type": random.choice([
                "DATA_COLLECTION", "AI_MONITORING", "VIDEO_RECORDING",
            ]),
            "granted_by": self.email,
        }, headers=self.headers)

    @task(2)
    @tag("consent", "read")
    def check_consent_status(self):
        patient_id = f"PAT-{random.randint(1000, 9999)}"
        self.client.get(f"/api/v1/consent/patient/{patient_id}/status",
                        headers=self.headers,
                        name="/api/v1/consent/patient/{id}/status")

    # ── Calibration (read-only in load test) ────────────────────────────

    @task(1)
    @tag("calibration", "read")
    def list_calibration_sessions(self):
        self.client.get("/api/v1/calibration/sessions", headers=self.headers)

    @task(1)
    @tag("calibration", "read")
    def profile_versions(self):
        name = random.choice(["default", "high_sensitivity", "standard"])
        self.client.get(f"/api/v1/calibration/profiles/{name}/versions",
                        headers=self.headers,
                        name="/api/v1/calibration/profiles/{name}/versions")

    # ── SSO metadata ────────────────────────────────────────────────────

    @task(1)
    @tag("sso", "read")
    def sso_metadata(self):
        self.client.get("/api/v1/sso/metadata", headers=self.headers)

    # ── Metrics endpoint (Prometheus scrape simulation) ─────────────────

    @task(1)
    @tag("monitoring")
    def prometheus_scrape(self):
        self.client.get("/metrics")


# ── Event hooks for reporting ───────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("  InfectionIQ Load Test Starting")
    print(f"  Target: {environment.host}")
    print(f"  Users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    print("\n" + "=" * 60)
    print("  Load Test Complete")
    print(f"  Total requests:  {total.num_requests}")
    print(f"  Failures:        {total.num_failures} ({total.fail_ratio * 100:.1f}%)")
    print(f"  Avg response:    {total.avg_response_time:.0f}ms")
    print(f"  p95 response:    {total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  p99 response:    {total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  RPS:             {total.total_rps:.1f}")
    print("=" * 60)
