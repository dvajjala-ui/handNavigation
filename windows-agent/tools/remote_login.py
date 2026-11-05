"""Temporary loopback-only remote desktop for one manual sign-in on an allowed source."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent)]
from core.runtime import ProcessLock
from core.sources import SOURCES, login_page_url
from core.storage import Store
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True)
    parser.add_argument('--url',default='',help='An exact public page of the chosen source; defaults to its sign-in page')
    parser.add_argument('--source',default='pinterest',choices=sorted(SOURCES))
    parser.add_argument('--seconds',type=int,default=1200,choices=range(60,1801))
    args=parser.parse_args()
    if sys.platform!='linux' or os.environ.get('HANDNAVIGATE_REMOTE_RUNNER')!='1':
        parser.error('Run this manual-login helper only on the chosen Linux VM.')
    if not args.url:
        args.url=('https://www.reddit.com/login/' if args.source=='reddit'
                  else 'https://www.pinterest.com/lonelyplanet/mountain-travel-best-places-to-visit/')
    try:login_page_url(args.source,args.url)
    except ValueError as error:parser.error(str(error))
    store=Store(args.data);stopped=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stopped.set())
    signal.signal(signal.SIGINT,lambda *_:stopped.set())
    # Do not replace an existing service on either loopback port.
    for port in (5901,6080):
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    processes=[]
    with ProcessLock(store.folder):
        try:
            processes.append(subprocess.Popen(['Xvfb',':97','-screen','0','1280x900x24','-nolisten','tcp']))
            deadline=time.monotonic()+10
            while not Path('/tmp/.X11-unix/X97').exists():
                if processes[0].poll() is not None or time.monotonic()>deadline:raise RuntimeError('Remote display did not start.')
                time.sleep(.1)
            os.environ['DISPLAY']=':97'
            processes.append(subprocess.Popen(['x11vnc','-display',':97','-listen','127.0.0.1','-localhost','-nopw','-forever','-shared','-rfbport','5901']))
            processes.append(subprocess.Popen(['websockify','--web=/usr/share/novnc','127.0.0.1:6080','127.0.0.1:5901']))
            with sync_playwright() as p:
                browser=p.chromium.launch_persistent_context(str(store.folder/'browser-profile'),headless=False,
                    args=['--disable-dev-shm-usage'],viewport={'width':1200,'height':800})
                try:
                    page=browser.pages[0] if browser.pages else browser.new_page()
                    page.goto(args.url,wait_until='domcontentloaded',timeout=60000)
                    print('Manual '+args.source+' login ready through SSH tunnel at http://127.0.0.1:6080/vnc.html. No password is logged.',flush=True)
                    deadline=time.monotonic()+args.seconds
                    while browser.pages and not stopped.is_set() and time.monotonic()<deadline:
                        try:page.wait_for_timeout(500)
                        except Exception:break
                finally:browser.close()
        finally:
            for process in reversed(processes):
                if process.poll() is None:process.terminate()
            for process in processes:
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':main()
