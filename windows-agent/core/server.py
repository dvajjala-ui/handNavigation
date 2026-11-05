from __future__ import annotations
import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .models import Permissions, Plan


def create_server(store,runner,llm,port=47841,collections=None):
    token=secrets.token_urlsafe(32)
    drafts={};draft_lock=threading.Lock()
    ui=Path(__file__).parent.parent/'ui'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass

        def send(self,status,value,content_type='application/json'):
            data=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)

        def host_ok(self):
            return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)

        def do_GET(self):
            if not self.host_ok():return self.send(403,{'error':'Use the exact loopback address.'})
            parsed=urlsplit(self.path);route=parsed.path
            if route in ('/','/app.js','/style.css'):
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[route]
                data=(ui/name).read_bytes().replace(b'__SESSION_TOKEN__',token.encode())
                return self.send(200,data,{'index.html':'text/html; charset=utf-8','app.js':'text/javascript','style.css':'text/css'}[name])
            if not hmac.compare_digest(self.headers.get('X-Agent-Token',''),token):return self.send(403,{'error':'Session authentication required.'})
            if route=='/api/state':return self.send(200,{**store.snapshot(),'permissions':store.setting('permissions',{}),'model':store.setting('model',llm.model),'busy':runner.busy.locked(),'active':runner.active})
            if route=='/api/model':
                try:return self.send(200,llm.health())
                except Exception as error:return self.send(503,{'error':str(error)})
            if collections and route=='/api/collections':
                from urllib.parse import parse_qs
                args=parse_qs(parsed.query)
                try:return self.send(200,collections.db.list_library(args.get('source',[''])[0],args.get('topic',[''])[0]))
                except Exception as error:return self.send(503,{'error':str(error)[:300]})
            if collections and route.startswith('/api/collection-image/'):
                try:
                    data,mime=collections.db.image_bytes(route.rsplit('/',1)[-1])
                    return self.send(200,data,mime)
                except Exception as error:return self.send(404,{'error':str(error)[:300]})
            return self.send(404,{'error':'Not found.'})

        def do_POST(self):
            expected='http://127.0.0.1:'+str(self.server.server_port)
            if not self.host_ok() or self.headers.get('Origin')!=expected or not hmac.compare_digest(self.headers.get('X-Agent-Token',''),token):
                return self.send(403,{'error':'Use the local application session.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=64000:raise ValueError('Request must be 1–64000 bytes.')
                if self.headers.get('Content-Type')!='application/json':raise ValueError('Send application/json.')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('Send a JSON object.')
                route=urlsplit(self.path).path
                if route=='/api/setup':
                    if runner.busy.locked():raise ValueError('Stop the active task before changing permissions.')
                    permissions=Permissions.model_validate(body['permissions'])
                    # Validate roots on save as well as on every actual file operation.
                    from .policy import checked_path
                    for root in permissions.cleanup_roots:checked_path(root)
                    model=body.get('model',llm.model)
                    from .llm import Ollama
                    checked=Ollama(model)
                    store.set_setting('permissions',permissions.model_dump());store.set_setting('model',checked.model)
                    llm.model=checked.model
                    return self.send(200,{'saved':True})
                if route=='/api/plan':
                    instruction=body.get('instruction','')
                    if not isinstance(instruction,str) or not 1<=len(instruction)<=8000:raise ValueError('Enter an instruction of at most 8000 characters.')
                    plan=llm.plan(instruction,runner.policy().permissions)
                    with draft_lock:
                        if len(drafts)>=100:drafts.clear()
                        draft_id=secrets.token_hex(16);drafts[draft_id]=plan
                    return self.send(200,{'draft_id':draft_id,'plan':plan.model_dump(),'metrics':llm.last_metrics})
                if route=='/api/save':
                    # Edited JSON is deliberately user-authored. The model cannot call this API.
                    plan=Plan.model_validate(body['plan']);runner.policy().plan(plan)
                    task=store.save(plan)
                    return self.send(200,{'id':task['id'],'sha':task['sha']})
                if route=='/api/run':
                    task_id=body['id'];runner.policy().plan(store.task(task_id)['plan'])
                    request_id=body.get('request_id') or secrets.token_hex(16)
                    if not isinstance(request_id,str) or not 8<=len(request_id)<=200:raise ValueError('Invalid request ID.')
                    run=runner.submit(task_id,request_id)
                    return self.send(202,{'id':run['id'],'status':run['status'],'request_id':request_id})
                if route=='/api/stop':runner.cancel.set();return self.send(200,{'stopping':True})
                if route=='/api/shutdown':
                    self.send(202,{'stopping':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
                if route=='/api/schedule':store.enable(body['id'],body['enabled'] is True);return self.send(200,{'saved':True})
                if route=='/api/reconcile':
                    if runner.busy.locked():raise ValueError('Wait for the active task.')
                    store.reconcile(body['id'],body['decision']);return self.send(200,{'reviewed':True})
                if collections and route=='/api/collection-jobs':
                    return self.send(200,{'id':collections.db.create_job(body)})
                if collections and route=='/api/collection-job':
                    return self.send(200,collections.db.update_job(body['id'],body))
                if collections and route=='/api/collection-run':
                    return self.send(202,collections.run_async(body['id']))
                if collections and route=='/api/collection-schedule':
                    collections.db.set_enabled(body['id'],body['enabled'] is True)
                    return self.send(200,{'saved':True})
                return self.send(404,{'error':'Not found.'})
            except Exception as error:return self.send(409,{'error':str(error)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.session_token=token
    return server
