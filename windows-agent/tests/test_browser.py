import io
import json
import sys
import tempfile
import threading
import unittest
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
from core.models import Permissions,Plan,Action
from core.policy import Policy
from core.browser import Browser
from core.runtime import Runner
from core.storage import Store


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.uploads=[];self.outside_hits=[]
        pictures=[]
        for color in ('red','green','blue'):
            output=io.BytesIO();Image.new('RGB',(180,180),color).save(output,format='PNG');pictures.append(output.getvalue())
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                if self.path.startswith('/image/'):
                    self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(pictures[int(self.path.rsplit('/',1)[-1])]);return
                if self.path.startswith('/stored/'):
                    self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(owner.uploads[int(self.path.rsplit('/',1)[-1])]);return
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location',owner.outside_origin);self.end_headers();return
                if self.path=='/source':body='<h1>owned account</h1>'+''.join(f'<img src="/image/{i}">' for i in range(3))
                elif self.path=='/gallery':body='<h1>owned account</h1>'+''.join(f'<img src="/stored/{i}">' for i in range(len(owner.uploads)))
                elif self.path=='/upload':body='<h1>owned account</h1><form method="POST" action="/upload" enctype="multipart/form-data"><input type="file" name="image"><button>Send</button></form>'
                else:body='<h1>owned account</h1><p id="result">pending</p><article data-record="A"><button id="save" onclick="document.querySelector(\'#result\').textContent=\'done\'">Save</button></article>'
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body.encode())
            def do_POST(self):
                data=self.rfile.read(int(self.headers['Content-Length']))
                msg=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+data)
                owner.uploads.extend(part.get_payload(decode=True) for part in msg.iter_parts() if part.get_filename())
                self.send_response(303);self.send_header('Location','/gallery');self.end_headers()
        class Outside(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                owner.outside_hits.append(self.path);self.send_response(200);self.end_headers()
        self.site=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.outside=ThreadingHTTPServer(('127.0.0.1',0),Outside)
        for server in (self.site,self.outside):
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            self.addCleanup(lambda s=server:(s.shutdown(),s.server_close()))
        self.origin='http://127.0.0.1:'+str(self.site.server_port);self.outside_origin='http://127.0.0.1:'+str(self.outside.server_port)
        self.permissions=Permissions(browser_origins=[self.origin],allow_upload=True,allow_browser_changes=True)

    def test_real_download_upload_readback_and_duplicate_free_rerun(self):
        store=Store(self.root/'state');store.set_setting('permissions',self.permissions.model_dump())
        plan=Plan(name='Owned transfer',instruction='Download and upload two owned images',kind='images',start_url=self.origin+'/source',
            upload_url=self.origin+'/upload',gallery_url=self.origin+'/gallery',account_marker='owned account',submit_name='Send',max_items=2)
        task=store.save(plan);runner=Runner(store,None,headless=True)
        result=runner.run(task['id'],'owned-transfer-1')
        self.assertEqual(result['status'],'VERIFIED',result);self.assertEqual(len(self.uploads),2)
        again=runner.run(task['id'],'owned-transfer-1')
        self.assertEqual(again['id'],result['id']);self.assertEqual(len(self.uploads),2)

    def test_changed_record_blocks_before_click(self):
        with Browser(self.root,Policy(self.permissions),threading.Event(),headless=True) as browser:
            browser.navigate(self.origin+'/task');snapshot=browser.observe()
            ref=next(c['ref'] for c in snapshot['controls'] if c['name']=='Save')
            browser.page.locator('article').evaluate('e=>e.dataset.record="B"')
            with self.assertRaisesRegex(RuntimeError,'record changed'):
                browser.perform(Action(action='click',ref=ref),'owned account')
            self.assertEqual(browser.page.locator('h1').inner_text(),'owned account')

    def test_image_candidates_exclude_hidden_and_gated_elements(self):
        with Browser(self.root,Policy(self.permissions),threading.Event(),headless=True) as browser:
            browser.navigate(self.origin+'/task')
            browser.page.set_content('<img src="/image/0"><img style="display:none" src="/image/1">'
                '<div data-test-id="gated-pin-image"><img src="/image/2"></div>')
            self.assertEqual(set(browser.candidates('img')),{self.origin+'/image/0'})

    def test_redirect_and_websocket_are_blocked_before_outside_request(self):
        with Browser(self.root,Policy(self.permissions),threading.Event(),headless=True) as browser:
            with self.assertRaises(Exception):browser.navigate(self.origin+'/redirect')
            self.assertFalse(self.outside_hits)
        with Browser(self.root,Policy(self.permissions),threading.Event(),headless=True) as browser:
            browser.navigate(self.origin+'/task')
            outcome=browser.page.evaluate('url=>new Promise(r=>{let w=new WebSocket(url);w.onopen=()=>r("opened");w.onerror=()=>r("blocked");setTimeout(()=>r("blocked"),1000)})',self.outside_origin.replace('http:','ws:'))
            self.assertIn(outcome,('opened','blocked'));self.assertFalse(self.outside_hits)
            with self.assertRaisesRegex(RuntimeError,'WebSockets are disabled'):browser.check()

    def test_model_finish_is_observed_and_does_not_enable_schedule(self):
        from core.models import Schedule
        class FakeModel:
            def action(self,*_):return Action(action='finish',evidence='I saw the old success text')
        store=Store(self.root/'state');store.set_setting('permissions',self.permissions.model_dump())
        task=store.save(Plan(name='Observe',instruction='Do something',kind='browser',start_url=self.origin+'/task',goal='Read owned page',account_marker='owned account',schedule=Schedule(time='09:00')))
        result=Runner(store,FakeModel(),headless=True).run(task['id'])
        self.assertEqual(result['status'],'OBSERVED',result)
        with self.assertRaises(ValueError):store.enable(task['id'],True)

    def test_blocked_optional_iframe_does_not_fail_the_main_page(self):
        with Browser(self.root,Policy(self.permissions),threading.Event(),headless=True) as browser:
            browser.navigate(self.origin+'/task')
            browser.page.evaluate('url=>{const f=document.createElement("iframe");f.src=url;document.body.append(f)}',self.outside_origin+'/optional-ad')
            browser.page.wait_for_timeout(500)
            browser.check()
            self.assertFalse(self.outside_hits)
            self.assertIsNone(browser.error)

    def test_fresh_scoped_result_verifies_and_old_result_does_not(self):
        class ClickingModel:
            count=0
            def action(self,goal,observation,history):
                if history:raise AssertionError('The verified result must stop the model before a repeated click')
                return Action(action='click',ref=next(c['ref'] for c in observation['controls'] if c['name']=='Save'))
        store=Store(self.root/'state');store.set_setting('permissions',self.permissions.model_dump())
        plan=Plan(name='Fresh output',instruction='Save owned item',kind='browser',start_url=self.origin+'/task',goal='Save',account_marker='owned account',result_selector='#result',expected_result='done',max_steps=1)
        task=store.save(plan);result=Runner(store,ClickingModel(),headless=True).run(task['id'])
        self.assertEqual(result['status'],'VERIFIED',result)
        class FinishModel:
            def action(self,*_):return Action(action='finish',evidence='Existing heading')
        task=store.save(plan.model_copy(update={'result_selector':'h1','expected_result':'owned account'}))
        result=Runner(store,FinishModel(),headless=True).run(task['id'])
        self.assertEqual(result['status'],'OBSERVED',result)

    def test_instagram_adapter_on_synthetic_markup_checks_account_author_and_state(self):
        # Synthetic HTML served by Playwright fulfillment. No Instagram request,
        # credentials or real account write occurs in this component test.
        permissions=Permissions(browser_origins=['https://www.instagram.com'],allow_instagram_likes=True)
        plan=Plan(name='Own posts',instruction='Like my own posts',kind='instagram_like_own',
                  start_url='https://www.instagram.com/me/',account_marker='me',max_items=1)
        receipts={};owner='me';signed_in='me';initial='Like';clicks=[]
        def effect(key,state=None,data=None):
            if state:receipts[key]={'state':state,'data':data}
            return receipts.get(key)
        with Browser(self.root,Policy(permissions),threading.Event(),headless=True) as browser:
            browser.page.expose_function('recordClick',lambda:clicks.append('clicked'))
            def fulfill(route):
                header=f'<h1>me</h1><nav><a href="/{signed_in}/">Profile</a></nav>'
                if route.request.url.endswith('/me/'):
                    html=header+'<a href="/p/owned-post/">My post</a>'
                else:
                    html=header+f'<article><a href="/{owner}/">{owner}</a><button onclick="recordClick();this.querySelector(\'svg\').setAttribute(\'aria-label\',\'Unlike\')"><svg aria-label="{initial}"></svg></button></article>'
                route.fulfill(status=200,content_type='text/html',body=html)
            browser.page.route('https://www.instagram.com/**',fulfill)
            result=browser.instagram(plan,effect)
            self.assertEqual(result['verified_likes'],1);self.assertEqual(len(clicks),1)
            initial='Unlike';browser.instagram(plan,effect);self.assertEqual(len(clicks),1)
            owner='other'
            with self.assertRaisesRegex(RuntimeError,'author'):browser.instagram(plan,effect)
            owner='me';signed_in='other'
            with self.assertRaisesRegex(RuntimeError,'signed-in'):browser.instagram(plan,effect)


if __name__=='__main__':unittest.main()
