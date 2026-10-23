"""Live browser CLI. No localhost fixture, set_content, or simulated-provider fallback."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

from .contracts import (LiveError, Scope, approval, origin, require_approval, save_json,
                        validate_workflow)


def read_json(path: Path):
    if path.stat().st_size > 5_000_000:
        raise LiveError('JSON input exceeds the 5 MB import budget')
    return json.loads(path.read_text(encoding='utf-8'))


def common(parser, *, url=True):
    if url:
        parser.add_argument('--url', required=True)
        parser.add_argument('--allow-origin', action='append', default=[])
        parser.add_argument('--allow-method', action='append', default=[])
        parser.add_argument('--max-actions',type=int,default=30)
    parser.add_argument('--authorized-site',action='store_true',help='Acknowledge that you have permission for this task on this site')
    parser.add_argument('--headless',action='store_true',help='Use a nonvisible browser; interactive demonstrations need a visible browser')
    parser.add_argument('--profile',type=Path,help='Dedicated local browser profile; sensitive data, excluded from exports')
    parser.add_argument('--manual-login',action='store_true',help='Pause for manual sign-in before recording or sending data to AI')
    parser.add_argument('--out',type=Path)


def checks_args(parser):
    parser.add_argument('--expect-text',action='append',default=[],help='Exact visible completion text')
    parser.add_argument('--expect-url',action='append',default=[],help='Exact final URL')
    parser.add_argument('--checks',type=Path,help='JSON list of explicit completion checks')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='HandNavigate experimental live-browser core; no synthetic-site fallback')
    subs = p.add_subparsers(dest='command', required=True)
    for name in ('inspect','record','agent','doctor'):
        parser = subs.add_parser(name)
        common(parser)
        if name in {'record','agent'}:
            checks_args(parser)
        if name == 'agent':
            parser.add_argument('--goal',required=True)
            parser.add_argument('--model',required=True,help='Current Groq tool-capable model ID')
            parser.add_argument('--allow-ai',action='store_true',help='Consent to send bounded page content to Groq and incur API usage')
            parser.add_argument('--send-screenshots',action='store_true',help='Also send screenshots; requires a vision-capable model')
    imp = subs.add_parser('import-trustudio')
    imp.add_argument('capture',type=Path)
    imp.add_argument('--flow')
    imp.add_argument('--out',type=Path,required=True)
    app = subs.add_parser('approve')
    app.add_argument('workflow',type=Path)
    app.add_argument('--inputs',type=Path)
    app.add_argument('--out',type=Path)
    rep = subs.add_parser('replay')
    rep.add_argument('workflow',type=Path)
    rep.add_argument('--inputs',type=Path)
    rep.add_argument('--approval',type=Path,required=True)
    common(rep,url=False)
    args = p.parse_args(argv)
    output = getattr(args,'out',None)
    try:
        if args.command == 'import-trustudio':
            from .workflows import import_trustudio
            workflow,report = import_trustudio(read_json(args.capture),args.flow)
            args.out.mkdir(parents=True,exist_ok=True)
            save_json(args.out/'workflow.draft.json',workflow)
            save_json(args.out/'import-report.json',report)
            print(json.dumps(report,indent=2))
            return 0 if not report['blockers'] else 2
        if args.command == 'approve':
            workflow = read_json(args.workflow)
            inputs = read_json(args.inputs) if args.inputs else {}
            if workflow.get('provenance',{}).get('blockers',0):
                raise LiveError('Draft has unresolved blockers; inspect its import/recording report')
            receipt = approval(workflow,inputs)
            print(json.dumps({'workflow':workflow,'inputs':inputs},indent=2))
            if input('Review every action and check above. Type APPROVE to authorize this exact replay: ') != 'APPROVE':
                raise LiveError('Not approved')
            path = args.out or args.workflow.with_suffix('.approval.json')
            save_json(path,receipt)
            print(path)
            return 0
        if not args.authorized_site:
            raise LiveError('Pass --authorized-site only for a site/task you are permitted to automate')
        if args.command == 'replay':
            workflow = read_json(args.workflow)
            inputs = read_json(args.inputs) if args.inputs else {}
            receipt = read_json(args.approval)
            scope = require_approval(workflow,inputs,receipt)
            start_url = workflow['start_url']
        else:
            scope = Scope(tuple(dict.fromkeys([origin(args.url)]+args.allow_origin)),
                          tuple(dict.fromkeys(['GET','HEAD','OPTIONS']+[m.upper() for m in args.allow_method])),args.max_actions)
            start_url = args.url
            scope.check(start_url)
        checks = []
        if args.command in {'record','agent'}:
            checks = read_json(args.checks) if args.checks else []
            checks += [{'kind':'text_visible','expected':t} for t in args.expect_text]
            checks += [{'kind':'url_equals','expected':u} for u in args.expect_url]
            validation = {'schema':'handnavigate.live.v1','scope':scope.as_dict(),'start_url':start_url,
                          'steps':[{'op':'wait','amount':0}],'checks':checks}
            validate_workflow(validation,require_checks=False)
        if args.command == 'record' and args.headless:
            raise LiveError('Human recording requires a visible browser')
        if args.manual_login and args.headless:
            raise LiveError('Manual sign-in requires a visible browser')
        provider = None
        if args.command == 'agent':
            from .agent import GroqProvider
            provider = GroqProvider(args.model,consent=args.allow_ai)
        if args.profile:
            marker = args.profile / '.handnavigate-profile.json'
            if args.profile.exists() and any(args.profile.iterdir()) and not marker.exists():
                raise LiveError('Use a new dedicated profile directory, not your regular browser profile')
            if marker.exists() and read_json(marker).get('origins') != list(scope.origins):
                raise LiveError('Profile scope differs; use a separate dedicated profile')
            save_json(marker,{'origins':list(scope.origins),'sensitive':True})
        if output is None:
            output = Path('live-runs') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
        from .browser import open_driver
        with open_driver(scope,output,headless=args.headless or args.command == 'doctor',profile=args.profile) as driver:
            driver.goto(start_url)
            if args.manual_login:
                from .recording import wait_for_operator
                wait_for_operator(driver.page,'Sign in manually. Press ENTER here when ready to continue: ')
                driver.check_page()
            if args.command in {'inspect','doctor'}:
                observation = driver.observe('live-url-probe')
                result = {'status':'OBSERVED','url':observation['url'],'controls':len(observation['elements']),
                          'model_calls':0,'notice':'Navigation/observation only, not an automation success'}
            elif args.command == 'record':
                from .recording import record
                result = record(driver,start_url=start_url,checks=checks)
            elif args.command == 'agent':
                from .agent import run_agent
                def approve_action(proposal):
                    print(json.dumps(proposal,indent=2))
                    return input('Execute this action? Type y: ').strip().lower() == 'y'
                result = run_agent(driver,provider,start_url=start_url,goal=args.goal,checks=checks,
                                   approve=approve_action,send_screenshots=args.send_screenshots)
            else:
                from .workflows import replay
                result = replay(driver,workflow,inputs,receipt)
            save_json(output/'result.json',result)
            print(json.dumps({'output':str(output),**result},indent=2))
            return 0 if result['status'] in {'OBSERVED','VERIFIED','DRAFT_REQUIRES_REVIEW'} else 2
    except (Exception,KeyboardInterrupt) as exc:
        blocked = 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc)
        result = {'status':'ENVIRONMENT_BLOCKED' if blocked else 'HALTED','error_type':type(exc).__name__,
                  'error':'Browser URL navigation is blocked by administrator policy; no fallback was attempted' if blocked else
                      (str(exc)[:500] if isinstance(exc,(LiveError,FileNotFoundError)) else 'Execution failed; no automatic retry or fixture substitution'),
                  'live_site_qualified':False}
        if output and args.command not in {'approve','import-trustudio'}:
            save_json(output/'result.json',result)
        print(json.dumps(result,indent=2),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
