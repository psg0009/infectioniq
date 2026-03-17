"""
Demo Simulation Script
======================
Simulates 8 people entering the OR during an active surgery:
  - 5 sanitize their hands before entering (COMPLIANT)
  - 3 skip hand hygiene (NON-COMPLIANT)

This calls the same backend API endpoints that the CV module would call
after processing a video feed, so all events, alerts, and analytics are real.

Usage: python -m scripts.simulate_demo
"""

import httpx
import time
import uuid
from datetime import datetime, timedelta

API_URL = "http://localhost:8000"
SERVICE_HEADERS = {"X-Service-Key": "dev-internal-key"}


def get_active_case_id() -> str:
    """Auto-fetch an active (IN_PROGRESS) case from the backend."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/cases/active", headers=SERVICE_HEADERS, timeout=5.0)
        if resp.status_code == 200:
            cases = resp.json()
            if cases and len(cases) > 0:
                case_id = cases[0]["id"]
                print(f"  Auto-detected active case: {case_id[:8]}...")
                return case_id
    except Exception as e:
        print(f"  Could not fetch active cases: {e}")

    # Fallback: try listing all cases and pick first IN_PROGRESS
    try:
        resp = httpx.get(f"{API_URL}/api/v1/cases/", headers=SERVICE_HEADERS, timeout=5.0)
        if resp.status_code == 200:
            cases = resp.json()
            for c in cases:
                if c.get("status") == "IN_PROGRESS":
                    case_id = c["id"]
                    print(f"  Found IN_PROGRESS case: {case_id[:8]}...")
                    return case_id
            # If no active case, use the first one
            if cases:
                case_id = cases[0]["id"]
                print(f"  No active case found, using first case: {case_id[:8]}...")
                return case_id
    except Exception as e:
        print(f"  Could not fetch cases: {e}")

    print("  ERROR: No cases found. Run 'python -m scripts.demo_seed' first.")
    raise SystemExit(1)


def get_staff_ids() -> list:
    """Auto-fetch staff IDs from the backend."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/staff/", headers=SERVICE_HEADERS, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            staff_list = data.get("staff", data) if isinstance(data, dict) else data
            if staff_list and len(staff_list) >= 8:
                result = []
                for i, s in enumerate(staff_list[:8]):
                    compliant = i < 5  # First 5 compliant, last 3 non-compliant
                    result.append((s["id"], s["name"], compliant))
                return result
    except Exception:
        pass

    # Fallback to hardcoded (from demo_seed.py)
    print("  Could not fetch staff from API, using defaults")
    return [
        ("staff-1", "Dr. Sarah Chen", True),
        ("staff-2", "Dr. James Patel", True),
        ("staff-3", "Maria Gonzalez, RN", True),
        ("staff-4", "David Kim, RN", True),
        ("staff-5", "Lisa Thompson, CST", True),
        ("staff-6", "Robert Jackson", False),
        ("staff-7", "Dr. Amy Liu", False),
        ("staff-8", "Carlos Rivera, RN", False),
    ]


def run_simulation():
    client = httpx.Client(timeout=10.0, headers=SERVICE_HEADERS)
    now = datetime.utcnow()
    compliant_count = 0
    violation_count = 0

    CASE_ID = get_active_case_id()
    STAFF = get_staff_ids()

    print(f"\nSimulating {len(STAFF)} staff members entering OR")
    print(f"Case ID: {CASE_ID}")
    print(f"{'='*60}\n")

    for i, (staff_id, name, sanitizes) in enumerate(STAFF):
        person_track_id = i + 1
        entry_time = now - timedelta(minutes=30 - i * 3)  # Stagger entries

        if sanitizes:
            # Step 1: Person approaches sanitizer zone (touch SANITIZER)
            sanitize_time = entry_time - timedelta(seconds=15)
            print(f"  [{person_track_id}] {name} approaches sanitizer...")
            resp = client.post(f"{API_URL}/api/v1/compliance/touch", json={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "timestamp": sanitize_time.isoformat(),
                "zone": "SANITIZER",
                "hand": "RIGHT",
                "confidence": 0.92,
            })
            if resp.status_code == 200:
                print(f"       Touch SANITIZER zone recorded")
            else:
                print(f"       Touch failed: {resp.status_code} {resp.text[:100]}")

            # Step 2: Record sanitization
            resp = client.post(f"{API_URL}/api/v1/compliance/sanitize", params={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "volume_ml": 1.5,
                "duration_sec": 4.2,
                "timestamp": sanitize_time.isoformat(),
            })
            if resp.status_code == 200:
                print(f"       Sanitization recorded (1.5ml, 4.2s)")
            else:
                print(f"       Sanitize failed: {resp.status_code} {resp.text[:100]}")

            # Step 3: Record compliant entry
            resp = client.post(f"{API_URL}/api/v1/compliance/entry", json={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "timestamp": entry_time.isoformat(),
                "compliant": True,
                "sanitize_method": "DISPENSER",
                "sanitize_duration_sec": 4.2,
                "sanitize_volume_ml": 1.5,
                "confidence": 0.95,
            })
            if resp.status_code == 200:
                compliant_count += 1
                print(f"  [OK] {name} entered OR (COMPLIANT)\n")
            else:
                print(f"  [!]  Entry failed: {resp.status_code} {resp.text[:100]}\n")
        else:
            # Non-compliant: skip sanitizer, enter directly
            # Step 1: Touch DOOR zone (approaching without sanitizing)
            door_time = entry_time - timedelta(seconds=5)
            resp = client.post(f"{API_URL}/api/v1/compliance/touch", json={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "timestamp": door_time.isoformat(),
                "zone": "DOOR",
                "hand": "LEFT",
                "confidence": 0.88,
            })
            if resp.status_code == 200:
                print(f"  [{person_track_id}] {name} passes through door...")
            else:
                print(f"       Touch DOOR failed: {resp.status_code} {resp.text[:100]}")

            # Step 2: Record non-compliant entry
            resp = client.post(f"{API_URL}/api/v1/compliance/entry", json={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "timestamp": entry_time.isoformat(),
                "compliant": False,
                "confidence": 0.91,
            })
            if resp.status_code == 200:
                violation_count += 1
                print(f"  [!!] {name} entered OR (NON-COMPLIANT - no hand hygiene)\n")
            else:
                print(f"  [!]  Entry failed: {resp.status_code} {resp.text[:100]}\n")

            # Step 3: Touch STERILE zone without sanitizing (generates alert)
            touch_time = entry_time + timedelta(seconds=10)
            resp = client.post(f"{API_URL}/api/v1/compliance/touch", json={
                "case_id": CASE_ID,
                "staff_id": staff_id,
                "person_track_id": person_track_id,
                "timestamp": touch_time.isoformat(),
                "zone": "STERILE",
                "hand": "RIGHT",
                "confidence": 0.87,
            })
            if resp.status_code == 200:
                result = resp.json()
                alert = result.get("alert_generated")
                if alert:
                    print(f"       ALERT: {alert.get('message', 'contamination detected')}")
                print(f"       Touched sterile zone without sanitizing\n")
            else:
                print(f"       Touch STERILE failed: {resp.status_code} {resp.text[:100]}\n")

        time.sleep(0.2)  # Small delay between requests

    # Record exits for everyone
    print(f"{'='*60}")
    print(f"Recording exits for all staff...\n")
    for i, (staff_id, name, _) in enumerate(STAFF):
        exit_time = now + timedelta(minutes=i * 2)
        resp = client.post(f"{API_URL}/api/v1/compliance/exit", params={
            "case_id": CASE_ID,
            "staff_id": staff_id,
            "person_track_id": i + 1,
            "timestamp": exit_time.isoformat(),
        })
        status = "OK" if resp.status_code == 200 else f"FAIL({resp.status_code})"
        print(f"  [{status}] {name} exited OR")

    # Print summary
    total = compliant_count + violation_count
    compliance_pct = (compliant_count / total * 100) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"SIMULATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total entries:     {total}")
    print(f"  Compliant:         {compliant_count} ({compliance_pct:.0f}%)")
    print(f"  Non-compliant:     {violation_count}")
    print(f"\n  Dashboard: http://localhost:3000")
    print(f"  Analytics: http://localhost:3000/analytics")

    # Verify via API
    print(f"\nVerifying via API...")
    dashboard = client.get(f"{API_URL}/api/v1/analytics/dashboard").json()
    print(f"  Active cases:      {dashboard.get('active_cases')}")
    print(f"  Compliance rate:   {dashboard.get('overall_compliance_rate', 0) * 100:.1f}%")
    print(f"  Active alerts:     {dashboard.get('active_alerts')}")
    print(f"  Today entries:     {dashboard.get('today_entries')}")
    print(f"  Today violations:  {dashboard.get('today_violations')}")

    client.close()


if __name__ == "__main__":
    run_simulation()
