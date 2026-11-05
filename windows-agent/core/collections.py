"""Private Supabase image library and the VM's bounded collection schedule."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from handnavigate.transfer.files import image_metadata
from .browser import Browser, LIMITS
from .models import Permissions, Plan
from .policy import Policy
from .sources import SOURCES, source_config

BUCKET='handnavigate-images'
ROOT=Path(__file__).resolve().parents[1]
TOPIC=re.compile(r'^[a-z][a-z0-9_]{1,39}$')
TIME=re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_):return None


def config(path=None):
    """The requested plain .env, never bundled or returned to the browser."""
    values={}
    file=Path(path or ROOT/'.env')
    if file.exists():
        for line in file.read_text(encoding='utf-8-sig').splitlines():
            if line and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1);values[key.strip()]=value.strip()
    import os
    values.update({k:v for k,v in os.environ.items() if k.startswith('SUPABASE_') or k.startswith('REDDIT_')})
    required=('SUPABASE_URL','SUPABASE_SECRET_KEY','SUPABASE_DB_HOST','SUPABASE_DB_USER','SUPABASE_DB_PASSWORD','SUPABASE_DB_NAME')
    if any(not values.get(key) for key in required):
        raise RuntimeError('Supabase is not configured in windows-agent/.env.')
    u=urlsplit(values['SUPABASE_URL'])
    if u.scheme!='https' or u.netloc!='kyvowdxtwazxhsdjajpm.supabase.co' or u.path:
        raise ValueError('Supabase URL must be the configured exact project endpoint.')
    if not values['SUPABASE_SECRET_KEY'].startswith('sb_secret_'):
        raise ValueError('A server-only Supabase secret key is required for private Storage.')
    return values


class CollectionDB:
    def __init__(self,values=None):self.values=values or config()

    def connect(self):
        v=self.values
        return psycopg.connect(host=v['SUPABASE_DB_HOST'],port=int(v.get('SUPABASE_DB_PORT','5432')),
            user=v['SUPABASE_DB_USER'],password=v['SUPABASE_DB_PASSWORD'],dbname=v['SUPABASE_DB_NAME'],
            sslmode='require',connect_timeout=12,row_factory=dict_row)

    def migrate(self):
        for sql in sorted((ROOT/'migrations').glob('*.sql')):
            with self.connect() as db:
                db.execute(sql.read_text(encoding='utf-8'))
        self.ensure_bucket()

    def storage(self,method,path,data=None,content_type=None,allow=None):
        url=self.values['SUPABASE_URL']+'/storage/v1/'+path.lstrip('/')
        headers={'apikey':self.values['SUPABASE_SECRET_KEY'],'User-Agent':'HandNavigate-VM/1.0'}
        if content_type:headers['Content-Type']=content_type
        request=Request(url,data=data,headers=headers,method=method)
        try:
            with build_opener(NoRedirect).open(request,timeout=30) as response:
                payload=response.read(27*1024*1024)
                if len(payload)>26*1024*1024:raise ValueError('Storage response exceeds bound.')
                return response.status,payload
        except HTTPError as error:
            with error:
                body=error.read(500)
            if allow and error.code in allow:return error.code,body
            raise RuntimeError('Supabase Storage HTTP '+str(error.code)+': '+body.decode('utf-8','replace')[:220]) from None

    def ensure_bucket(self):
        status,body=self.storage('GET','bucket/'+BUCKET,allow={400,404})
        if status in (400,404) and b'NoSuchBucket' not in body:
            raise RuntimeError('Storage bucket lookup failed.')
        if status in (400,404):
            body={'name':BUCKET,'id':BUCKET,'public':False,'file_size_limit':26214400,
                  'allowed_mime_types':['image/jpeg','image/png','image/webp']}
            self.storage('POST','bucket',json.dumps(body).encode(),'application/json')
        # A preexisting public bucket is never silently reused.
        _,raw=self.storage('GET','bucket/'+BUCKET)
        if json.loads(raw).get('public') is not False:
            raise RuntimeError('The collection bucket must be private.')

    def upload_verified(self,source,topic,data,meta):
        path=f"{source}/{topic}/{meta['sha256']}{meta['extension']}"
        status,_=self.storage('POST','object/'+BUCKET+'/'+path,data,meta['mime'],allow={409})
        if status not in (200,201,409):raise RuntimeError('Storage upload was not accepted.')
        _,actual=self.storage('GET','object/authenticated/'+BUCKET+'/'+path)
        if hashlib.sha256(actual).hexdigest()!=meta['sha256']:
            raise RuntimeError('Storage read-back did not match the local image.')
        return path

    def store_image(self,run_id,source,topic,page_url,source_url,data,rendition='preview',post_id=None):
        if source not in SOURCES or not TOPIC.fullmatch(topic):raise ValueError('Invalid source/topic.')
        meta=image_metadata(data,LIMITS)
        with self.connect() as db:
            previous=db.execute('select id from public.collected_images where sha256=%s',(meta['sha256'],)).fetchone()
        if previous:return {'id':str(previous['id']),'duplicate':True,'sha256':meta['sha256']}
        path=self.upload_verified(source,topic,data,meta)
        with self.connect() as db:
            row=db.execute('''insert into public.collected_images
              (run_id,source,topic_key,source_page_url,source_image_url,source_post_id,storage_path,
               sha256,mime_type,width,height,byte_count,rendition)
              values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
              on conflict (sha256) do update set sha256=excluded.sha256 returning id''',
              (run_id,source,topic,page_url,source_url,post_id,path,meta['sha256'],meta['mime'],
               meta['width'],meta['height'],meta['bytes'],rendition)).fetchone()
        return {'id':str(row['id']),'duplicate':False,'sha256':meta['sha256']}

    def list_library(self,source='',topic=''):
        if source and source not in SOURCES:raise ValueError('Invalid source filter.')
        if topic and not TOPIC.fullmatch(topic):raise ValueError('Invalid topic filter.')
        with self.connect() as db:
            topics=db.execute('select key,label,pinterest_verified,reddit_verified,enabled from public.collection_topics order by label').fetchall()
            jobs=db.execute('''select id,name,source,topic_key,random_topic,image_count,daily_time::text as daily_time,
                timezone,enabled from public.collection_jobs order by created_at desc limit 30''').fetchall()
            images=db.execute('''select id,source,topic_key,source_page_url,sha256,mime_type,width,height,
                byte_count,rendition,rights_status,collected_at from public.collected_images
                where (%s='' or source=%s) and (%s='' or topic_key=%s)
                order by collected_at desc limit 100''',(source,source,topic,topic)).fetchall()
            counts=db.execute('select source,topic_key,count(*) as count from public.collected_images group by 1,2').fetchall()
            runs=db.execute('''select id,job_id,source,topic_key,requested,downloaded,stored,status,error,started_at
                from public.collection_runs order by started_at desc limit 10''').fetchall()
        def encode(row):
            return {k:v.isoformat() if isinstance(v,datetime) else str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()}
        return {'topics':[encode(x) for x in topics],'jobs':[encode(x) for x in jobs],
                'images':[encode(x) for x in images],'counts':[encode(x) for x in counts],
                'runs':[encode(x) for x in runs]}

    def image_bytes(self,image_id):
        image_id=uuid.UUID(image_id)
        with self.connect() as db:
            row=db.execute('select storage_path,sha256,mime_type from public.collected_images where id=%s',(image_id,)).fetchone()
        if not row:raise ValueError('Image not found.')
        _,data=self.storage('GET','object/authenticated/'+BUCKET+'/'+row['storage_path'])
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise RuntimeError('Stored image failed hash verification.')
        return data,row['mime_type']

    def mark_verified(self,topic_key,source_url,source='pinterest'):
        """A topic becomes collectable on a source only after a real run passed on that source's exact URL."""
        config=source_config(source)
        with self.connect() as db:
            row=db.execute('select '+config['url_column']+' as url from public.collection_topics where key=%s',
                           (topic_key,)).fetchone()
            if not row:raise ValueError('Unknown content topic.')
            if row['url']!=source_url:
                raise ValueError('The verified result came from a different URL than the '+config['label']+' topic source.')
            db.execute('update public.collection_topics set '+config['verified_column']+'=true where key=%s',(topic_key,))

    def _job_fields(self,body):
        """Shared validation for creating and editing a schedule; nothing reaches SQL unless it passes."""
        source=body.get('source');topic=body.get('topic_key') or None
        random_topic=body.get('random_topic') is True
        count=body.get('image_count');daily_time=body.get('daily_time');zone=body.get('timezone','Asia/Kolkata')
        name=body.get('name','')
        if source not in SOURCES or not isinstance(count,int) or not 1<=count<=20:
            raise ValueError('Choose '+' or '.join(sorted(SOURCES)) +' and 1–20 images.')
        if not isinstance(name,str) or not 1<=len(name)<=120 or not isinstance(daily_time,str) or not TIME.fullmatch(daily_time):
            raise ValueError('Enter a name and exact daily time (HH:MM).')
        try:ZoneInfo(zone)
        except Exception:raise ValueError('Choose a real time zone such as Asia/Kolkata.') from None
        if not random_topic and (not isinstance(topic,str) or not TOPIC.fullmatch(topic)):
            raise ValueError('Choose a content topic or random.')
        return {'name':name,'source':source,'topic':None if random_topic else topic,
                'random_topic':random_topic,'count':count,'daily_time':daily_time,'zone':zone}

    def _source_available(self,db,source,topic,random_topic):
        """True when at least one enabled topic is collectable on this source."""
        column=source_config(source)['verified_column']
        if random_topic:
            return db.execute('select 1 from public.collection_topics where enabled and '+column+' limit 1').fetchone()
        return db.execute('select 1 from public.collection_topics where key=%s and enabled and '+column,
                          (topic,)).fetchone()

    def create_job(self,body):
        fields=self._job_fields(body)
        with self.connect() as db:
            if not self._source_available(db,fields['source'],fields['topic'],fields['random_topic']):
                raise ValueError('No verified '+source_config(fields['source'])['label']
                                 +' source exists for that selection yet. Collect one batch on it first.')
            row=db.execute('''insert into public.collection_jobs
                (name,source,topic_key,random_topic,image_count,daily_time,timezone)
                values (%s,%s,%s,%s,%s,%s,%s) returning id''',
                (fields['name'],fields['source'],fields['topic'],fields['random_topic'],fields['count'],
                 fields['daily_time'],fields['zone'])).fetchone()
        return str(row['id'])

    def update_job(self,job_id,body):
        """Change what a proven job collects; enabling still requires its own verified run."""
        fields=self._job_fields(body)
        with self.connect() as db:
            job=db.execute('select id,enabled from public.collection_jobs where id=%s',(uuid.UUID(str(job_id)),)).fetchone()
            if not job:raise ValueError('Job not found.')
            if not self._source_available(db,fields['source'],fields['topic'],fields['random_topic']):
                raise ValueError('No verified '+source_config(fields['source'])['label']
                                 +' source exists for that selection yet. Collect one batch on it first.')
            db.execute('''update public.collection_jobs set name=%s,source=%s,topic_key=%s,random_topic=%s,
                image_count=%s,daily_time=%s,timezone=%s where id=%s''',
                (fields['name'],fields['source'],fields['topic'],fields['random_topic'],fields['count'],
                 fields['daily_time'],fields['zone'],job['id']))
        return {'id':str(job_id),**{'image_count':fields['count'],'daily_time':fields['daily_time'],
                'source':fields['source'],'topic_key':fields['topic'],'random_topic':fields['random_topic'],
                'name':fields['name'],'timezone':fields['zone']}}

    def set_enabled(self,job_id,enabled):
        with self.connect() as db:
            job=db.execute('select source,topic_key,random_topic from public.collection_jobs where id=%s',(uuid.UUID(job_id),)).fetchone()
            if not job:raise ValueError('Job not found.')
            if enabled:
                if not self._source_available(db,job['source'],job.get('topic_key'),bool(job.get('random_topic'))):
                    raise ValueError('No verified '+source_config(job['source'])['label']
                                     +' source exists for that selection yet. Collect one batch on it first.')
                passed=db.execute("select 1 from public.collection_runs where job_id=%s and status='VERIFIED' limit 1",(uuid.UUID(job_id),)).fetchone()
                if not passed:raise ValueError('Run this job successfully once before enabling daily collection.')
            db.execute('update public.collection_jobs set enabled=%s where id=%s',(bool(enabled),uuid.UUID(job_id)))

    def due_jobs(self,at=None):
        at=at or datetime.now(timezone.utc)
        with self.connect() as db:
            jobs=db.execute('select * from public.collection_jobs where enabled order by created_at').fetchall()
            due=[]
            for job in jobs:
                local=at.astimezone(ZoneInfo(job['timezone']))
                if local.time().replace(tzinfo=None)<job['daily_time']:continue
                if db.execute('select 1 from public.collection_runs where job_id=%s and scheduled_date=%s',
                              (job['id'],local.date())).fetchone():continue
                due.append((job,local.date()))
        return due

    def topic_for(self,job,day=None):
        column=source_config(job['source'])['verified_column']
        with self.connect() as db:
            if job['random_topic']:
                rows=db.execute('select * from public.collection_topics where enabled and '+column+' order by key').fetchall()
                if not rows:raise ValueError('No verified topics are available for random selection on that source.')
                # Stable within one occurrence, independent of process restarts.
                seed=f"{job['id']}:{day or datetime.now(timezone.utc).date()}"
                return random.Random(seed).choice(rows)
            row=db.execute('select * from public.collection_topics where key=%s and enabled',(job['topic_key'],)).fetchone()
            if not row:raise ValueError('The selected topic is unavailable.')
            if not row[column]:raise ValueError('That topic has no verified '+source_config(job['source'])['label']+' source yet.')
            return row

    def start_run(self,job,topic,scheduled_date=None):
        with self.connect() as db:
            row=db.execute('''insert into public.collection_runs
              (job_id,scheduled_date,source,topic_key,requested,status)
              values (%s,%s,%s,%s,%s,'RUNNING') on conflict (job_id,scheduled_date) do nothing returning id''',
              (job['id'],scheduled_date,job['source'],topic['key'],job['image_count'])).fetchone()
        return str(row['id']) if row else None

    def finish_run(self,run_id,status,downloaded,stored,error=None):
        with self.connect() as db:
            db.execute('''update public.collection_runs set status=%s,downloaded=%s,stored=%s,error=%s,
                finished_at=now() where id=%s''',(status,downloaded,stored,error,uuid.UUID(run_id)))
            if status!='VERIFIED':
                db.execute('update public.collection_jobs set enabled=false where id=(select job_id from public.collection_runs where id=%s)',(uuid.UUID(run_id),))

    def recover(self):
        with self.connect() as db:
            db.execute("update public.collection_jobs set enabled=false where id in (select job_id from public.collection_runs where status='RUNNING')")
            db.execute("update public.collection_runs set status='NEEDS_REVIEW',error='Worker restarted during collection.',finished_at=now() where status='RUNNING'")


class CollectionCoordinator:
    def __init__(self,db,runner,store,channel=''):
        self.db=db;self.runner=runner;self.store=store;self.channel=channel
        self.active=None

    def run_job(self,job_id,scheduled_date=None,preclaimed=False):
        if not preclaimed and not self.runner.busy.acquire(blocking=False):raise RuntimeError('Runner is busy.')
        run_id=None;downloaded=stored=0
        try:
            self.runner.cancel.clear()
            with self.db.connect() as conn:
                job=conn.execute('select * from public.collection_jobs where id=%s',(uuid.UUID(str(job_id)),)).fetchone()
            if not job:raise ValueError('Job not found.')
            config=source_config(job['source'])
            topic=self.db.topic_for(job,scheduled_date)
            if not topic[config['verified_column']]:
                raise RuntimeError('That topic has no signed-in '+config['label']+' acceptance run yet.')
            if os.environ.get('HANDNAVIGATE_REMOTE_RUNNER')!='1':
                raise RuntimeError(config['label']+' collection is restricted to the remote worker.')
            run_id=self.db.start_run(job,topic,scheduled_date)
            if not run_id:raise ValueError('This scheduled occurrence was already claimed.')
            self.active=run_id
            url=topic[config['url_column']]
            policy=Policy(Permissions(browser_origins=list(config['browser_origins']),
                                      image_origins=list(config['image_origins'])))
            plan=Plan(name=config['label']+' '+topic['label'],
                      instruction='Collect visible '+config['label']+' images',kind='images',
                      start_url=url,image_selector=config['image_selector'],max_items=job['image_count'])
            folder=self.store.folder/'collection-downloads'/run_id
            with self.db.connect() as conn:
                known={x['sha256'] for x in conn.execute('select sha256 from public.collected_images')}
            with Browser(self.store.folder,policy,self.runner.cancel,headless=True,channel=self.channel) as browser:
                items=browser.collect(plan,folder,known,lambda _item:None)
                if not items:
                    # Report a wall instead of pushing through it. No credential is entered,
                    # no challenge is answered, and no substitute source is used.
                    observed=browser.observe()['text'].lower()
                    walls=[marker for marker in config['wall_markers'] if marker in observed]
                    raise RuntimeError(config['label']+' returned no collectable image'
                                       +(' and shows a sign-in or network block: '+', '.join(walls) if walls else '.')
                                       +' Nothing was bypassed.')
            downloaded=len(items)
            for item in items:
                if self.runner.cancel.is_set():raise InterruptedError('Collection stopped.')
                result=self.db.store_image(run_id,job['source'],topic['key'],url,item['source'],Path(item['file']).read_bytes())
                if not result['duplicate']:stored+=1
            status='VERIFIED' if stored==job['image_count'] else 'PARTIAL'
            self.db.finish_run(run_id,status,downloaded,stored)
            return {'id':run_id,'status':status,'downloaded':downloaded,'stored':stored}
        except Exception as error:
            if run_id:self.db.finish_run(run_id,'HALTED',downloaded,stored,str(error)[:500])
            return {'id':run_id,'status':'HALTED','downloaded':downloaded,'stored':stored,'error':str(error)}
        finally:
            self.active=None;self.runner.busy.release()

    def run_async(self,job_id):
        if not self.runner.busy.acquire(blocking=False):raise RuntimeError('Runner is busy.')
        try:threading.Thread(target=self.run_job,args=(job_id,None,True),daemon=True).start()
        except BaseException:
            self.runner.busy.release();raise
        return {'started':True}

    def tick(self):
        if self.runner.busy.locked():return []
        return [self.run_job(job['id'],day) for job,day in self.db.due_jobs()]
