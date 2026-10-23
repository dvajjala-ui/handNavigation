"""Durable teaching drafts, checksum approvals, plans and supervised batch runs.

New lessons are immutable. Import never carries approval. A shared execution
lock prevents the original scheduler and this rehearsal from running together.
In-flight work recovered after a restart requires acknowledgement, not retry.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import threading
from uuid import UUID, uuid4

from .contracts import ContractError, digest
from .teaching import compile_lesson, make_plan, timestamp, validate_lesson
from .teaching_runner import execute_lesson


def uuid_key(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ContractError('Expected a canonical UUID') from None
    return value


def dumps(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


class TeachingService:
    def __init__(self, store, root, execution_lock, *, execute=None):
        self.store, self.root, self.execution_lock = store, Path(root).resolve(), execution_lock
        self.execute = execute or execute_lesson
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread = None
        self.active_id = None
        self.closing = False
        self.error = None
        with self.store.connection(write=True) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS teaching_lessons(
                  id TEXT PRIMARY KEY, recipe TEXT NOT NULL, sha TEXT NOT NULL,
                  approved_sha TEXT, source TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS teaching_runs(
                  id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                  lesson_id TEXT NOT NULL, plan_sha TEXT NOT NULL, rows_json TEXT NOT NULL,
                  state TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT, report TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_running_lesson
                  ON teaching_runs((1)) WHERE state='RUNNING';
            ''')
            # RuntimeOwnership belongs to the parent Controller, acquired first.
            interrupted = db.execute("SELECT id FROM teaching_runs WHERE state='RUNNING'").fetchall()
            db.execute("UPDATE teaching_runs SET state='NEEDS_REVIEW' WHERE state='RUNNING'")
            for row in interrupted:
                self._audit(db, 'TEACHING_INTERRUPTED', row['id'], {'automatic_retry': False})

    def _audit(self, db, event, subject, detail):
        db.execute('INSERT INTO audit(at,event,subject,detail) VALUES(?,?,?,?)',
                   (timestamp(), event, subject, dumps(detail)))

    def _lesson(self, row):
        if row is None:
            raise ContractError('Lesson not found')
        recipe = json.loads(row['recipe'])
        validate_lesson(recipe)
        if digest(recipe) != row['sha']:
            raise ContractError('Stored lesson does not match its checksum')
        return {'id': row['id'], 'recipe': recipe, 'sha256': row['sha'],
                'approved': row['approved_sha'] == row['sha'],
                'source': row['source'], 'created_at': row['created_at']}

    def get(self, key):
        uuid_key(key)
        with self.store.connection() as db:
            return self._lesson(db.execute('SELECT * FROM teaching_lessons WHERE id=?', (key,)).fetchone())

    def create(self, recipe, source='Imported recipe; not trusted and not approved'):
        validate_lesson(recipe)
        key, sha = str(uuid4()), digest(recipe)
        with self.store.connection(write=True) as db:
            db.execute('INSERT INTO teaching_lessons VALUES(?,?,?,?,?,?)',
                       (key, dumps(recipe), sha, None, source, timestamp()))
            self._audit(db, 'TEACHING_DRAFT_CREATED', key, {'recipe_sha256': sha, 'source': source})
        return self.get(key)

    def compile(self, args):
        recipe = compile_lesson(args['events'], args['bindings'], name=args['name'],
                                verification_contract=args['verification_contract'], max_rows=args['max_rows'])
        return self.create(recipe, 'Explicit recording compilation; variables, verifier and repeat bound supplied by reviewer')

    def approve(self, key, reviewed_sha256, acknowledgement):
        uuid_key(key)
        if acknowledgement is not True:
            raise ContractError('Explicit review acknowledgement required')
        with self.store.connection(write=True) as db:
            lesson = self._lesson(db.execute('SELECT * FROM teaching_lessons WHERE id=?', (key,)).fetchone())
            if reviewed_sha256 != lesson['sha256']:
                raise ContractError('Lesson changed; review the exact checksum')
            db.execute('UPDATE teaching_lessons SET approved_sha=sha WHERE id=?', (key,))
            self._audit(db, 'TEACHING_APPROVED', key, {'recipe_sha256': reviewed_sha256})
        return self.get(key)

    def revoke(self, key):
        uuid_key(key)
        with self.lock, self.store.connection(write=True) as db:
            self._lesson(db.execute('SELECT * FROM teaching_lessons WHERE id=?', (key,)).fetchone())
            if db.execute("SELECT 1 FROM teaching_runs WHERE lesson_id=? AND state='RUNNING'", (key,)).fetchone():
                raise ContractError('Stop and finish the active rehearsal before revoking approval')
            db.execute('UPDATE teaching_lessons SET approved_sha=NULL WHERE id=?', (key,))
            self._audit(db, 'TEACHING_REVOKED', key, {})
        return self.get(key)

    def plan(self, key, rows):
        lesson = self.get(key)
        return {'lesson_id': key, 'approved': lesson['approved'], **make_plan(lesson['recipe'], rows)}

    def start(self, key, rows, reviewed_plan_sha256, request_id):
        uuid_key(key)
        uuid_key(request_id)
        with self.lock:
            if self.closing or self.error:
                raise ContractError('Teaching runner is stopped; restart and review interrupted work')
            lesson = self.get(key)
            plan = make_plan(lesson['recipe'], rows)
            if not lesson['approved'] or plan['plan_sha256'] != reviewed_plan_sha256:
                raise ContractError('Approve the lesson and review the unchanged input plan first')
            with self.store.connection() as db:
                old = db.execute('SELECT * FROM teaching_runs WHERE request_id=?', (request_id,)).fetchone()
                if old:
                    if old['lesson_id'] != key or old['plan_sha'] != reviewed_plan_sha256:
                        raise ContractError('This request ID already belongs to a different execution plan')
                    return {'run_id': old['id'], 'state': old['state'], 'deduplicated': True}
                if db.execute("SELECT 1 FROM teaching_runs WHERE state='NEEDS_REVIEW'").fetchone():
                    raise ContractError('Review interrupted teaching work before starting another batch')
            if not self.execution_lock.acquire(blocking=False):
                raise ContractError('The local browser runner is busy; no second execution was started')
            run_id = str(uuid4())
            try:
                with self.store.connection(write=True) as db:
                    # Recheck approval in the write transaction before recording the effect intent.
                    latest = self._lesson(db.execute('SELECT * FROM teaching_lessons WHERE id=?', (key,)).fetchone())
                    if not latest['approved'] or latest['sha256'] != lesson['sha256']:
                        raise ContractError('Approval was revoked before execution')
                    db.execute('INSERT INTO teaching_runs VALUES(?,?,?,?,?,?,?,?,?)',
                               (run_id, request_id, key, reviewed_plan_sha256, dumps(rows), 'RUNNING', timestamp(), None, None))
                    self._audit(db, 'TEACHING_STARTED', run_id, {'lesson_id': key, 'plan_sha256': reviewed_plan_sha256, 'rows': len(rows)})
                self.active_id = run_id
                self.cancel_event = threading.Event()
                self.thread = threading.Thread(target=self._work,
                    args=(run_id, lesson, json.loads(dumps(rows)), reviewed_plan_sha256),
                    name='handnavigate-teaching', daemon=True)
                self.thread.start()
            except BaseException:
                self.thread = None
                self.active_id = None
                self.execution_lock.release()
                # A committed intent without a worker is still explicit unresolved work.
                with self.store.connection(write=True) as db:
                    db.execute("UPDATE teaching_runs SET state='NEEDS_REVIEW' WHERE id=? AND state='RUNNING'", (run_id,))
                raise
            return {'run_id': run_id, 'state': 'RUNNING', 'deduplicated': False}

    def _work(self, run_id, lesson, rows, plan_sha):
        try:
            def progress(report):
                with self.store.connection(write=True) as db:
                    db.execute("UPDATE teaching_runs SET report=? WHERE id=? AND state='RUNNING'", (dumps(report), run_id))
            report = self.execute(lesson['recipe'], {'recipe_sha256': lesson['sha256']}, rows,
                output=self.root, reviewed_plan_sha256=plan_sha, run_id=run_id,
                cancel_event=self.cancel_event, on_progress=progress)
            if report.get('status') not in ('VERIFIED', 'HALTED', 'CANCELLED'):
                raise ContractError('Runner did not produce a terminal result')
            with self.store.connection(write=True) as db:
                db.execute('UPDATE teaching_runs SET state=?,report=?,finished_at=? WHERE id=?',
                           (report['status'], dumps(report), timestamp(), run_id))
                self._audit(db, 'TEACHING_FINISHED', run_id,
                            {'state': report['status'], 'verified_rows': report.get('verified_rows', 0)})
        except Exception:
            # A persistence/worker failure may follow an action; do not fabricate a clean halt or retry.
            self.error = 'Runner bookkeeping failed; review required, no automatic retry'
            try:
                with self.store.connection(write=True) as db:
                    db.execute("UPDATE teaching_runs SET state='NEEDS_REVIEW' WHERE id=?", (run_id,))
                    self._audit(db, 'TEACHING_NEEDS_REVIEW', run_id, {'automatic_retry': False})
            except Exception:
                pass  # RUNNING remains durable and becomes NEEDS_REVIEW on restart.
        finally:
            self.active_id = None
            self.execution_lock.release()

    def stop(self, run_id):
        uuid_key(run_id)
        with self.lock:
            if run_id != self.active_id:
                raise ContractError('This is not the active teaching run')
            self.cancel_event.set()
        return {'stop_requested': True, 'notice': 'Cooperative stop at a safe step boundary, not a hard kill'}

    def acknowledge(self, run_id, acknowledgement):
        uuid_key(run_id)
        if acknowledgement != 'REVIEWED_WITHOUT_RETRY':
            raise ContractError('Explicitly acknowledge reviewed work without retrying it')
        with self.store.connection(write=True) as db:
            updated = db.execute("UPDATE teaching_runs SET state='ACKNOWLEDGED' WHERE id=? AND state='NEEDS_REVIEW'", (run_id,))
            if updated.rowcount != 1:
                raise ContractError('No interrupted run with that ID')
            self._audit(db, 'TEACHING_ACKNOWLEDGED', run_id, {'automatic_retry': False})
        return {'acknowledged': True, 'retried': False}

    def snapshot(self):
        with self.store.connection() as db:
            lessons = [self._lesson(row) for row in db.execute('SELECT * FROM teaching_lessons ORDER BY created_at DESC LIMIT 30')]
            runs = [{'id': row['id'], 'lesson_id': row['lesson_id'], 'state': row['state'],
                     'created_at': row['created_at'], 'finished_at': row['finished_at'],
                     'plan_sha256': row['plan_sha'], 'report': json.loads(row['report']) if row['report'] else None}
                    for row in db.execute('SELECT * FROM teaching_runs ORDER BY created_at DESC LIMIT 30')]
        return {'lessons': lessons, 'runs': runs, 'active_id': self.active_id, 'error': self.error,
                'scope': 'Owned form rehearsals only; not connected to schedules or authenticated sites'}

    def artifact(self, run_id, row_id):
        uuid_key(run_id)
        with self.store.connection() as db:
            row = db.execute('SELECT report FROM teaching_runs WHERE id=?', (run_id,)).fetchone()
        report = json.loads(row['report']) if row and row['report'] else None
        if not report:
            raise ContractError('Verified artifact not found')
        item = next((r for r in report.get('rows', []) if r['row_id'] == row_id and r['state'] == 'VERIFIED'), None)
        if not item:
            raise ContractError('Verified row not found')
        path = self.root / item['artifact']['path']
        if path.is_symlink() or not path.resolve().is_relative_to((self.root / 'lesson-artifacts').resolve()):
            raise ContractError('Artifact is outside the verified output directory')
        if path.stat().st_size > 65536:
            raise ContractError('Artifact exceeded its verified size budget')
        content = path.read_bytes()
        if sha256(content).hexdigest() != item['artifact']['sha256']:
            raise ContractError('Artifact changed after verification')
        return content

    def close(self):
        with self.lock:
            self.closing = True
            self.cancel_event.set()
            thread = self.thread
        if thread:
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError('Teaching worker has not stopped; process ownership must not be released')
