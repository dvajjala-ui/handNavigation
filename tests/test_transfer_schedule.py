"""Scheduling state tests plus a real subprocess/browser transfer acceptance check."""
from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys

import pytest

from handnavigate.live.contracts import LiveError, digest
from handnavigate.transfer.contracts import approve, template
from handnavigate.transfer.demo import running_demo
from handnavigate.transfer.scheduler import Scheduler, execute_worker, kill_worker
from handnavigate.transfer.store import Journal


def setup_schedule(tmp_path, execute=None):
    recipe = template('https://source.example', 'https://target.example')
    receipt = approve(recipe, {})
    journal = Journal(tmp_path)
    journal.begin('explicit-scheduler-test-double', digest({'recipe': recipe, 'inputs': {}}), 'scheduler-test')
    journal.finish('explicit-scheduler-test-double', {'status': 'VERIFIED'})
    journal.close()
    clock = [datetime(2026, 10, 25, 3, 0, tzinfo=timezone.utc)]
    calls = []
    def success(*args):
        calls.append(args[4])
        return {'status': 'VERIFIED', 'job': args[4]}
    scheduler = Scheduler(tmp_path, clock=lambda: clock[0], execute=execute or success)
    spec = {'name': 'daily transfer', 'time': '09:00', 'timezone': 'Asia/Kolkata', 'misfire': 'run_once', 'grace_seconds': 3600}
    identifier = scheduler.add(recipe, {}, receipt, spec)
    return scheduler, clock, calls, identifier


def test_daily_job_pinned_and_deduplicated_across_restart(tmp_path):
    scheduler, clock, calls, identifier = setup_schedule(tmp_path)
    assert scheduler.tick() == []
    clock[0] += timedelta(minutes=30)
    assert len(scheduler.tick()) == 1
    assert scheduler.tick() == []
    assert len(calls) == 1
    scheduler.close()
    again = Scheduler(tmp_path, clock=lambda: clock[0], execute=lambda *args: pytest.fail('same occurrence repeated'))
    assert again.tick() == []
    again.close()


def test_missed_days_only_materialize_one_latest_run(tmp_path):
    scheduler, clock, calls, _ = setup_schedule(tmp_path)
    clock[0] += timedelta(days=5, minutes=45)
    assert len(scheduler.tick()) == 1
    assert len(calls) == 1
    assert scheduler.tick() == []
    scheduler.close()


def test_failed_run_pauses_schedule(tmp_path):
    scheduler, clock, _, _ = setup_schedule(tmp_path, execute=lambda *args: {'status': 'NEEDS_REVIEW'})
    clock[0] += timedelta(hours=1)
    assert scheduler.tick()[0]['status'] == 'NEEDS_REVIEW'
    assert scheduler.list()[0]['enabled'] is False
    scheduler.close()


def test_interrupted_occurrence_never_automatically_repeats(tmp_path):
    scheduler, clock, _, identifier = setup_schedule(tmp_path)
    with scheduler.db:
        scheduler.db.execute("INSERT INTO occurrences VALUES (?,?,?,'RUNNING',NULL)", (identifier, scheduler.list()[0]['due'], 'interrupted-test-double'))
    assert scheduler.tick() == []
    assert scheduler.list()[0]['enabled'] is False
    assert scheduler.db.execute('SELECT status FROM occurrences').fetchone()[0] == 'NEEDS_REVIEW'
    scheduler.close()


def test_schedule_requires_exact_verified_rehearsal(tmp_path):
    scheduler, clock, _, _ = setup_schedule(tmp_path)
    recipe = template('https://source.example', 'https://target.example', 2)
    with pytest.raises(LiveError):
        scheduler.add(recipe, {}, approve(recipe, {}), {'name':'new task', 'time':'10:00', 'timezone':'Asia/Kolkata', 'misfire':'skip', 'grace_seconds':0})
    scheduler.close()


def test_real_cli_worker_uploads_and_verifies(tmp_path):
    with running_demo(count=2) as (recipe, uploads, _, state):
        recipe['count'] = 2
        result = execute_worker(recipe, {}, approve(recipe, {}), tmp_path, 'subprocess-acceptance')
        assert result['status'] == 'VERIFIED', result
        assert result['confirmed'] == len(uploads) == state['post_count'] == 2
        assert result['execution_id']


def test_watchdog_terminates_a_real_worker():
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], **options)
    try:
        kill_worker(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill(); process.wait()
