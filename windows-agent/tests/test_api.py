import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
from core.models import Plan
from core.llm import Ollama
from core.storage import Store
from core.runtime import Runner
from core.server import create_server


class ApiTests(unittest.TestCase):
    def test_local_session_permissions_persist_and_cross_origin_requests_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);llm=Ollama();server=create_server(store,Runner(store,llm),llm,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                with urlopen(base) as response:self.assertIn(b'HandNavigate Windows core',response.read())
                headers={'Content-Type':'application/json','Origin':base,'X-Agent-Token':server.session_token}
                payload=json.dumps({'model':'qwen3.5:4b','permissions':{'cleanup_roots':[folder]}}).encode()
                with urlopen(Request(base+'/api/setup',data=payload,headers=headers)) as response:self.assertEqual(response.status,200)
                self.assertEqual(Store(folder).setting('permissions')['cleanup_roots'],[folder])
                headers['Origin']='https://outside.example'
                with self.assertRaises(HTTPError) as failure:urlopen(Request(base+'/api/setup',data=payload,headers=headers))
                self.assertEqual(failure.exception.code,403)
                with self.assertRaises(HTTPError) as failure:urlopen(base+'/api/state')
                self.assertEqual(failure.exception.code,403)
            finally:server.shutdown();server.server_close()

    def test_ollama_adapter_uses_schema_and_validates_returned_plan(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        seen=[]
        class Model(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(request)
                plan=Plan(name='Needs detail',kind='cleanup',instruction='Original',missing_information=['Which folder?'])
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'message':{'content':plan.model_dump_json()},'eval_count':20}).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            from core.models import Permissions
            llm=Ollama(base_url='http://127.0.0.1:'+str(server.server_port))
            result=llm.plan('Delete files',Permissions())
            self.assertEqual(result.instruction,'Delete files');self.assertTrue(result.missing_information)
            self.assertIn('properties',seen[0]['format']);self.assertFalse(seen[0]['stream'])
            invalid={'name':'Bad model output','instruction':'Delete files','kind':'cleanup','folder':'','pattern':'/placeholder','missing_information':['folder']}
            llm.request=lambda *_:{'message':{'content':json.dumps(invalid)}}
            with self.assertRaises(ValueError):llm.plan('Delete files',Permissions())
            self.assertEqual(json.loads(llm.last_output),invalid,'Failure evidence must show this response, not the prior plan')
        finally:server.shutdown();server.server_close()
