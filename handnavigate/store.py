"""Transactional local run queue, immutable recipes, schedules and audit records.

The controller must own RuntimeOwnership before recovering abandoned attempts.
SQLite transactions prevent duplicate claims; they do NOT provide exactly-once
external actions. An interrupted RUNNING attempt is never automatically retried.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .contracts import ContractError, approve, digest, load_default, validate_recipe
from .scheduling import iso, parse, next_due, latest_due, validate_schedule, preview


def dumps(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "studio.db"
        with self.connection() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, recipe TEXT NOT NULL, sha TEXT NOT NULL,
                source TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, recipe TEXT NOT NULL,
                request TEXT NOT NULL, enabled INTEGER NOT NULL,
                next_due_at TEXT NOT NULL, created_at TEXT NOT NULL, pause_reason TEXT);
              CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, schedule_id TEXT, due_at TEXT, source TEXT NOT NULL,
                state TEXT NOT NULL, recipe TEXT NOT NULL, request TEXT NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, report TEXT,
                UNIQUE(schedule_id, due_at));
              CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt
                ON attempts((1)) WHERE state='RUNNING';
              CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                event TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL);
              PRAGMA user_version=2;
            ''')
            db.execute("INSERT OR IGNORE INTO config VALUES ('active_recipe',?)", (dumps(load_default()),))

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def _audit(self, db, at, event, subject, detail):
        db.execute("INSERT INTO audit(at,event,subject,detail) VALUES (?,?,?,?)",
                   (iso(at), event, subject, dumps(detail)))

    def recipe(self):
        with self.connection() as db:
            return json.loads(db.execute("SELECT value FROM config WHERE key='active_recipe'").fetchone()[0])

    def create_draft(self, recipe, source, at):
        validate_recipe(recipe)
        recipe = deepcopy(recipe)
        key = str(uuid4())
        with self.connection(write=True) as db:
            db.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?)",
                       (key, dumps(recipe), digest(recipe), source, "DRAFT", iso(at)))
            self._audit(db, at, "DRAFT_CREATED", key, {"source": source, "sha256": digest(recipe)})
        return {"id": key, "recipe": recipe, "sha256": digest(recipe), "source": source, "state": "DRAFT"}

    def activate_draft(self, key, reviewed_sha, at):
        with self.connection(write=True) as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (key,)).fetchone()
            if not row or row["sha"] != reviewed_sha or row["state"] != "DRAFT":
                raise ContractError("Review the exact pending draft before activating it")
            recipe = json.loads(row["recipe"])
            current = json.loads(db.execute("SELECT value FROM config WHERE key='active_recipe'").fetchone()[0])
            if recipe["revision"] != current["revision"] + 1:
                raise ContractError("Draft is stale; create a new draft from the active revision")
            validate_recipe(recipe)
            if digest(recipe) != row["sha"]:
                raise ContractError("Draft content changed; approval refused")
            db.execute("UPDATE config SET value=? WHERE key='active_recipe'", (row["recipe"],))
            db.execute("UPDATE drafts SET state='APPROVED' WHERE id=?", (key,))
            db.execute("UPDATE schedules SET enabled=0,pause_reason='RECIPE_CHANGED' WHERE enabled=1")
            db.execute("UPDATE attempts SET state='CANCELLED',finished_at=? WHERE state='QUEUED'", (iso(at),))
            self._audit(db, at, "RECIPE_APPROVED", key,
                        {"receipt": approve(recipe, "local studio operator"), "schedules_paused": True})
        return recipe

    def drafts(self):
        with self.connection() as db:
            return [{"id": row["id"], "recipe": json.loads(row["recipe"]), "sha256": row["sha"],
                     "source": row["source"], "state": row["state"], "created_at": row["created_at"]}
                    for row in db.execute("SELECT * FROM drafts ORDER BY rowid DESC LIMIT 20")]

    def _unresolved(self, db):
        return db.execute("SELECT 1 FROM attempts WHERE state='NEEDS_REVIEW' LIMIT 1").fetchone() is not None

    def busy(self):
        with self.connection() as db:
            return bool(db.execute("SELECT 1 FROM attempts WHERE state IN ('QUEUED','RUNNING') LIMIT 1").fetchone())

    def submit_manual(self, recipe, request, at):
        validate_recipe(recipe)
        key = str(uuid4())
        request = {**deepcopy(request), "job_key": request.get("job_key") or str(uuid4())}
        with self.connection(write=True) as db:
            current = json.loads(db.execute("SELECT value FROM config WHERE key='active_recipe'").fetchone()[0])
            if digest(recipe) != digest(current):
                raise ContractError("Active recipe changed; review again")
            if self._unresolved(db):
                raise ContractError("An interrupted attempt needs review before another run")
            if db.execute("SELECT 1 FROM attempts WHERE state IN ('QUEUED','RUNNING') LIMIT 1").fetchone():
                raise ContractError("A run is already queued or in progress")
            db.execute("INSERT INTO attempts(id,source,state,recipe,request,created_at) VALUES (?,?,?,?,?,?)",
                       (key, "manual", "QUEUED", dumps(recipe), dumps(request), iso(at)))
            self._audit(db, at, "RUN_QUEUED", key, {"source": "manual"})
        return key

    def _rehearsed(self, db, recipe, request):
        for row in db.execute("SELECT report FROM attempts WHERE state='VERIFIED' AND report IS NOT NULL ORDER BY rowid DESC"):
            report = json.loads(row[0])
            if (report.get("recipe_sha256") == digest(recipe) and
                report.get("parameters") == {"topic": request["topic"], "limit": request["limit"]} and
                report.get("scenario") == request["case"] and
                report.get("fixture_transport") == request["fixture_transport"]):
                return True
        return False

    def create_schedule(self, spec, recipe, request, at):
        validate_schedule(spec)
        validate_recipe(recipe)
        if not any(step["op"] == "collect" for step in recipe["steps"]):
            raise ContractError("Recurring execution needs a file-effect contract, not just replayed clicks")
        if request.get("pause_after") is not None or request.get("case") != "normal":
            raise ContractError("Schedules require the normal fixture and no test pause")
        request = {key: request[key] for key in ("topic", "limit", "case", "fixture_transport")}
        key = str(uuid4())
        with self.connection(write=True) as db:
            current = json.loads(db.execute("SELECT value FROM config WHERE key='active_recipe'").fetchone()[0])
            if digest(current) != digest(recipe):
                raise ContractError("Active recipe changed; review again")
            if self._unresolved(db):
                raise ContractError("Resolve interrupted work before scheduling")
            if not self._rehearsed(db, recipe, request):
                raise ContractError("First complete a verified rehearsal with this exact recipe, topic, count and transport")
            db.execute("INSERT INTO schedules VALUES (?,?,?,?,?,?,?,NULL)",
                       (key, dumps(spec), dumps(recipe), dumps(request), 1, iso(next_due(spec, at)), iso(at)))
            self._audit(db, at, "SCHEDULE_CREATED", key, {"spec": spec, "recipe_sha256": digest(recipe)})
        return key

    def schedules(self):
        with self.connection() as db:
            return [{"id": row["id"], "spec": json.loads(row["spec"]), "request": json.loads(row["request"]),
                     "recipe_sha256": digest(json.loads(row["recipe"])), "enabled": bool(row["enabled"]),
                     "next_due_at": row["next_due_at"], "pause_reason": row["pause_reason"]}
                    for row in db.execute("SELECT * FROM schedules ORDER BY created_at DESC")]

    def toggle_schedule(self, key, enabled, reviewed_sha, at):
        if type(enabled) is not bool:
            raise ContractError("Enabled must be a boolean")
        with self.connection(write=True) as db:
            row = db.execute("SELECT * FROM schedules WHERE id=?", (key,)).fetchone()
            if not row:
                raise ContractError("Unknown schedule")
            if enabled:
                recipe = json.loads(db.execute("SELECT value FROM config WHERE key='active_recipe'").fetchone()[0])
                if reviewed_sha != digest(recipe):
                    raise ContractError("Review the active recipe to resume this schedule")
                if self._unresolved(db):
                    raise ContractError("An interrupted attempt still needs review")
                if not self._rehearsed(db, recipe, json.loads(row["request"])):
                    raise ContractError("A matching verified rehearsal is required")
                db.execute("UPDATE schedules SET enabled=1,recipe=?,next_due_at=?,pause_reason=NULL WHERE id=?",
                           (dumps(recipe), iso(next_due(json.loads(row["spec"]), at)), key))
            else:
                db.execute("UPDATE schedules SET enabled=0,pause_reason='OPERATOR_PAUSED' WHERE id=?", (key,))
                db.execute("UPDATE attempts SET state='CANCELLED',finished_at=? WHERE schedule_id=? AND state='QUEUED'",
                           (iso(at), key))
            self._audit(db, at, "SCHEDULE_RESUMED" if enabled else "SCHEDULE_PAUSED", key,
                        {"paused_days_are_not_backfilled": True})

    def enqueue_due(self, at):
        """Coalesce missed days into ONE latest occurrence; never replay a backlog."""
        materialized = []
        with self.connection(write=True) as db:
            if self._unresolved(db):
                return []
            rows = db.execute("SELECT * FROM schedules WHERE enabled=1 AND next_due_at<=? ORDER BY next_due_at,id", (iso(at),)).fetchall()
            for row in rows:
                spec = json.loads(row["spec"])
                due = latest_due(spec, at)
                old_due = parse(row["next_due_at"])
                db.execute("UPDATE schedules SET next_due_at=? WHERE id=?", (iso(next_due(spec, at)), row["id"]))
                pending = db.execute("SELECT id,state,due_at FROM attempts WHERE schedule_id=? AND state IN ('QUEUED','RUNNING')", (row["id"],)).fetchall()
                if any(p["state"] == "RUNNING" or parse(p["due_at"]) >= due for p in pending):
                    self._audit(db, at, "OCCURRENCE_SKIPPED_OVERLAP", row["id"], {"due_at": iso(due)})
                    continue
                # A queued occurrence has performed no effects. Replace an old
                # unstarted day rather than replaying a backlog after downtime.
                for pending_row in pending:
                    db.execute("UPDATE attempts SET state='SUPERSEDED',finished_at=? WHERE id=?", (iso(at), pending_row["id"]))
                    self._audit(db, at, "QUEUED_OCCURRENCE_SUPERSEDED", pending_row["id"], {"replaced_by_due_at": iso(due)})
                late = (at - due).total_seconds()
                if (spec["misfire"] == "skip" and late > spec["grace_seconds"]) or late > 86400:
                    self._audit(db, at, "MISSED_RUN_SKIPPED", row["id"], {"due_at": iso(due), "late_seconds": late})
                    continue
                request = json.loads(row["request"])
                request["job_key"] = "schedule:" + row["id"] + ":" + iso(due)
                key = str(uuid4())
                cursor = db.execute("INSERT OR IGNORE INTO attempts(id,schedule_id,due_at,source,state,recipe,request,created_at) VALUES (?,?,?,?,?,?,?,?)",
                                    (key, row["id"], iso(due), "schedule", "QUEUED", row["recipe"], dumps(request), iso(at)))
                if cursor.rowcount:
                    materialized.append(key)
                    self._audit(db, at, "SCHEDULE_OCCURRENCE_QUEUED", row["id"],
                                {"attempt": key, "due_at": iso(due), "coalesced_from": iso(old_due), "late_seconds": late})
        return materialized

    def claim(self, at):
        with self.connection(write=True) as db:
            if self._unresolved(db) or db.execute("SELECT 1 FROM attempts WHERE state='RUNNING'").fetchone():
                return None
            while True:
                row = db.execute("SELECT * FROM attempts WHERE state='QUEUED' ORDER BY created_at,id LIMIT 1").fetchone()
                if not row:
                    return None
                if row["schedule_id"]:
                    schedule = db.execute("SELECT * FROM schedules WHERE id=?", (row["schedule_id"],)).fetchone()
                    spec = json.loads(schedule["spec"])
                    late = (at - parse(row["due_at"])).total_seconds()
                    if not schedule["enabled"] or late > 86400 or (spec["misfire"] == "skip" and late > spec["grace_seconds"]):
                        db.execute("UPDATE attempts SET state='MISSED',finished_at=? WHERE id=?", (iso(at), row["id"]))
                        self._audit(db, at, "QUEUED_OCCURRENCE_EXPIRED", row["id"], {"late_seconds": late})
                        continue
                break
            db.execute("UPDATE attempts SET state='RUNNING',started_at=? WHERE id=?", (iso(at), row["id"]))
            self._audit(db, at, "RUN_STARTED", row["id"], {"source": row["source"]})
            result = dict(row)
            result["state"] = "RUNNING"
            result["recipe"] = json.loads(row["recipe"])
            result["request"] = json.loads(row["request"])
            return result

    def finish(self, key, report, at):
        if report.get("status") not in ("VERIFIED", "REPLAYED", "PARTIAL", "HALTED", "PAUSED", "CANCELLED"):
            raise ContractError("Runner returned an invalid terminal outcome")
        with self.connection(write=True) as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (key,)).fetchone()
            if not row or row["state"] != "RUNNING":
                raise ContractError("Only an owned RUNNING attempt can be completed")
            report = {**report, "attempt_id": key, "trigger": row["source"], "schedule_id": row["schedule_id"], "due_at": row["due_at"]}
            db.execute("UPDATE attempts SET state=?,finished_at=?,report=? WHERE id=?",
                       (report["status"], iso(at), dumps(report), key))
            if row["schedule_id"] and report["status"] != "VERIFIED":
                db.execute("UPDATE schedules SET enabled=0,pause_reason=? WHERE id=?",
                           ("LAST_RUN_" + report["status"], row["schedule_id"]))
            self._audit(db, at, "RUN_FINISHED", key, {"status": report["status"], "verified_count": report.get("verified_count", 0)})

    def recover_interrupted(self, at):
        """Only call after acquiring the exclusive process ownership lock."""
        with self.connection(write=True) as db:
            rows = db.execute("SELECT id,schedule_id FROM attempts WHERE state='RUNNING'").fetchall()
            for row in rows:
                db.execute("UPDATE attempts SET state='NEEDS_REVIEW',finished_at=? WHERE id=?", (iso(at), row["id"]))
                self._audit(db, at, "INTERRUPTED_NEEDS_REVIEW", row["id"], {"automatic_retry": False})
            if rows:
                db.execute("UPDATE schedules SET enabled=0,pause_reason='INTERRUPTED_RUN' WHERE enabled=1")
            return len(rows)

    def resolve_interrupted(self, key, acknowledgement, at):
        if acknowledgement != "I checked the outcome; do not retry this attempt":
            raise ContractError("Explicit reconciliation acknowledgement is required")
        with self.connection(write=True) as db:
            row = db.execute("SELECT state FROM attempts WHERE id=?", (key,)).fetchone()
            if not row or row["state"] != "NEEDS_REVIEW":
                raise ContractError("Attempt is not waiting for review")
            db.execute("UPDATE attempts SET state='ABANDONED',finished_at=? WHERE id=?", (iso(at), key))
            self._audit(db, at, "INTERRUPTED_RECONCILED_WITHOUT_RETRY", key, {"acknowledgement": acknowledgement})

    def cancel_queued(self, at):
        with self.connection(write=True) as db:
            rows = db.execute("SELECT id,schedule_id FROM attempts WHERE state='QUEUED'").fetchall()
            for row in rows:
                db.execute("UPDATE attempts SET state='CANCELLED',finished_at=? WHERE id=?", (iso(at), row["id"]))
                if row["schedule_id"]:
                    db.execute("UPDATE schedules SET enabled=0,pause_reason='OPERATOR_STOPPED' WHERE id=?", (row["schedule_id"],))
                self._audit(db, at, "QUEUED_RUN_CANCELLED", row["id"], {})

    def attempts(self, limit=50):
        with self.connection() as db:
            return [{"id": row["id"], "source": row["source"], "state": row["state"],
                     "schedule_id": row["schedule_id"], "due_at": row["due_at"],
                     "created_at": row["created_at"], "started_at": row["started_at"],
                     "request": json.loads(row["request"]), "report": json.loads(row["report"]) if row["report"] else None}
                    for row in db.execute("SELECT * FROM attempts ORDER BY created_at DESC,rowid DESC LIMIT ?", (limit,))]

    def history(self, limit=20):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT report FROM attempts WHERE report IS NOT NULL ORDER BY finished_at DESC,rowid DESC LIMIT ?", (limit,))]

    def report(self, run_id):
        # Local history is intentionally small; no filesystem path is accepted from the API.
        with self.connection() as db:
            for row in db.execute("SELECT report FROM attempts WHERE report IS NOT NULL ORDER BY rowid DESC"):
                report = json.loads(row[0])
                if report.get("run_id") == run_id:
                    return report
        return None

    def audit(self, limit=100):
        with self.connection() as db:
            return [{**dict(row), "detail": json.loads(row["detail"])} for row in
                    db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]
