from __future__ import annotations
import fnmatch
import hashlib
import json
import os
import stat
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from send2trash import send2trash
from .browser import Browser
from .models import Permissions
from .policy import Policy, checked_path


class ProcessLock:
    def __init__(self,folder):
        self.file=Path(folder)/'runner.lock';self.stream=None

    def __enter__(self):
        self.file.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.file.open('a+b');self.stream.seek(0)
        if self.file.stat().st_size==0:self.stream.write(b'0');self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stream.close();raise RuntimeError('Another runner owns this data folder.') from None
        return self

    def __exit__(self,*_):
        self.stream.close()  # OS releases lock on close or process exit; no stale PID file.


class Runner:
    def __init__(self,store,llm,headless=False,channel='chrome',recycle=send2trash):
        self.store=store;self.llm=llm;self.headless=headless;self.channel=channel;self.recycle=recycle
        self.cancel=threading.Event();self.busy=threading.Lock();self.active=None

    def policy(self):
        return Policy(Permissions.model_validate(self.store.setting('permissions',{})))

    def check(self):
        if self.cancel.is_set():raise InterruptedError('Task stopped.')
        if time.monotonic()>self.deadline:raise TimeoutError('Task exceeded its 10-minute runtime limit.')

    def cleanup(self,task_id,plan,policy,run_id):
        root=policy.folder(plan.folder)
        if not root.is_dir():raise ValueError('Cleanup folder does not exist.')
        cutoff=time.time()-plan.older_than_days*86400
        candidates=[]
        for file in sorted(root.iterdir()):
            self.check()
            if not fnmatch.fnmatch(file.name,plan.pattern):continue
            file=checked_path(str(file));info=file.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_mtime>cutoff:continue
            if len(candidates)>=plan.max_items:raise ValueError('Cleanup exceeds the saved per-run file limit. Narrow the pattern or increase its explicit bound.')
            candidates.append((file,info))
        recycled=[]
        for file,previous in candidates:
            self.check();policy.folder(plan.folder);checked_path(str(file))
            fresh=file.stat(follow_symlinks=False)
            if (fresh.st_dev,fresh.st_ino,fresh.st_size,fresh.st_mtime_ns)!=(previous.st_dev,previous.st_ino,previous.st_size,previous.st_mtime_ns):
                raise RuntimeError('A cleanup target changed after the preview scan.')
            key='recycle:'+hashlib.sha256((str(file)+str(fresh.st_mtime_ns)+str(fresh.st_size)).encode()).hexdigest()
            prior=self.store.effect(task_id,key)
            if prior and prior['state']=='STARTED':raise RuntimeError('Prior file removal is uncertain; review it first.')
            # Persist the intent BEFORE the effect. No recursive deletion or arbitrary shell.
            self.store.effect(task_id,key,'STARTED',{'path':str(file)})
            self.changed=True;self.recycle(str(file))
            if file.exists():raise RuntimeError('File remains at its original location after recycle operation.')
            self.store.effect(task_id,key,'VERIFIED',{'path':str(file)})
            recycled.append(str(file));self.store.event(run_id,{'recycled':str(file)})
        return {'status':'VERIFIED','recycled':recycled,'matched':len(candidates),'recursive':False}

    def submit(self,task_id,request_id):
        # Claim durably before returning 202; concurrent callers cannot lose a run.
        with self.store.db() as db:
            previous=db.execute('SELECT * FROM runs WHERE request_id=?',(request_id,)).fetchone()
        if previous:
            if previous['task_id']!=task_id:raise ValueError('Request ID belongs to another task.')
            return dict(previous)
        if not self.busy.acquire(blocking=False):raise RuntimeError('Runner is busy.')
        try:
            self.policy().plan(self.store.task(task_id)['plan'])
            run,created=self.store.begin(task_id,request_id)
            if not created:self.busy.release();return run
            self.cancel.clear();self.active=run['id']
            threading.Thread(target=self.run,args=(task_id,request_id,run),daemon=True).start()
            return run
        except BaseException:
            self.busy.release();raise

    def run(self,task_id,request_id=None,_claimed=None):
        if _claimed is None and not self.busy.acquire(blocking=False):raise RuntimeError('Runner is busy.')
        browser=None;run=_claimed;self.changed=False
        if _claimed is None:self.cancel.clear()
        self.deadline=time.monotonic()+600
        try:
            task=self.store.task(task_id);plan=task['plan'];policy=self.policy();policy.plan(plan)
            if run is None:
                run,created=self.store.begin(task_id,request_id or uuid.uuid4().hex)
                if not created:return run
            self.active=run['id']
            if plan.kind=='cleanup':result=self.cleanup(task_id,plan,policy,run['id'])
            else:
                with Browser(self.store.folder,policy,self.cancel,self.headless,self.channel) as browser:
                    effect=lambda key,state=None,data=None:self.store.effect(task_id,key,state,data)
                    if plan.kind=='images':
                        # Reuse validated pending files after a source/transfer interruption.
                        with self.store.db() as db:
                            prior=[json.loads(r[0]) for r in db.execute("SELECT data FROM effects WHERE task_id=? AND item LIKE 'download:%'",(task_id,))]
                        pending=[i for i in prior if not effect('upload:'+i['sha256']) or effect('upload:'+i['sha256'])['state']!='VERIFIED'] if plan.upload_url else []
                        for item in pending:
                            if hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Pending image changed on disk.')
                        items=pending[:plan.max_items]
                        if len(items)<plan.max_items:
                            remaining=plan.model_copy(update={'max_items':plan.max_items-len(items)})
                            items+=browser.collect(remaining,self.store.folder/'downloads'/run['id'],{i['sha256'] for i in prior},
                                lambda item:effect('download:'+item['sha256'],'VERIFIED',item))
                        self.check()
                        count=browser.upload(plan,items,effect) if plan.upload_url and items else len(items)
                        result={'status':'VERIFIED' if count==plan.max_items else 'PARTIAL','downloaded':len(items),'confirmed':count,'items':items}
                    elif plan.kind=='instagram_like_own':
                        result={'status':'VERIFIED',**browser.instagram(plan,effect)}
                    else:
                        browser.navigate(plan.start_url);browser.account(plan.account_marker);history=[]
                        def output_matches():
                            if not plan.result_selector:return False
                            output=browser.page.locator(plan.result_selector)
                            return output.count()==1 and output.is_visible() and output.inner_text().strip()==plan.expected_result
                        already_matched=output_matches()
                        for _ in range(plan.max_steps):
                            self.check();observation=browser.observe()
                            action=self.llm.action(plan.goal,observation,history)
                            self.store.event(run['id'],{'action':action.model_dump(),'url':observation['url']})
                            if action.action=='finish':
                                verified=not already_matched and output_matches()
                                result={'status':'VERIFIED' if verified else 'OBSERVED','message':action.evidence,
                                    'verification':'Fresh exact text at the configured result element' if verified else 'Model report and page observation; no independent completion verifier passed'}
                                break
                            browser.perform(action,plan.account_marker);history.append(action.model_dump())
                        else:raise RuntimeError('Browser agent reached its action budget.')
            self.store.finish(run['id'],result['status'],result)
            return {'id':run['id'],**result}
        except Exception as error:
            if os.environ.get('HANDNAVIGATE_DEBUG')=='1':
                import traceback
                traceback.print_exc()
            uncertain=self.changed or browser is not None and browser.changed
            status='NEEDS_REVIEW' if uncertain else 'CANCELLED' if self.cancel.is_set() else 'HALTED'
            result={'status':status,'error':str(error)}
            if run:self.store.finish(run['id'],status,result)
            return {'id':run['id'] if run else None,**result}
        finally:
            self.active=None;self.busy.release()

    def tick(self,at=None):
        if self.busy.locked():return []
        at=at or datetime.now(timezone.utc);results=[]
        for task in self.store.due(at):
            # Keep the old due marker until execution is durably claimed. A retry
            # reuses its request ID; after downtime only one occurrence is run.
            result=self.run(task['id'],'daily:'+task['id']+':'+task['next_due'])
            self.store.advance(task['id'],at);results.append(result)
        return results
