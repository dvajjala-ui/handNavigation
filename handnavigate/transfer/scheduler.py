"""Pinned daily transfers, durable occurrence deduplication, and a process watchdog."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
from uuid import uuid4

from ..live.contracts import LiveError, digest, save_json
from ..ownership import RuntimeOwnership
from ..scheduling import iso, latest_due, next_due, parse, validate_schedule
from .contracts import require_approval


def kill_worker(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def execute_worker(recipe, inputs, receipt, root, job, source_profile=None, target_profile=None, *, headless=True):
    """Use a separate process so stalled browser/download code has a hard lifetime."""
    root = Path(root).resolve()
    folder = root/'workers'/digest({'job': job})
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in [('recipe', recipe), ('inputs', inputs), ('approval', receipt)]:
        save_json(folder/(name+'.json'), data)
    args = [sys.executable, '-m', 'handnavigate', 'live', 'transfer', 'run', str(folder/'recipe.json'),
            '--inputs', str(folder/'inputs.json'), '--approval', str(folder/'approval.json'),
            '--root', str(root), '--job', job, '--headless' if headless else '--headed', '--inside-worker']
    for flag, profile in [('--source-profile', source_profile), ('--target-profile', target_profile)]:
        if profile:
            args += [flag, str(Path(profile).resolve())]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    # Resolve the package path independently of the caller's current directory.
    env = dict(os.environ)
    execution_id = uuid4().hex
    env['HANDNAVIGATE_TRANSFER_EXECUTION_ID'] = execution_id
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])+os.pathsep+env.get('PYTHONPATH', '')
    process = None
    try:
        with (folder/'console.txt').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       env=env, **options)
            process.wait(timeout=recipe['limits']['timeout_seconds']+20)
        result_path = root/'runs'/(digest_job(job)+'.json')
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if (result.get('contract_sha256') == digest({'recipe': recipe, 'inputs': inputs}) and
                result.get('job') == job and result.get('execution_id') == execution_id):
                # A nonzero exit cannot reuse a previously VERIFIED receipt.
                if process.returncode == 0 and result['status'] == 'VERIFIED':
                    return result
                if process.returncode == 2 and result['status'] != 'VERIFIED':
                    return result
        raise LiveError('Transfer worker exited without a matching current result')
    except subprocess.TimeoutExpired:
        kill_worker(process)
        result = {'status': 'NEEDS_REVIEW', 'job': job, 'error': 'Worker exceeded its hard time limit; no uncertain upload was retried', 'model_calls': 0}
        save_json(root/'latest-result.json', result)
        return result
    except BaseException:
        if process:
            kill_worker(process)
        raise


def digest_job(job):
    from hashlib import sha256
    return sha256(job.encode()).hexdigest()


class Scheduler:
    def __init__(self, root, *, clock=None, execute=execute_worker):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.execute = execute
        self.db = sqlite3.connect(self.root/'transfer-schedules.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''CREATE TABLE IF NOT EXISTS schedules (
          id TEXT PRIMARY KEY, spec TEXT NOT NULL, recipe TEXT NOT NULL, inputs TEXT NOT NULL,
          approval TEXT NOT NULL, source_profile TEXT, target_profile TEXT,
          due TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
          CREATE TABLE IF NOT EXISTS occurrences (
          schedule TEXT NOT NULL, due TEXT NOT NULL, job TEXT NOT NULL, status TEXT NOT NULL,
          report TEXT, PRIMARY KEY(schedule,due));''')

    def add(self, recipe, inputs, receipt, spec, source_profile=None, target_profile=None):
        require_approval(recipe, inputs, receipt)
        validate_schedule(spec)
        journal = self.root/'transfers.sqlite3'
        if not journal.exists():
            raise LiveError('Complete one verified transfer before enabling a daily schedule')
        with sqlite3.connect(journal) as db:
            rehearsed = db.execute("SELECT 1 FROM jobs WHERE contract=? AND status='VERIFIED' LIMIT 1", (digest({'recipe': recipe, 'inputs': inputs}),)).fetchone()
        if not rehearsed:
            raise LiveError('Daily scheduling requires a verified run of these exact recipe and inputs')
        profile_paths = [str(Path(p).resolve()) if p else None for p in (source_profile, target_profile)]
        identifier = digest({'recipe': recipe, 'inputs': inputs, 'spec': spec, 'profiles': profile_paths})[:24]
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO schedules VALUES (?,?,?,?,?,?,?,?,1)',
                            (identifier, json.dumps(spec), json.dumps(recipe), json.dumps(inputs), json.dumps(receipt),
                             *profile_paths, iso(next_due(spec, self.clock()))))
        return identifier

    def list(self):
        return [{'id': r['id'], 'name': json.loads(r['spec'])['name'], 'due': r['due'], 'enabled': bool(r['enabled'])}
                for r in self.db.execute('SELECT * FROM schedules ORDER BY id')]

    def enable(self, identifier, enabled):
        with self.db:
            if self.db.execute('UPDATE schedules SET enabled=? WHERE id=?', (int(enabled), identifier)).rowcount != 1:
                raise LiveError('Unknown schedule')

    def tick(self):
        # Separate scheduler ownership allows add/list while a worker is active.
        owner = RuntimeOwnership(self.root/'scheduler-owner')
        try:
            # A process interruption never silently repeats the same external effects.
            with self.db:
                interrupted = self.db.execute("SELECT DISTINCT schedule FROM occurrences WHERE status='RUNNING'").fetchall()
                self.db.execute("UPDATE occurrences SET status='NEEDS_REVIEW' WHERE status='RUNNING'")
                for r in interrupted:
                    self.db.execute('UPDATE schedules SET enabled=0 WHERE id=?', (r['schedule'],))
            now = self.clock()
            reports = []
            for row in self.db.execute('SELECT * FROM schedules WHERE enabled=1 ORDER BY due').fetchall():
                if parse(row['due']) > now:
                    continue
                spec = json.loads(row['spec'])
                due = latest_due(spec, now)
                job = 'daily-'+row['id']+'-'+iso(due)
                stale = (now-due).total_seconds() > spec['grace_seconds']
                status = 'SKIPPED' if spec['misfire'] == 'skip' and stale else 'RUNNING'
                with self.db:
                    inserted = self.db.execute('INSERT OR IGNORE INTO occurrences(schedule,due,job,status) VALUES (?,?,?,?)',
                                               (row['id'], iso(due), job, status)).rowcount
                    self.db.execute('UPDATE schedules SET due=? WHERE id=?', (iso(next_due(spec, now)), row['id']))
                if not inserted or status == 'SKIPPED':
                    continue
                try:
                    result = self.execute(json.loads(row['recipe']), json.loads(row['inputs']), json.loads(row['approval']),
                                          self.root, job, row['source_profile'], row['target_profile'])
                except Exception as exc:
                    result = {'status': 'NEEDS_REVIEW', 'job': job, 'error': f'Worker failed: {type(exc).__name__}'}
                with self.db:
                    self.db.execute('UPDATE occurrences SET status=?,report=? WHERE schedule=? AND due=?',
                                    (result['status'], json.dumps(result), row['id'], iso(due)))
                    if result['status'] != 'VERIFIED':
                        self.db.execute('UPDATE schedules SET enabled=0 WHERE id=?', (row['id'],))
                reports.append(result)
            return reports
        finally:
            owner.close()

    def close(self):
        self.db.close()
