"""Run explicitly after Build.ps1; exercises the real executable and owned sites."""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent))
import test_browser


@unittest.skipUnless(os.environ.get('HANDNAVIGATE_TEST_PACKAGE')=='1','Run explicitly with HANDNAVIGATE_TEST_PACKAGE=1 after building')
class PackagedTests(unittest.TestCase):
    def test_exact_executable_ui_and_verified_image_transfer(self):
        executable=ROOT/'dist'/'HandNavigateAgent'/'HandNavigateAgent.exe'
        self.assertTrue(executable.is_file(),'Build the executable first')
        fixture=test_browser.BrowserTests();fixture.setUp()
        try:
            with tempfile.TemporaryDirectory() as folder:
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                base='http://127.0.0.1:'+str(port)
                log=Path(folder)/'console.txt'
                with log.open('w') as output:
                    process=subprocess.Popen([str(executable),'--data',str(Path(folder)/'data'),'--headless','serve','--port',str(port)],stdout=output,stderr=output,env={**os.environ,'HANDNAVIGATE_DEBUG':'1'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                token=None
                def request(route,body=None):
                    headers={'X-Agent-Token':token or ''}
                    if body is not None:headers.update({'Content-Type':'application/json','Origin':base})
                    with urlopen(Request(base+route,data=json.dumps(body).encode() if body is not None else None,headers=headers),timeout=5) as response:return json.load(response)
                try:
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        if process.poll() is not None:self.fail(log.read_text())
                        try:
                            with urlopen(base,timeout=1) as response:html=response.read().decode()
                            token=re.search(r'name="agent-token" content="([^"]+)"',html).group(1);break
                        except OSError:time.sleep(.1)
                    self.assertIsNotNone(token,log.read_text())
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        ui_browser=p.chromium.launch(headless=True,channel='chrome')
                        try:
                            page=ui_browser.new_page(viewport={'width':1300,'height':1000})
                            page.goto(base);page.locator('#status').filter(has_text='Runner ready').wait_for()
                            page.locator('#origins').fill(fixture.origin)
                            page.locator('#uploads').check();page.locator('#save-setup').click()
                            page.locator('#message').filter(has_text='Setup saved').wait_for()
                            self.assertEqual(request('/api/state')['permissions']['browser_origins'],[fixture.origin])
                            evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
                            page.screenshot(path=str(evidence/'packaged-ui.png'),full_page=True)
                        finally:ui_browser.close()
                    with urlopen(base+'/app.js') as response:self.assertIn(b"api('plan'",response.read())
                    task=request('/api/save',{'plan':{'name':'Packaged transfer','instruction':'Transfer two owned images','kind':'images',
                        'start_url':fixture.origin+'/source','upload_url':fixture.origin+'/upload','gallery_url':fixture.origin+'/gallery',
                        'account_marker':'owned account','submit_name':'Send','max_items':2}})
                    started=request('/api/run',{'id':task['id'],'request_id':'packaged-transfer-test'})
                    self.assertTrue(started['id'])
                    result=None;deadline=time.monotonic()+60
                    while time.monotonic()<deadline:
                        state=request('/api/state')
                        result=next((r for r in state['runs'] if r['id']==started['id']),None)
                        if result and result['status']!='RUNNING':break
                        time.sleep(.2)
                    self.assertIsNotNone(result);self.assertEqual(result['status'],'VERIFIED',str(result)+'\n'+log.read_text())
                    self.assertEqual(len(fixture.uploads),2)
                    repeated=request('/api/run',{'id':task['id'],'request_id':'packaged-transfer-test'})
                    self.assertEqual(repeated['id'],started['id']);self.assertEqual(len(fixture.uploads),2)
                    request('/api/shutdown',{});process.wait(timeout=15)
                    self.assertEqual(process.returncode,0,log.read_text())
                finally:
                    if process.poll() is None:process.terminate();process.wait(timeout=15)
        finally:fixture.doCleanups()
