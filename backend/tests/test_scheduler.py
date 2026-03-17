"""Tests for task scheduler core functionality"""

import pytest
import asyncio
from datetime import datetime, timedelta

from app.services.scheduler import TaskScheduler, ScheduledTask


# ---------------------------------------------------------------------------
# TaskScheduler core
# ---------------------------------------------------------------------------

class TestTaskScheduler:
    def test_register_task(self):
        scheduler = TaskScheduler()
        async def dummy(): pass
        scheduler.register("test_task", dummy, 60)
        assert "test_task" in scheduler.tasks
        assert scheduler.tasks["test_task"].interval_seconds == 60
        assert scheduler.tasks["test_task"].enabled is True

    def test_register_multiple_tasks(self):
        scheduler = TaskScheduler()
        async def dummy(): pass
        scheduler.register("task_a", dummy, 300)
        scheduler.register("task_b", dummy, 600)
        assert len(scheduler.tasks) == 2

    def test_get_status_empty(self):
        scheduler = TaskScheduler()
        assert scheduler.get_status() == []

    def test_get_status_with_tasks(self):
        scheduler = TaskScheduler()
        async def dummy(): pass
        scheduler.register("daily_report", dummy, 86400)
        status = scheduler.get_status()
        assert len(status) == 1
        assert status[0]["name"] == "daily_report"
        assert status[0]["interval_seconds"] == 86400
        assert status[0]["last_run"] is None
        assert status[0]["is_running"] is False
        assert status[0]["enabled"] is True

    def test_get_status_shows_last_run(self):
        scheduler = TaskScheduler()
        async def dummy(): pass
        scheduler.register("task", dummy, 60)
        now = datetime.utcnow()
        scheduler.tasks["task"].last_run = now
        status = scheduler.get_status()
        assert status[0]["last_run"] == now.isoformat()


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------

class TestTaskExecution:
    @pytest.mark.asyncio
    async def test_execute_task_calls_function(self):
        called = False
        async def my_func():
            nonlocal called
            called = True

        task = ScheduledTask(name="test", func=my_func, interval_seconds=60)
        scheduler = TaskScheduler()
        await scheduler._execute_task(task)

        assert called is True
        assert task.last_run is not None
        assert task.is_running is False

    @pytest.mark.asyncio
    async def test_execute_task_handles_failure(self):
        async def failing_func():
            raise ValueError("boom")

        task = ScheduledTask(name="failing_task", func=failing_func, interval_seconds=60)
        scheduler = TaskScheduler()
        await scheduler._execute_task(task)

        # Task should not be stuck in running state
        assert task.is_running is False
        # last_run is NOT set on failure
        assert task.last_run is None

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        scheduler = TaskScheduler()
        async def dummy(): pass
        scheduler.register("noop", dummy, 9999)

        await scheduler.start()
        assert scheduler._running is True

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        scheduler = TaskScheduler()
        await scheduler.start()
        task1 = scheduler._loop_task
        await scheduler.start()  # second start is no-op
        assert scheduler._loop_task is task1
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_disabled_task_not_executed(self):
        called = False
        async def my_func():
            nonlocal called
            called = True

        scheduler = TaskScheduler()
        scheduler.register("disabled", my_func, 1)
        scheduler.tasks["disabled"].enabled = False

        # Simulate one loop iteration manually
        now = datetime.utcnow()
        for task in scheduler.tasks.values():
            if not task.enabled or task.is_running:
                continue
            if task.last_run is None or (now - task.last_run).total_seconds() >= task.interval_seconds:
                await scheduler._execute_task(task)

        assert called is False

    @pytest.mark.asyncio
    async def test_already_running_task_not_reentered(self):
        call_count = 0
        async def slow_func():
            nonlocal call_count
            call_count += 1

        scheduler = TaskScheduler()
        scheduler.register("slow", slow_func, 1)
        scheduler.tasks["slow"].is_running = True

        now = datetime.utcnow()
        for task in scheduler.tasks.values():
            if not task.enabled or task.is_running:
                continue
            await scheduler._execute_task(task)

        assert call_count == 0

    @pytest.mark.asyncio
    async def test_task_runs_after_interval(self):
        called = False
        async def my_func():
            nonlocal called
            called = True

        scheduler = TaskScheduler()
        scheduler.register("periodic", my_func, 60)
        # Set last_run to 61 seconds ago → should run
        scheduler.tasks["periodic"].last_run = datetime.utcnow() - timedelta(seconds=61)

        now = datetime.utcnow()
        for task in scheduler.tasks.values():
            if not task.enabled or task.is_running:
                continue
            if task.last_run is None or (now - task.last_run).total_seconds() >= task.interval_seconds:
                await scheduler._execute_task(task)

        assert called is True

    @pytest.mark.asyncio
    async def test_task_skipped_before_interval(self):
        called = False
        async def my_func():
            nonlocal called
            called = True

        scheduler = TaskScheduler()
        scheduler.register("periodic", my_func, 60)
        # Set last_run to 30 seconds ago → should NOT run
        scheduler.tasks["periodic"].last_run = datetime.utcnow() - timedelta(seconds=30)

        now = datetime.utcnow()
        for task in scheduler.tasks.values():
            if not task.enabled or task.is_running:
                continue
            if task.last_run is None or (now - task.last_run).total_seconds() >= task.interval_seconds:
                await scheduler._execute_task(task)

        assert called is False


# ---------------------------------------------------------------------------
# ScheduledTask dataclass
# ---------------------------------------------------------------------------

class TestScheduledTask:
    def test_defaults(self):
        async def dummy(): pass
        task = ScheduledTask(name="t", func=dummy, interval_seconds=10)
        assert task.last_run is None
        assert task.is_running is False
        assert task.enabled is True

    def test_custom_values(self):
        async def dummy(): pass
        now = datetime.utcnow()
        task = ScheduledTask(
            name="custom",
            func=dummy,
            interval_seconds=300,
            last_run=now,
            is_running=True,
            enabled=False,
        )
        assert task.name == "custom"
        assert task.interval_seconds == 300
        assert task.last_run == now
        assert task.is_running is True
        assert task.enabled is False


# ---------------------------------------------------------------------------
# Registered default tasks
# ---------------------------------------------------------------------------

def test_default_scheduler_has_tasks():
    """The module-level scheduler instance should have default tasks registered."""
    from app.services.scheduler import scheduler
    assert "daily_report" in scheduler.tasks
    assert "audit_cleanup" in scheduler.tasks
    assert "dispenser_check" in scheduler.tasks

def test_daily_report_interval():
    from app.services.scheduler import scheduler
    assert scheduler.tasks["daily_report"].interval_seconds == 86400

def test_dispenser_check_interval():
    from app.services.scheduler import scheduler
    assert scheduler.tasks["dispenser_check"].interval_seconds == 300
