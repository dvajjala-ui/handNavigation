import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent),str(ROOT/'tools')]
from collect_pinterest import verified_inventory, source_url
from handnavigate.transfer.files import image_metadata
from core.browser import LIMITS


class RemoteCollectionTests(unittest.TestCase):
    def test_public_page_override_stays_on_exact_pinterest_https_hosts(self):
        board='https://www.pinterest.com/lonelyplanet/mountain-travel-best-places-to-visit/'
        self.assertEqual(source_url('nature landscape',board),board)
        self.assertIn('q=nature+landscape',source_url('nature landscape'))
        for url in ('http://www.pinterest.com/board/','https://www.pinterest.com.evil.test/board/',
                    'https://user@www.pinterest.com/board/','https://www.pinterest.com:443/board/',
                    'https://www.pinterest.com/board/#hidden','https://i.pinimg.com/image.png'):
            with self.subTest(url=url),self.assertRaises(ValueError):source_url('nature',url)

    def test_saved_folder_requires_exact_count_and_decoded_matching_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);items=[]
            for index,color in enumerate(('red','blue')):
                out=io.BytesIO();Image.new('RGB',(160,180),color).save(out,format='PNG');data=out.getvalue()
                file=root/f'{index}.png';file.write_bytes(data)
                items.append({**image_metadata(data,LIMITS),'file':str(file)})
            self.assertTrue(verified_inventory(root,items,2))
            self.assertFalse(verified_inventory(root,items,20))
            (root/'1.png').write_bytes(b'not an image')
            with self.assertRaises(Exception):verified_inventory(root,items,2)

    def test_manifest_cannot_claim_files_outside_the_result_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'output';output.mkdir();external=root/'outside.png'
            with self.assertRaisesRegex(ValueError,'left the chosen'):
                verified_inventory(output,[{'file':str(external),'sha256':'f'*64}],1)

    def test_remote_acceptance_cli_refuses_accidental_local_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            env={k:v for k,v in os.environ.items() if k not in ('GITHUB_ACTIONS','HANDNAVIGATE_REMOTE_RUNNER')}
            result=subprocess.run([sys.executable,str(ROOT/'tools'/'collect_pinterest.py'),'--output',folder],
                                  capture_output=True,text=True,env=env,timeout=15)
            self.assertEqual(result.returncode,2)
            self.assertIn('runs remotely',result.stderr)
            self.assertFalse(any(Path(folder).iterdir()))

    def test_manual_login_helper_refuses_local_execution_without_creating_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            env={k:v for k,v in os.environ.items() if k!='HANDNAVIGATE_REMOTE_RUNNER'}
            result=subprocess.run([sys.executable,str(ROOT/'tools'/'remote_login.py'),'--data',folder],
                                  capture_output=True,text=True,env=env,timeout=15)
            self.assertEqual(result.returncode,2)
            self.assertIn('only on the chosen Linux VM',result.stderr)
            self.assertFalse(any(Path(folder).iterdir()))
