from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .models import Plan, Schedule


def now():
    return datetime.now(timezone.utc).isoformat()


def next_due(schedule: Schedule, after: datetime) -> str:
    zone = ZoneInfo(schedule.timezone)
    hour, minute = map(int, schedule.time.split(':'))
    day = after.astimezone(zone).date()
    for offset in range(370):
        wall = datetime.combine(day + timedelta(days=offset), datetime.min.time()).replace(hour=hour,minute=minute)
        # Skip nonexistent times, use only the first fold during DST fallback.
        options = []
        for fold in (0,1):
            candidate = wall.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc)
            if candidate.astimezone(zone).replace(tzinfo=None) == wall:
                options.append(candidate)
        if options and min(options) > after:
            return min(options).isoformat()
    raise ValueError('Cannot compute next schedule occurrence.')


class Store:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True,exist_ok=True)
        self.file = self.folder/'agent.db'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,plan TEXT NOT NULL,sha TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,next_due TEXT,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,request_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL,started TEXT NOT NULL,finished TEXT,result TEXT NOT NULL DEFAULT '{}');
            CREATE UNIQUE INDEX IF NOT EXISTS single_active_run ON runs((1)) WHERE status='RUNNING';
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,run_id TEXT,at TEXT NOT NULL,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS effects(task_id TEXT NOT NULL,item TEXT NOT NULL,state TEXT NOT NULL,
                data TEXT NOT NULL,PRIMARY KEY(task_id,item));
            ''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.file,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def setting(self,key,default=None):
        with self.db() as db:
            row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self,key,value):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))

    def recover(self):
        # Called only after the process owns the data-folder lock.
        with self.db() as db:
            db.execute("UPDATE tasks SET enabled=0 WHERE id IN (SELECT task_id FROM runs WHERE status='RUNNING')")
            db.execute("UPDATE runs SET status='NEEDS_REVIEW',finished=?,result=? WHERE status='RUNNING'",
                       (now(),json.dumps({'error':'Process stopped during execution; reconcile before resuming.'})))

    def save(self,plan: Plan):
        if plan.missing_information:
            raise ValueError('Provide missing information before saving a task.')
        task_id=uuid.uuid4().hex
        due=next_due(plan.schedule,datetime.now(timezone.utc)) if plan.schedule else None
        with self.db() as db:
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)',(task_id,plan.model_dump_json(),plan.digest(),0,due,now()))
        return self.task(task_id)

    def task(self,task_id):
        with self.db() as db:
            row=db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not row:
            raise ValueError('Task not found.')
        task=dict(row);task['plan']=Plan.model_validate_json(task['plan'])
        if task['sha'] != task['plan'].digest():
            raise ValueError('Task integrity check failed.')
        return task

    def begin(self,task_id,request_id):
        with self.db() as db:
            prior=db.execute('SELECT * FROM runs WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if prior['task_id'] != task_id:
                    raise ValueError('Request ID belongs to another task.')
                return dict(prior),False
            if db.execute("SELECT 1 FROM runs WHERE task_id=? AND status='NEEDS_REVIEW'",(task_id,)).fetchone():
                raise ValueError('Reconcile the previous uncertain run before starting again.')
            run_id=uuid.uuid4().hex
            db.execute('INSERT INTO runs(id,task_id,request_id,status,started) VALUES (?,?,?,?,?)',
                       (run_id,task_id,request_id,'RUNNING',now()))
        return {'id':run_id,'task_id':task_id,'status':'RUNNING'},True

    def event(self,run_id,data):
        with self.db() as db:
            db.execute('INSERT INTO events(run_id,at,data) VALUES (?,?,?)',(run_id,now(),json.dumps(data)))

    def effect(self,task_id,item,state=None,data=None):
        with self.db() as db:
            if state:
                db.execute('INSERT OR REPLACE INTO effects VALUES (?,?,?,?)',(task_id,item,state,json.dumps(data or {})))
            row=db.execute('SELECT * FROM effects WHERE task_id=? AND item=?',(task_id,item)).fetchone()
        return {**dict(row),'data':json.loads(row['data'])} if row else None

    def finish(self,run_id,status,result):
        with self.db() as db:
            db.execute('UPDATE runs SET status=?,finished=?,result=? WHERE id=?',(status,now(),json.dumps(result),run_id))
            if status not in ('VERIFIED','OBSERVED'):
                db.execute('UPDATE tasks SET enabled=0 WHERE id=(SELECT task_id FROM runs WHERE id=?)',(run_id,))

    def enable(self,task_id,enabled):
        task=self.task(task_id)
        if enabled and not task['plan'].schedule:
            raise ValueError('Task has no daily schedule.')
        with self.db() as db:
            if enabled and not db.execute("SELECT 1 FROM runs WHERE task_id=? AND status='VERIFIED'",(task_id,)).fetchone():
                raise ValueError('Complete one verified run before enabling unattended daily execution.')
            if enabled and db.execute("SELECT 1 FROM runs WHERE task_id=? AND status='NEEDS_REVIEW'",(task_id,)).fetchone():
                raise ValueError('Reconcile the uncertain run first.')
            due=next_due(task['plan'].schedule,datetime.now(timezone.utc)) if enabled else task['next_due']
            db.execute('UPDATE tasks SET enabled=?,next_due=? WHERE id=?',(int(enabled),due,task_id))

    def due(self,at):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT id,next_due FROM tasks WHERE enabled=1 AND next_due<=?',(at.isoformat(),))]

    def advance(self,task_id,at):
        task=self.task(task_id)
        with self.db() as db:
            db.execute('UPDATE tasks SET next_due=? WHERE id=?',(next_due(task['plan'].schedule,at),task_id))

    def snapshot(self):
        with self.db() as db:
            tasks=[{**dict(r),'plan':json.loads(r['plan'])} for r in db.execute('SELECT * FROM tasks ORDER BY created DESC')]
            runs=[{**dict(r),'result':json.loads(r['result'])} for r in db.execute('SELECT * FROM runs ORDER BY started DESC LIMIT 100')]
        return {'tasks':tasks,'runs':runs}

    def reconcile(self,run_id,decision):
        if decision not in ('completed','absent'):
            raise ValueError('Explicitly choose completed or absent after inspecting the outcome.')
        with self.db() as db:
            row=db.execute("SELECT * FROM runs WHERE id=? AND status='NEEDS_REVIEW'",(run_id,)).fetchone()
            if not row:raise ValueError('Choose a run that needs review.')
            result=json.loads(row['result']);result['human_resolution']={'decision':decision,'at':now()}
            db.execute("UPDATE runs SET status='REVIEWED',result=? WHERE id=?",(json.dumps(result),run_id))
            db.execute("UPDATE effects SET state=? WHERE task_id=? AND state='STARTED'",
                       ('VERIFIED' if decision=='completed' else 'RELEASED',row['task_id']))
        self.event(run_id,{'human_resolution':decision})
