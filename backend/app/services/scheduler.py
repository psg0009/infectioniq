"""
Background Task Scheduler
Handles periodic report generation and maintenance tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    name: str
    func: Callable
    interval_seconds: int
    last_run: Optional[datetime] = None
    is_running: bool = False
    enabled: bool = True


class TaskScheduler:
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    def register(self, name: str, func: Callable, interval_seconds: int):
        self.tasks[name] = ScheduledTask(
            name=name, func=func, interval_seconds=interval_seconds
        )
        logger.info(f"Registered scheduled task: {name} (every {interval_seconds}s)")

    async def start(self):
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("Task scheduler started")

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Task scheduler stopped")

    async def _run_loop(self):
        while self._running:
            now = datetime.utcnow()
            for task in self.tasks.values():
                if not task.enabled or task.is_running:
                    continue
                if task.last_run is None or (now - task.last_run).total_seconds() >= task.interval_seconds:
                    asyncio.create_task(self._execute_task(task))
            await asyncio.sleep(10)

    async def _execute_task(self, task: ScheduledTask):
        import time as _time
        from app.core.metrics import scheduled_task_duration_seconds, scheduled_task_failures_total

        task.is_running = True
        start = _time.perf_counter()
        try:
            logger.info(f"Running scheduled task: {task.name}")
            await task.func()
            task.last_run = datetime.utcnow()
            logger.info(f"Completed scheduled task: {task.name}")
        except Exception as e:
            logger.error(f"Scheduled task {task.name} failed: {e}")
            scheduled_task_failures_total.labels(task_name=task.name).inc()
        finally:
            duration = _time.perf_counter() - start
            scheduled_task_duration_seconds.labels(task_name=task.name).observe(duration)
            task.is_running = False

    def get_status(self) -> List[dict]:
        return [
            {
                "name": t.name,
                "interval_seconds": t.interval_seconds,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "is_running": t.is_running,
                "enabled": t.enabled,
            }
            for t in self.tasks.values()
        ]


scheduler = TaskScheduler()


async def generate_daily_report():
    """Generate daily compliance summary report"""
    from app.core.database import async_session_maker
    from app.models.models import EntryExitEvent, Alert, SurgicalCase
    from sqlalchemy import select, func

    async with async_session_maker() as db:
        yesterday = datetime.utcnow() - timedelta(days=1)

        total_entries = (await db.execute(
            select(func.count(EntryExitEvent.id)).where(
                EntryExitEvent.timestamp >= yesterday,
                EntryExitEvent.event_type == "ENTRY"
            )
        )).scalar() or 0

        compliant_entries = (await db.execute(
            select(func.count(EntryExitEvent.id)).where(
                EntryExitEvent.timestamp >= yesterday,
                EntryExitEvent.event_type == "ENTRY",
                EntryExitEvent.compliant == True
            )
        )).scalar() or 0

        total_alerts = (await db.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= yesterday)
        )).scalar() or 0

        active_cases = (await db.execute(
            select(func.count(SurgicalCase.id)).where(
                SurgicalCase.status == "IN_PROGRESS"
            )
        )).scalar() or 0

        compliance_rate = (compliant_entries / total_entries * 100) if total_entries > 0 else 0

        report = {
            "date": yesterday.date().isoformat(),
            "total_entries": total_entries,
            "compliant_entries": compliant_entries,
            "compliance_rate": round(compliance_rate, 1),
            "total_alerts": total_alerts,
            "active_cases": active_cases,
        }
        logger.info(f"Daily report generated: {report}")

        from app.core.redis import RedisPubSub
        await RedisPubSub.publish_dashboard_update(report)


async def cleanup_old_audit_logs():
    """Clean up audit logs older than retention period"""
    from app.core.database import async_session_maker
    from app.models.audit_log import AuditLog
    from sqlalchemy import delete
    from app.config import settings

    async with async_session_maker() as db:
        cutoff = datetime.utcnow() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        result = await db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await db.commit()
        deleted = result.rowcount
        logger.info(f"Cleaned up {deleted} audit logs older than {settings.AUDIT_RETENTION_DAYS} days")


async def check_dispenser_levels():
    """Check dispenser levels and send alerts for low levels"""
    from app.core.database import async_session_maker
    from app.models.models import DispenserStatus
    from sqlalchemy import select
    from app.services.alert_routing import alert_router

    async with async_session_maker() as db:
        result = await db.execute(select(DispenserStatus))
        statuses = result.scalars().all()

        for status in statuses:
            if status.level_percent is not None and status.level_percent < 20:
                severity = "HIGH" if status.level_percent < 10 else "MEDIUM"
                await alert_router.route_alert({
                    "type": "DISPENSER_LOW",
                    "severity": severity,
                    "message": f"Dispenser {status.dispenser_id} at {status.level_percent}%",
                    "dispenser_id": str(status.dispenser_id),
                    "level_percent": status.level_percent,
                })
                logger.warning(f"Dispenser {status.dispenser_id} low: {status.level_percent}%")


async def check_camera_health():
    """Detect stale cameras and fire CAMERA_OFFLINE alerts."""
    from app.api.v1.cameras import _camera_registry
    from app.services.alert_routing import alert_router
    from app.core.metrics import (
        cameras_registered_total, cameras_online, cameras_offline,
        camera_heartbeat_age_seconds,
    )

    from app.config import settings
    now = datetime.utcnow()
    stale_threshold = timedelta(seconds=settings.CAMERA_STALE_THRESHOLD_SECONDS)
    online_count = 0
    offline_count = 0

    for cam in _camera_registry.values():
        age = (now - cam.last_frame_at).total_seconds() if cam.last_frame_at else 9999
        camera_heartbeat_age_seconds.labels(
            camera_id=cam.camera_id, or_number=cam.or_number
        ).set(age)

        if age > stale_threshold.total_seconds():
            if cam.status != "OFFLINE":
                cam.status = "OFFLINE"
                await alert_router.route_alert({
                    "type": "CAMERA_OFFLINE",
                    "severity": "HIGH",
                    "message": f"Camera {cam.camera_id} in {cam.or_number} is offline (no heartbeat for {int(age)}s)",
                    "camera_id": cam.camera_id,
                    "or_number": cam.or_number,
                })
                logger.warning(f"Camera {cam.camera_id} marked OFFLINE (age={int(age)}s)")
            offline_count += 1
        else:
            if cam.status == "OFFLINE":
                cam.status = "ONLINE"
                logger.info(f"Camera {cam.camera_id} recovered to ONLINE")
            online_count += 1

    cameras_registered_total.set(len(_camera_registry))
    cameras_online.set(online_count)
    cameras_offline.set(offline_count)


# Register default tasks
scheduler.register("daily_report", generate_daily_report, 86400)
scheduler.register("audit_cleanup", cleanup_old_audit_logs, 86400)
scheduler.register("dispenser_check", check_dispenser_levels, 300)
scheduler.register("camera_health_check", check_camera_health, 60)
