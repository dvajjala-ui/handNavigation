"""Operator driver for the remote worker's collection schedule (loopback only, one-shot).

Creates the daily Pinterest job, runs it once through the real scheduler path, and
enables it only when that run reports VERIFIED. Run on the VM with the agent service up.
"""
import json
import re
import sys
import time
import urllib.request

BASE = 'http://127.0.0.1:47841'
PORT = '47841'


def call(route, body=None, token=None):
    headers = {'Host': '127.0.0.1:' + PORT, 'Origin': BASE}
    data = None
    if token:
        headers['X-Agent-Token'] = token
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE + '/api/' + route, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def main():
    count=int(sys.argv[1]) if len(sys.argv)>1 else 5
    daily_time=sys.argv[2] if len(sys.argv)>2 else '09:00'
    token = re.search(r'name="agent-token" content="([^"]+)"',
                      urllib.request.urlopen(BASE + '/', timeout=30).read().decode()).group(1)
    state = call('state', token=token)
    print('runner busy:', state['busy'], '| active:', state['active'], flush=True)

    library = call('collections', token=token)
    existing = [job for job in library['jobs'] if job['source'] == 'pinterest']
    wanted = {'name': 'Daily Pinterest rotation', 'source': 'pinterest', 'random_topic': True,
              'topic_key': None, 'image_count': count, 'daily_time': daily_time,
              'timezone': 'Asia/Kolkata'}
    if existing:
        job_id = existing[0]['id']
        print('updating job', job_id, 'to', count, 'images at', daily_time,
              json.dumps(call('collection-job', {'id': job_id, **wanted}, token=token)), flush=True)
    else:
        job_id = call('collection-jobs', wanted, token=token)['id']
        print('created job', job_id, flush=True)

    print('starting one real occurrence...', flush=True)
    call('collection-run', {'id': job_id}, token=token)
    runs = {}
    for _ in range(90):
        time.sleep(5)
        runs = {run['id']: run for run in call('collections', token=token)['runs']}
        mine = [run for run in runs.values() if run.get('job_id') == job_id]
        if mine and mine[0]['status'] != 'RUNNING':
            print('run', mine[0]['status'], json.dumps({k: mine[0][k] for k in
                  ('topic_key', 'requested', 'downloaded', 'stored', 'error') if k in mine[0]}), flush=True)
            break
        if not mine and not state['busy']:
            print('run row not claimed yet', flush=True)
    else:
        sys.exit('The run did not finish within 450 s; the schedule was left paused.')

    verified = [run for run in runs.values() if run.get('job_id') == job_id and run['status'] == 'VERIFIED']
    if not verified:
        sys.exit('Latest run was not VERIFIED; the schedule stays paused so no broken daily job is claimed.')

    call('collection-schedule', {'id': job_id, 'enabled': True}, token=token)
    final = call('collections', token=token)
    job = [item for item in final['jobs'] if item['id'] == job_id][0]
    print('JOB:', json.dumps(job), flush=True)
    print('TOPICS:', json.dumps(final['topics']), flush=True)
    print('COUNTS:', json.dumps(final['counts']), flush=True)
    print('RUNS:', json.dumps([{k: run[k] for k in ('topic_key', 'status', 'stored', 'requested')}
                               for run in final['runs']]), flush=True)


if __name__ == '__main__':
    main()
