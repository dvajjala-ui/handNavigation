"""Single local worker. Durable queue; no hidden retries, remote sites or models."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from uuid import uuid4

from .contracts import ContractError, approve
from .ownership import RuntimeOwnership
from .runner import Runner
from .store import Store


class Controller:
    def __init__(self, root: Path, origin: str, *, clock=None, execute=None, autostart=True):
        self.root, self.origin = Path(root).resolve(), origin
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ownership = RuntimeOwnership(self.root)
        try:
            self.store = Store(self.root)
            self.store.recover_interrupted(self.clock())
        except BaseException:
            self.ownership.close()
            raise
        self.execute = execute or self._execute
        self.shutdown_event = threading.Event()
        self.wake = threading.Event()
        self.cancel_event = threading.Event()
        self.control_lock = threading.RLock()
        self.execution_lock = threading.Lock()
        self.error = None
        self.last_tick_at = None
        self.worker = None
        if autostart:
            self.worker = threading.Thread(target=self._loop, name="handnavigate-worker", daemon=True)
            self.worker.start()

    def _execute(self, attempt, cancel_event):
        request = attempt["request"]
        return Runner(self.root, cancel_event=cancel_event).run(
            attempt["recipe"], approve(attempt["recipe"], "reviewed local queue snapshot"),
            origin=self.origin, topic=request["topic"], limit=request["limit"],
            case=request["case"], job_key=request["job_key"],
            pause_after=request.get("pause_after"), fixture_transport=request["fixture_transport"])

    def tick(self):
        """Share one local browser execution slot with supervised teaching."""
        if not self.execution_lock.acquire(blocking=False):
            return None
        try:
            return self._tick_owned()
        finally:
            self.execution_lock.release()

    def _tick_owned(self):
        """One due-check/claim/execute cycle. Tests inject clocks, not sleep for days."""
        with self.control_lock:
            if self.shutdown_event.is_set():
                return None
            at = self.clock()
            self.store.enqueue_due(at)
            self.last_tick_at = at.isoformat()
            attempt = self.store.claim(at)
            if not attempt:
                return None
            self.cancel_event = threading.Event()
        try:
            report = self.execute(attempt, self.cancel_event)
        except Exception as exc:
            request = attempt["request"]
            report = {"run_id": str(uuid4()), "job_key": request["job_key"],
                      "status": "HALTED", "parameters": {"topic": request["topic"], "limit": request["limit"]},
                      "scenario": request["case"], "verified_count": 0, "verified_files": [],
                      "model_calls": 0, "events": [], "skipped": [],
                      "error": {"code": "WORKER_ERROR", "message": str(exc)[:250]}}
        # Persistence failures deliberately leave RUNNING unresolved. Do not retry.
        self.store.finish(attempt["id"], report, self.clock())
        return report

    def _loop(self):
        while not self.shutdown_event.is_set():
            try:
                self.tick()
                self.error = None
            except Exception as exc:
                self.error = f"Scheduler stopped: {type(exc).__name__}: {str(exc)[:250]}"
                # A failed bookkeeping operation may follow a performed effect.
                # Hold ownership and wait for explicit shutdown/reconciliation.
                break
            self.wake.wait(.5)
            self.wake.clear()

    def notify(self):
        self.wake.set()

    def stop_active(self):
        with self.control_lock:
            self.cancel_event.set()
            self.store.cancel_queued(self.clock())

    def close(self):
        with self.control_lock:
            self.shutdown_event.set()
            self.cancel_event.set()
            # QUEUED tasks were never started; they may safely remain durable.
            self.wake.set()
        if self.worker:
            self.worker.join(timeout=60)
            if self.worker.is_alive():
                # Do not release ownership while a worker could still be acting.
                raise RuntimeError("Worker has not stopped; runtime ownership is retained")
        self.ownership.close()
