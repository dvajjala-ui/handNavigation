from __future__ import annotations
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from playwright.sync_api import sync_playwright
from handnavigate.transfer.files import image_metadata, read_url
from handnavigate.live.contracts import Scope
from .models import origin

LIMITS={'max_bytes':25*1024*1024,'max_pixels':40_000_000,'min_width':128,'min_height':128}
DESCRIBE=r'''el => {
 const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
 if(!rect.width||!rect.height||style.visibility==='hidden'||style.display==='none')return null;
 const clean=s=>String(s||'').replace(/\s+/g,' ').trim().slice(0,500);
 const sensitive=/password|secret|token|api.?key|credential|one.?time|cc-number|cc-csc|cvv/i.test([el.type,el.name,el.id,el.autocomplete,el.getAttribute('aria-label')].join(' '))||!!el.closest('[data-private],[data-sensitive]');
 if(sensitive)return null;
 const record=el.closest('article,[data-record],[data-id],[data-item-id],tr,form');
 const data={tag:el.tagName,type:el.type,name:clean(el.getAttribute('aria-label')||Array.from(el.labels||[]).map(l=>l.innerText).join(' ')||el.innerText||el.title||el.placeholder),href:el.href||'',disabled:el.disabled||el.getAttribute('aria-disabled')==='true',attrs:Array.from(el.attributes).filter(a=>a.name!=='style').map(a=>[a.name,a.value]),record:record?clean(record.innerText)+'|'+record.outerHTML.slice(0,3000):''};
 return {...data,fingerprint:JSON.stringify(data)};
}'''


class Browser:
    def __init__(self,folder,policy,cancel,headless=False,channel='chrome'):
        self.folder=Path(folder);self.policy=policy;self.cancel=cancel
        self.headless=headless;self.channel=channel;self.changed=False;self.refs={};self.error=None;self.blocked_requests=[]
        self.deadline=time.monotonic()+600

    def __enter__(self):
        self.p=sync_playwright().start()
        try:
            self.context=self.p.chromium.launch_persistent_context(str(self.folder/'browser-profile'),
                headless=self.headless,channel=self.channel or None,service_workers='block',accept_downloads=False)
            self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
            self.context.set_default_timeout(12000)
            self.context.route('**/*',self.initial_guard)
            self.context.route_web_socket('**/*',self.deny_socket)
            self.context.on('page',self.popup)
            self.page.on('dialog',lambda dialog:dialog.dismiss())
            # Request-stage CDP interception validates EVERY redirect hop.
            self.cdp=self.context.new_cdp_session(self.page)
            self.main_frame_id=self.cdp.send('Page.getFrameTree')['frameTree']['frame']['id']
            self.cdp.on('Fetch.requestPaused',self.guard)
            self.cdp.send('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Request'}]})
            self.page.on('download',lambda download:download.cancel())
            return self
        except BaseException:
            if hasattr(self,'context'):
                self.context.close()
            self.p.stop();raise

    def __exit__(self,*_):
        try:self.context.close()
        finally:self.p.stop()

    def popup(self,page):
        self.error='A popup requires manual sign-in or review.'
        page.close()

    def initial_guard(self,route):
        try:
            self.policy.url(route.request.url,images=True)
            if route.request.is_navigation_request() and route.request.frame!=self.page.main_frame:
                raise PermissionError('Only the main task frame may navigate.')
            route.continue_()
        except Exception:
            route.abort('blockedbyclient')

    def deny_socket(self,ws):
        # An intercepted route never reaches a server unless connect_to_server()
        # is explicitly called. Sink messages locally and stop the task. Calling
        # close() inside this sync route callback can deadlock older drivers.
        self.error='WebSockets are disabled for this task; no server connection was made.'
        ws.on_message(lambda _message:None)

    def guard(self,event):
        try:
            u=urlsplit(event['request']['url'])
            if u.scheme in ('http','https'):
                self.policy.url(event['request']['url'],images=True)
            elif u.scheme not in ('data','blob','about','chrome-error'):
                raise PermissionError('Unsupported request scheme.')
            self.cdp.send('Fetch.continueRequest',{'requestId':event['requestId']})
        except Exception:
            is_main=event.get('frameId')==self.main_frame_id
            if len(self.blocked_requests)<100:
                self.blocked_requests.append({'url':event['request']['url'].split('?')[0],
                    'resource_type':event.get('resourceType'),'main_frame':is_main})
            if event.get('resourceType')=='Document' and is_main:
                self.error='Navigation left saved website permissions: '+event['request']['url'].split('?')[0]
            try:self.cdp.send('Fetch.failRequest',{'requestId':event['requestId'],'errorReason':'BlockedByClient'})
            except Exception:pass

    def check(self):
        if self.cancel.is_set():raise InterruptedError('Task stopped.')
        if time.monotonic()>self.deadline:raise TimeoutError('Browser task reached its 10-minute limit.')
        if self.error:raise RuntimeError(self.error)

    def navigate(self,url):
        self.check();self.policy.url(url)
        self.page.goto(url,wait_until='domcontentloaded',timeout=30000)
        self.page.wait_for_timeout(400);self.check();self.policy.url(self.page.url)

    def account(self,marker):
        if not marker or marker not in self.page.locator('body').inner_text(timeout=10000):
            raise RuntimeError('Expected account or owned-page marker is absent. Sign in or review the task.')

    def observe(self):
        self.check();self.refs={};controls=[]
        for element in self.page.query_selector_all('button,a[href],input,textarea,select,[role=button]')[:250]:
            info=element.evaluate(DESCRIBE)
            if not info:continue
            ref='e'+str(len(controls)+1)
            self.refs[ref]=(element,info)
            controls.append({'ref':ref,**{k:info[k] for k in ('tag','type','name','href','disabled') if k in info}})
        text=self.page.locator('body').inner_text()[:10000]
        return {'url':self.page.url,'title':self.page.title(),'text':text,'controls':controls}

    def perform(self,action,marker):
        self.check()
        if action.action=='navigate':self.navigate(action.url);return
        if action.action=='scroll':self.page.mouse.wheel(0,700);self.page.wait_for_timeout(300);return
        if action.action=='wait':self.page.wait_for_timeout(1000);return
        if action.action in ('observe','finish'):return
        self.account(marker)
        if action.ref not in self.refs:raise ValueError('Model selected an unknown or stale control reference.')
        element,before=self.refs[action.ref]
        current=element.evaluate(DESCRIBE)
        if not current or current['fingerprint']!=before['fingerprint']:
            raise RuntimeError('Control or enclosing business record changed before action.')
        if current['disabled']:raise RuntimeError('Control is disabled.')
        if action.action=='fill' and current.get('type') not in ('text','search','email','url','number','tel','') and current['tag']!='TEXTAREA':
            raise RuntimeError('This field requires manual interaction.')
        # Record uncertainty before any browser action that may have an effect.
        self.changed=True
        if action.action=='click':element.click(timeout=10000)
        elif action.action=='fill':element.fill(action.value,timeout=10000)
        self.refs={};self.page.wait_for_timeout(300);self.check()

    def candidates(self,selector,ranked=False):
        """One entry per displayed picture. Plain: the URL as displayed. ranked=True: that picture's URLs best first
        (largest srcset rendition, e.g. Pinterest's originals/736x instead of the 236x grid preview), still one
        entry per picture so srcset variants never count as extra images."""
        return self.page.locator(selector).evaluate_all(r'''(els, ranked) => els.slice(0,300).flatMap(e=>{
          const i=e.tagName==='IMG'?e:e.querySelector('img');if(!i)return [];
          if(!i.checkVisibility()||i.closest('[data-test-id="gated-pin-image"],[hidden],[aria-hidden="true"]'))return [];
          const a=i.closest('a[href]');const linked=a&&/\.(png|jpe?g|webp)(\?|$)/i.test(a.href)?[a.href]:[];
          if(!ranked){
            const urls=[...linked,i.currentSrc,i.src,...(i.srcset||'').split(',').map(s=>s.trim().split(/\s+/)[0])];
            // One displayed image contributes one URL; srcset variants must not
            // count as multiple pictures toward the requested collection count.
            return urls.filter(u=>/^https?:/.test(u)).slice(0,1);
          }
          const sized=(i.srcset||'').split(',').map(s=>s.trim().split(/\s+/)).filter(p=>p[0]).map(p=>{
            let u='';try{u=new URL(p[0],location.href).href}catch(_){}
            return {u,v:parseFloat(p[1]||'0')||0};}).filter(x=>x.u).sort((x,y)=>y.v-x.v).map(x=>x.u);
          const urls=[...new Set([...linked,...sized,i.currentSrc,i.src].filter(u=>/^https?:/.test(u)))].slice(0,4);
          return urls.length?[urls]:[];})''',ranked)

    def read_image(self,url):
        self.check();self.policy.url(url,images=True)
        scope=Scope(tuple(sorted(set(self.policy.permissions.browser_origins+self.policy.permissions.image_origins))),max_actions=60)
        data=read_url(self.context,scope,url,LIMITS['max_bytes'],time.monotonic()+30)
        return data,image_metadata(data,LIMITS)

    def collect(self,plan,folder,known,record):
        self.navigate(plan.start_url)
        items=[];seen=set();seen_hashes=set(known)
        folder.mkdir(parents=True,exist_ok=True)
        for _ in range(10):
            self.check()
            for urls in self.candidates(plan.image_selector,ranked=True):
                if any(u in seen for u in urls):continue
                seen.update(urls)
                if len(seen)>500:break
                data=meta=url=None
                for option in urls:
                    # Largest rendition first; fall back to the displayed one if it can't be read.
                    # check() keeps Stop and the time limit effective between attempts.
                    self.check()
                    try:
                        data,meta=self.read_image(option);url=option;break
                    except (InterruptedError,TimeoutError):raise
                    except Exception:
                        if option is urls[-1]:raise
                if meta is None:continue
                if meta['sha256'] in seen_hashes:continue
                seen_hashes.add(meta['sha256'])
                file=folder/(meta['sha256']+meta['extension'])
                with file.open('xb') as output:output.write(data)
                item={**meta,'file':str(file),'source':url}
                items.append(item);record(item)
                if len(items)>=plan.max_items:return items
            if len(seen)>500:break
            self.page.mouse.wheel(0,800);self.page.wait_for_timeout(500)
        return items

    def gallery(self,plan,hashes):
        self.navigate(plan.gallery_url);self.account(plan.account_marker)
        found=set()
        for url in self.candidates(plan.image_selector)[:300]:
            self.check()
            _,meta=self.read_image(url)
            if meta['sha256'] in hashes:found.add(meta['sha256'])
        return found

    def upload(self,plan,items,effect):
        expected={i['sha256'] for i in items}
        present=self.gallery(plan,expected)
        for item in items:
            self.check();key='upload:'+item['sha256']
            prior=effect(key)
            if item['sha256'] in present:
                effect(key,'VERIFIED',item);continue
            if prior and prior['state']=='STARTED':
                raise RuntimeError('Previous upload is uncertain and absent from the checked gallery. Review before retry.')
            self.navigate(plan.upload_url);self.account(plan.account_marker)
            file=Path(item['file']);data=file.read_bytes()
            if hashlib.sha256(data).hexdigest()!=item['sha256']:raise RuntimeError('Downloaded file changed before upload.')
            control=self.page.locator(plan.file_selector)
            if control.count()!=1:raise RuntimeError('Expected one exact upload input.')
            effect(key,'STARTED',item);self.changed=True
            control.set_input_files(str(file))
            if plan.submit_name:self.page.get_by_role('button',name=plan.submit_name,exact=True).click()
            # Wait for the original request; never repeat the submission.
            try:self.page.wait_for_load_state('networkidle',timeout=45000)
            except Exception:raise RuntimeError('Upload did not settle; review before retry.')
            found=set()
            for _ in range(4):
                found=self.gallery(plan,expected)
                if item['sha256'] in found:break
                self.page.wait_for_timeout(1000)
            if item['sha256'] not in found:raise RuntimeError('Persisted original could not be verified. Upload was not resubmitted.')
            present|=found;effect(key,'VERIFIED',item)
        return len(present & expected)

    def instagram(self,plan,effect):
        u=urlsplit(plan.start_url)
        username=u.path.strip('/')
        if origin(plan.start_url)!='https://www.instagram.com' or not re.fullmatch(r'[A-Za-z0-9._]{1,30}',username) or plan.account_marker!=username:
            raise ValueError('Use your exact Instagram profile URL and matching username.')
        self.navigate(plan.start_url)
        self.account(username)
        def signed_in_profile():
            profile=self.page.locator(f'a[href="/{username}/"]').filter(has=self.page.get_by_text('Profile',exact=True))
            if profile.count()!=1:
                raise RuntimeError('The signed-in navigation Profile link does not identify the configured account. Review login or site markup.')
        signed_in_profile()
        links=[]
        for _ in range(5):
            links=list(dict.fromkeys(links+self.page.locator('a[href^="/p/"],a[href^="/reel/"]').evaluate_all('els=>els.map(e=>e.href)')))
            if len(links)>=plan.max_items:break
            self.page.mouse.wheel(0,900);self.page.wait_for_timeout(700)
        verified=0
        for url in links[:plan.max_items]:
            self.check()
            if origin(url)!='https://www.instagram.com':raise RuntimeError('Post origin changed.')
            self.navigate(url)
            signed_in_profile()
            articles=self.page.locator('article')
            if articles.count()!=1:raise RuntimeError('Expected one unambiguous post article.')
            article=articles.first
            if not article.locator(f'a[href="/{username}/"]').count():raise RuntimeError('Post author does not match the configured own profile.')
            unlike=article.locator('button').filter(has=self.page.locator('svg[aria-label="Unlike"]'))
            if unlike.count()==1:
                effect('like:'+url,'VERIFIED',{'post':url});verified+=1;continue
            prior=effect('like:'+url)
            if prior and prior['state']=='STARTED':raise RuntimeError('An earlier like is uncertain. Review the post instead of toggling again.')
            like=article.locator('button').filter(has=self.page.locator('svg[aria-label="Like"]'))
            if like.count()!=1:raise RuntimeError('Expected one English Like control. Login, localization or markup needs attention.')
            effect('like:'+url,'STARTED',{'post':url});self.changed=True;like.click()
            unlike.wait_for(state='visible',timeout=10000)
            effect('like:'+url,'VERIFIED',{'post':url});verified+=1
        if not links:raise RuntimeError('No own-profile posts found. Check login, profile and site markup.')
        return {'verified_likes':verified,'scanned_posts':min(len(links),plan.max_items),'verification':'Current post author and visible Unlike state'}
