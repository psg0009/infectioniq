"""
Video Upload & Processing API
Upload OR footage and run the CV pipeline on it for demos and analysis.
"""

import os
import uuid
import asyncio
import logging
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Upload directory ────────────────────────────────────────────────
import shutil
import tempfile


def _pick_upload_dir() -> str:
    """Pick an upload directory on a drive that has free space."""
    configured = os.environ.get("VIDEO_UPLOAD_DIR")
    if configured:
        return configured
    # Build candidate list based on platform
    candidates = []
    if sys.platform == "win32":
        candidates.append("D:/infectioniq/videos")
    candidates.append(os.path.join(tempfile.gettempdir(), "infectioniq", "videos"))
    # Prefer a drive with space; fall back to system temp
    for candidate in candidates:
        drive = os.path.splitdrive(candidate)[0] or candidate
        try:
            usage = shutil.disk_usage(drive + "/" if not drive.endswith("/") else drive)
            if usage.free > 100 * 1024 * 1024:  # at least 100 MB free
                return candidate
        except OSError:
            continue
    return os.path.join(tempfile.gettempdir(), "infectioniq", "videos")


UPLOAD_DIR = Path(_pick_upload_dir())
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Maximum file size: 500 MB
MAX_FILE_SIZE = 500 * 1024 * 1024

# Allowed video extensions
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# ── In-memory job tracker ───────────────────────────────────────────
_jobs: Dict[str, dict] = {}


class VideoJobStatus(BaseModel):
    job_id: str
    status: str  # QUEUED, PROCESSING, COMPLETED, FAILED
    filename: str
    case_id: Optional[str] = None
    or_number: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    events_published: int = 0


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    or_number: str = Form("OR-1"),
    sample_frames: bool = Form(False),
    demo_mode: bool = Form(False),
):
    """Upload a video file and run the CV pipeline on it.

    The pipeline runs as a background process. Events are published to the
    backend in real-time (same as a live camera), so the dashboard updates
    as the video plays.

    Set demo_mode=True to simulate events (5 compliant, 3 non-compliant)
    timed to the video instead of running YOLO detection.

    Returns a job_id that can be polled for status.
    """
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file with size check
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents) / 1024 / 1024:.0f} MB). Max: {MAX_FILE_SIZE / 1024 / 1024:.0f} MB"
        )

    # Save to disk
    job_id = str(uuid.uuid4())
    safe_name = f"{job_id}{ext}"
    video_path = UPLOAD_DIR / safe_name
    try:
        video_path.write_bytes(contents)
    except OSError as e:
        raise HTTPException(
            status_code=507,
            detail=f"Insufficient storage to save video: {e}"
        )

    logger.info(f"Video uploaded: {file.filename} → {video_path} ({len(contents) / 1024 / 1024:.1f} MB)")

    # Create job record
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "QUEUED",
        "filename": file.filename,
        "video_path": str(video_path),
        "case_id": case_id,
        "or_number": or_number,
        "sample_frames": sample_frames,
        "demo_mode": demo_mode,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "events_published": 0,
        "pid": None,
    }

    # Launch processing in background
    if demo_mode:
        background_tasks.add_task(_run_demo_simulation, job_id)
    else:
        background_tasks.add_task(_run_cv_pipeline, job_id)

    return {
        "job_id": job_id,
        "status": "QUEUED",
        "message": f"Video '{file.filename}' uploaded. CV pipeline will process it in the background.",
        "poll_url": f"/api/v1/video/jobs/{job_id}",
    }


@router.get("/jobs")
async def list_jobs():
    """List all video processing jobs."""
    jobs = sorted(_jobs.values(), key=lambda j: j.get("started_at") or "", reverse=True)
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get status of a video processing job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job or delete a completed one."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Kill the process if still running
    pid = job.get("pid")
    if pid and job["status"] == "PROCESSING":
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Killed CV pipeline process {pid} for job {job_id}")
        except (OSError, ProcessLookupError):
            pass
        job["status"] = "FAILED"
        job["error"] = "Cancelled by user"

    # Clean up video file
    video_path = job.get("video_path")
    if video_path and os.path.exists(video_path):
        os.remove(video_path)

    del _jobs[job_id]
    return {"status": "deleted", "job_id": job_id}


async def _run_cv_pipeline(job_id: str):
    """Run the CV pipeline as a subprocess on the uploaded video."""
    job = _jobs.get(job_id)
    if not job:
        return

    job["status"] = "PROCESSING"
    job["started_at"] = datetime.utcnow().isoformat()

    video_path = job["video_path"]
    case_id = job.get("case_id")
    or_number = job.get("or_number", "OR-1")
    sample_frames = job.get("sample_frames", False)

    # Auto-pick an active case if none provided (required for event publishing)
    # Query DB directly instead of HTTP (avoids deadlock calling our own server)
    if not case_id:
        try:
            import sqlite3
            db_path = Path(__file__).resolve().parents[3] / "infectioniq.db"
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT id FROM surgical_cases WHERE status='IN_PROGRESS' ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                case_id = row[0]
                job["case_id"] = case_id
                logger.info(f"Auto-selected active case: {case_id}")
            else:
                logger.warning("No active case found for auto-selection")
        except Exception as e:
            logger.warning(f"Could not auto-select case: {e}")

    # Build the command to run the CV module
    # The CV module is at cv_module/src/main.py relative to the project root
    project_root = Path(__file__).resolve().parents[4]  # backend/app/api/v1/video.py → project root
    cv_main = project_root / "cv_module" / "src" / "main.py"

    if not cv_main.exists():
        # Fallback: try relative to working directory
        cv_main = Path("cv_module") / "src" / "main.py"

    cmd = [
        sys.executable, "-m", "src.main",
        "--video", str(Path(video_path).resolve()),
        "--no-loop",
        "--headless",
        "--or", or_number,
    ]

    if case_id:
        cmd.extend(["--case-id", case_id])

    if sample_frames:
        cmd.extend(["--sample-frames"])

    # Set working directory to cv_module
    cwd = str(project_root / "cv_module")

    # Set DISPLAY to empty to run headless (no cv2.imshow window)
    env = os.environ.copy()
    env["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"  # Prefer FFMPEG on Windows
    # Run headless: we set a flag the CV module can check
    env["INFECTIONIQ_HEADLESS"] = "1"

    logger.info(f"Starting CV pipeline: {' '.join(cmd)} (cwd={cwd})")

    def _run_subprocess():
        """Run CV subprocess in a thread (avoids Windows asyncio subprocess issues)."""
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        job["pid"] = proc.pid
        stdout, stderr = proc.communicate()
        return proc.returncode, stdout, stderr

    try:
        returncode, stdout, stderr = await asyncio.to_thread(_run_subprocess)

        if returncode == 0:
            job["status"] = "COMPLETED"
            logger.info(f"CV pipeline completed for job {job_id}")
        else:
            job["status"] = "FAILED"
            error_msg = stderr.decode(errors="replace")[-500:] if stderr else "Unknown error"
            job["error"] = error_msg
            logger.error(f"CV pipeline failed for job {job_id} (exit {returncode}): {error_msg}")

    except Exception as e:
        job["status"] = "FAILED"
        job["error"] = f"{type(e).__name__}: {e}"
        logger.error(f"Failed to run CV pipeline for job {job_id}: {traceback.format_exc()}")

    finally:
        job["completed_at"] = datetime.utcnow().isoformat()
        job["pid"] = None


async def _fetch_demo_staff(client, api: str, num_compliant: int = 5, num_non_compliant: int = 3):
    """Fetch real staff from the database and assign compliance roles."""
    staff_list = []
    try:
        resp = await client.get(f"{api}/api/v1/staff/")
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("staff", data) if isinstance(data, dict) else data
            if isinstance(raw, list) and raw:
                for s in raw:
                    staff_list.append({"id": s.get("id"), "name": s.get("name", "Unknown")})
    except Exception as e:
        logger.warning(f"Could not fetch staff: {e}")

    total_needed = num_compliant + num_non_compliant

    # Pad with generated entries if not enough staff in DB
    while len(staff_list) < total_needed:
        idx = len(staff_list) + 1
        staff_list.append({"id": None, "name": f"Staff Member #{idx}"})

    # Assign compliance: first N compliant, rest non-compliant
    result = []
    for i in range(total_needed):
        entry = staff_list[i % len(staff_list)].copy()
        entry["compliant"] = i < num_compliant
        result.append(entry)
    return result


async def _run_demo_simulation(job_id: str):
    """Simulate staff entering the OR with real-time delays.

    Fetches real staff from the database and uses the same compliance API
    endpoints the CV module uses, so dashboard, analytics, and alerts all
    update in real-time as the 'video processes'.
    """
    import httpx

    job = _jobs.get(job_id)
    if not job:
        return

    job["status"] = "PROCESSING"
    job["started_at"] = datetime.utcnow().isoformat()

    case_id = job.get("case_id")
    or_number = job.get("or_number", "OR-1")
    api = "http://localhost:8000"

    # Internal service key for authenticating with our own API
    service_headers = {"X-Service-Key": "dev-internal-key"}

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=service_headers) as client:
            # Auto-pick active case if needed
            if not case_id:
                resp = await client.get(f"{api}/api/v1/cases/active")
                if resp.status_code == 200:
                    cases = resp.json()
                    if cases:
                        case_id = cases[0].get("id")
                        job["case_id"] = case_id
                        logger.info(f"Demo: auto-selected case {case_id}")

            if not case_id:
                job["status"] = "FAILED"
                job["error"] = "No active case found. Create a case first."
                return

            # Fetch real staff from database
            demo_staff = await _fetch_demo_staff(client, api)
            logger.info(f"Demo: using {len(demo_staff)} staff members from database")

            now = datetime.utcnow()
            events_published = 0

            for i, person in enumerate(demo_staff):
                person_track_id = i + 1
                staff_id = person.get("id")
                entry_time = now + timedelta(seconds=i * 4)

                # Delay between each person (simulates real-time processing)
                await asyncio.sleep(3)

                # Build common fields
                staff_fields = {}
                if staff_id:
                    staff_fields["staff_id"] = staff_id

                if person["compliant"]:
                    # Step 1: Touch sanitizer zone
                    sanitize_time = entry_time - timedelta(seconds=15)
                    resp = await client.post(f"{api}/api/v1/compliance/touch", json={
                        "case_id": case_id,
                        **staff_fields,
                        "person_track_id": person_track_id,
                        "timestamp": sanitize_time.isoformat(),
                        "zone": "SANITIZER",
                        "hand": "RIGHT",
                        "confidence": 0.92,
                    })
                    if resp.status_code == 200:
                        events_published += 1

                    # Step 2: Record sanitization
                    resp = await client.post(f"{api}/api/v1/compliance/sanitize", params={
                        "case_id": case_id,
                        **({"staff_id": staff_id} if staff_id else {}),
                        "person_track_id": person_track_id,
                        "volume_ml": 1.5,
                        "duration_sec": 4.2,
                        "timestamp": sanitize_time.isoformat(),
                    })
                    if resp.status_code == 200:
                        events_published += 1

                    # Step 3: Compliant entry
                    resp = await client.post(f"{api}/api/v1/compliance/entry", json={
                        "case_id": case_id,
                        **staff_fields,
                        "person_track_id": person_track_id,
                        "timestamp": entry_time.isoformat(),
                        "compliant": True,
                        "sanitize_method": "DISPENSER",
                        "sanitize_duration_sec": 4.2,
                        "sanitize_volume_ml": 1.5,
                        "confidence": 0.95,
                    })
                    if resp.status_code == 200:
                        events_published += 1
                        logger.info(f"Demo: {person['name']} entered (COMPLIANT)")
                else:
                    # Step 1: Touch door zone (bypassing sanitizer)
                    door_time = entry_time - timedelta(seconds=5)
                    resp = await client.post(f"{api}/api/v1/compliance/touch", json={
                        "case_id": case_id,
                        **staff_fields,
                        "person_track_id": person_track_id,
                        "timestamp": door_time.isoformat(),
                        "zone": "DOOR",
                        "hand": "LEFT",
                        "confidence": 0.88,
                    })
                    if resp.status_code == 200:
                        events_published += 1

                    # Step 2: Non-compliant entry
                    resp = await client.post(f"{api}/api/v1/compliance/entry", json={
                        "case_id": case_id,
                        **staff_fields,
                        "person_track_id": person_track_id,
                        "timestamp": entry_time.isoformat(),
                        "compliant": False,
                        "confidence": 0.91,
                    })
                    if resp.status_code == 200:
                        events_published += 1
                        logger.info(f"Demo: {person['name']} entered (NON-COMPLIANT)")

                    # Step 3: Touch sterile zone without sanitizing (generates alert)
                    touch_time = entry_time + timedelta(seconds=10)
                    resp = await client.post(f"{api}/api/v1/compliance/touch", json={
                        "case_id": case_id,
                        **staff_fields,
                        "person_track_id": person_track_id,
                        "timestamp": touch_time.isoformat(),
                        "zone": "STERILE",
                        "hand": "RIGHT",
                        "confidence": 0.87,
                    })
                    if resp.status_code == 200:
                        events_published += 1

                job["events_published"] = events_published

            # Record exits for everyone
            await asyncio.sleep(2)
            for i, person in enumerate(demo_staff):
                exit_time = now + timedelta(minutes=5 + i)
                staff_id = person.get("id")
                params = {
                    "case_id": case_id,
                    "person_track_id": i + 1,
                    "timestamp": exit_time.isoformat(),
                }
                if staff_id:
                    params["staff_id"] = staff_id
                resp = await client.post(f"{api}/api/v1/compliance/exit", params=params)
                if resp.status_code == 200:
                    events_published += 1

            job["events_published"] = events_published
            job["status"] = "COMPLETED"
            logger.info(f"Demo simulation completed: {events_published} events published")

    except Exception as e:
        job["status"] = "FAILED"
        job["error"] = f"{type(e).__name__}: {e}"
        logger.error(f"Demo simulation failed for job {job_id}: {traceback.format_exc()}")

    finally:
        job["completed_at"] = datetime.utcnow().isoformat()
