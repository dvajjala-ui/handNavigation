"""Durable item receipts. Unknown remote effects are reconciled before any retry."""
import json
from pathlib import Path
import sqlite3

from ..live.contracts import LiveError


class Journal:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'transfers.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS jobs (
              job TEXT PRIMARY KEY, contract TEXT NOT NULL, namespace TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'RUNNING', report TEXT);
            CREATE TABLE IF NOT EXISTS items (
              job TEXT NOT NULL, source_id TEXT NOT NULL, sha256 TEXT NOT NULL,
              artifact TEXT NOT NULL, metadata TEXT NOT NULL, state TEXT NOT NULL,
              target_id TEXT, PRIMARY KEY(job, sha256));
            CREATE INDEX IF NOT EXISTS states ON items(state);
            CREATE TABLE IF NOT EXISTS resolutions (
              job TEXT NOT NULL, sha256 TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')

    def begin(self, job, contract, namespace):
        if not isinstance(job, str) or not 1 <= len(job) <= 150:
            raise LiveError('job must be a nonempty identifier of at most 150 characters')
        previous = self.db.execute('SELECT * FROM jobs WHERE job=?', (job,)).fetchone()
        if previous and (previous['contract'] != contract or previous['namespace'] != namespace):
            raise LiveError('This job is pinned to different recipe/inputs; use a new job identifier')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO jobs(job,contract,namespace) VALUES (?,?,?)', (job, contract, namespace))

    def items(self, job):
        return [dict(row) for row in self.db.execute('SELECT * FROM items WHERE job=? ORDER BY rowid', (job,))]

    def add(self, job, source_id, metadata, artifact):
        with self.db:
            self.db.execute('INSERT INTO items VALUES (?,?,?,?,?,?,NULL)',
                            (job, source_id, metadata['sha256'], artifact, json.dumps(metadata), 'READY'))

    def state(self, job, hash_, state, target_id=None):
        if state not in {'READY', 'UPLOADING', 'NEEDS_REVIEW', 'CONFIRMED'}:
            raise LiveError('Invalid transfer state')
        with self.db:
            changed = self.db.execute('UPDATE items SET state=?,target_id=? WHERE job=? AND sha256=?',
                                     (state, target_id, job, hash_)).rowcount
            if changed != 1:
                raise LiveError('Missing transfer journal item')

    def known(self, namespace):
        return {row[0] for row in self.db.execute('''SELECT i.sha256 FROM items i JOIN jobs j ON i.job=j.job
                                                   WHERE j.namespace=? AND i.state='CONFIRMED' ''', (namespace,))}

    def uncertain(self, namespace):
        return [dict(row) for row in self.db.execute('''SELECT i.* FROM items i JOIN jobs j ON i.job=j.job
                          WHERE j.namespace=? AND i.state IN ('UPLOADING','NEEDS_REVIEW')''', (namespace,))]

    def resolve_not_uploaded(self, job, hash_):
        with self.db:
            changed = self.db.execute("UPDATE items SET state='READY',target_id=NULL WHERE job=? AND sha256=? AND state IN ('UPLOADING','NEEDS_REVIEW')", (job, hash_)).rowcount
            if changed != 1:
                raise LiveError('There is no uncertain upload matching this job and hash')
            self.db.execute("INSERT INTO resolutions(job,sha256,action) VALUES (?,?,'OPERATOR_CONFIRMED_NOT_UPLOADED')", (job, hash_))

    def finish(self, job, report):
        with self.db:
            self.db.execute('UPDATE jobs SET status=?,report=? WHERE job=?', (report['status'], json.dumps(report), job))

    def close(self):
        self.db.close()
