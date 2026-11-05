import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
from core.models import Permissions, Plan, Schedule
from core.policy import Policy
from core.storage import Store, next_due
from core.runtime import Runner, ProcessLock


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.files=self.root/'files';self.files.mkdir()
        self.store=Store(self.root/'state')
        self.store.set_setting('permissions',Permissions(cleanup_roots=[str(self.files)]).model_dump())

    def task(self,**kwargs):
        return self.store.save(Plan(name='Cleanup',instruction='Recycle temporary files',kind='cleanup',folder=str(self.files),pattern='*.tmp',**kwargs))

    def test_cleanup_recycles_only_matching_files_and_request_id_reuses_run(self):
        target=self.files/'a.tmp';target.write_text('disposable test file')
        keep=self.files/'keep.txt';keep.write_text('keep')
        nested=self.files/'nested';nested.mkdir();(nested/'b.tmp').write_text('keep nested')
        moved=[]
        def recycle(value):
            file=Path(value);file.rename(self.root/('recycled-'+file.name));moved.append(value)
        runner=Runner(self.store,None,recycle=recycle);task=self.task()
        result=runner.run(task['id'],'same-request-id')
        self.assertEqual(result['status'],'VERIFIED');self.assertEqual(len(moved),1)
        self.assertTrue(keep.exists());self.assertTrue((nested/'b.tmp').exists())
        self.assertEqual(runner.run(task['id'],'same-request-id')['id'],result['id'])
        self.assertEqual(len(moved),1)

    @unittest.skipUnless(sys.platform=='win32','Windows recycle-bin acceptance')
    def test_actual_windows_recycle_bin_for_disposable_file(self):
        file=self.files/'disposable.tmp';file.write_text('HandNavigate disposable acceptance file')
        result=Runner(self.store,None).run(self.task()['id'])
        self.assertEqual(result['status'],'VERIFIED',result);self.assertFalse(file.exists())

    def test_cleanup_budget_fails_before_any_removal(self):
        for name in ('a.tmp','b.tmp'):(self.files/name).write_text('keep')
        moved=[];runner=Runner(self.store,None,recycle=lambda file:moved.append(file))
        result=runner.run(self.task(max_items=1)['id'])
        self.assertEqual(result['status'],'HALTED');self.assertFalse(moved)

    def test_traversal_and_outside_paths_rejected(self):
        policy=Policy(Permissions(cleanup_roots=[str(self.files)]))
        for value in (str(self.root/'outside'),str(self.files/'..'/'outside')):
            with self.assertRaises(PermissionError):policy.folder(value)

    def test_symlink_target_rejected(self):
        link=self.files/'alias'
        try:link.symlink_to(self.root,target_is_directory=True)
        except OSError:self.skipTest('OS has not enabled user symlinks')
        with self.assertRaises(PermissionError):Policy(Permissions(cleanup_roots=[str(self.files)])).folder(str(link))

    def test_restart_requires_review_and_pauses_schedule(self):
        task=self.task(schedule=Schedule(time='09:00'))
        run,_=self.store.begin(task['id'],'interrupted-request')
        with self.store.db() as db:db.execute('UPDATE tasks SET enabled=1 WHERE id=?',(task['id'],))
        self.store.recover()
        self.assertFalse(self.store.task(task['id'])['enabled'])
        self.assertEqual(self.store.snapshot()['runs'][0]['status'],'NEEDS_REVIEW')
        result=Runner(self.store,None).run(task['id'])
        self.assertEqual(result['status'],'HALTED')
        self.store.reconcile(run['id'],'absent')
        self.assertEqual(Runner(self.store,None).run(task['id'])['status'],'VERIFIED')

    def test_permissions_are_rechecked_after_revocation(self):
        task=self.task();self.store.set_setting('permissions',{})
        self.assertEqual(Runner(self.store,None).run(task['id'])['status'],'HALTED')

    def test_schedule_runs_once_after_downtime_and_deduplicates(self):
        task=self.task(schedule=Schedule(time='09:00'));runner=Runner(self.store,None)
        runner.run(task['id']);self.store.enable(task['id'],True)
        with self.store.db() as db:db.execute('UPDATE tasks SET next_due=? WHERE id=?',('2026-10-01T03:30:00+00:00',task['id']))
        at=datetime(2026,11,4,5,tzinfo=timezone.utc)
        self.assertEqual(len(runner.tick(at)),1);self.assertEqual(len(runner.tick(at)),0)

    def test_schedule_requires_verified_rehearsal(self):
        task=self.task(schedule=Schedule(time='09:00'))
        with self.assertRaises(ValueError):self.store.enable(task['id'],True)

    def test_dst_nonexistent_time_skipped(self):
        due=next_due(Schedule(time='02:30',timezone='America/New_York'),datetime(2026,3,8,0,tzinfo=timezone.utc))
        self.assertEqual(due,'2026-03-09T06:30:00+00:00')

    def test_unknown_actions_fields_and_model_scope_rejected(self):
        from core.models import Action
        from core.llm import Ollama
        with self.assertRaises(ValueError):Action(action='shell',value='del D:')
        with self.assertRaises(ValueError):Action(action='click',command='anything')
        with self.assertRaises(ValueError):Ollama(base_url='https://remote.example')
        with self.assertRaises(ValueError):Ollama(model='qwen:cloud')

    def test_exclusive_process_lock(self):
        with ProcessLock(self.store.folder):
            with self.assertRaises(RuntimeError):
                with ProcessLock(self.store.folder):pass

    def test_submit_is_durable_before_response_and_deduplicates(self):
        import time
        task=self.task();runner=Runner(self.store,None)
        run=runner.submit(task['id'],'submitted-request-id')
        with self.store.db() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM runs WHERE id=?',(run['id'],)).fetchone())
        self.assertEqual(runner.submit(task['id'],'submitted-request-id')['id'],run['id'])
        deadline=time.monotonic()+5
        while runner.busy.locked() and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(runner.busy.locked())

    def test_interrupted_effect_requires_explicit_resolution(self):
        file=self.files/'a.tmp';file.write_text('keep until failure')
        def uncertain_recycle(value):
            Path(value).rename(self.root/'uncertain.tmp')
            raise OSError('Lost final receipt')
        task=self.task();runner=Runner(self.store,None,recycle=uncertain_recycle)
        result=runner.run(task['id'])
        self.assertEqual(result['status'],'NEEDS_REVIEW')
        self.assertEqual(runner.run(task['id'])['status'],'HALTED')
        self.store.reconcile(result['id'],'completed')
        self.assertEqual(runner.run(task['id'])['status'],'VERIFIED')


if __name__=='__main__':unittest.main()
