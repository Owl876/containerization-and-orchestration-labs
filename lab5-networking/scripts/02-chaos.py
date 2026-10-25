"""180-second Service/DNS and NodePort check during graceful pod deletions."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

lab = Path(__file__).resolve().parents[1]
k = ['kubectl', '--kubeconfig', os.getenv('LAB5_KUBECONFIG', str(Path.home()/'.kube/lab5.yaml')),
     '--context', 'kind-lab5', '--request-timeout=20s']
out = lab/'report/evidence'/time.strftime('chaos-%Y%m%d-%H%M%S')
out.mkdir(parents=True)
duration = 180

def run(*args):
    return subprocess.check_output(k+list(args), text=True)

def snapshot():
    return json.loads(run('-n', 'shop', 'get', 'pods', '-o', 'json'))

# A separate client survives deletion of application pods, using the cached app image.
client = 'panda-client-' + str(int(time.time()))
processes = []
files = []
try:
    run('-n', 'shop', 'run', client, '--image=registry.local/shop/app:1.0.0',
        '--image-pull-policy=Never', '--restart=Never', '--labels=app=panda-client',
        '--command', '--', 'python', '-c', 'import time; time.sleep(900)')
    run('-n', 'shop', 'wait', '--for=condition=Ready', 'pod/'+client, '--timeout=120s')
    (out/'pods-before.json').write_text(json.dumps(snapshot(), indent=2))
    (out/'kube-proxy.yaml').write_text(run('-n', 'kube-system', 'get', 'configmap', 'kube-proxy', '-o', 'yaml'))
    code = (lab/'scripts/load-client.py').read_text()
    commands = {
        'dns': k+['-n', 'shop', 'exec', '-i', client, '--', 'python', '-u', '-',
                  'http://shop-api.shop.svc.cluster.local.:8000/health', str(duration)],
        'nodeport': [sys.executable, '-u', str(lab/'scripts/load-client.py'),
                     'http://127.0.0.1:28000/health', str(duration)],
    }
    for name, command in commands.items():
        f = (out/(name+'.jsonl')).open('w')
        err = (out/(name+'.stderr')).open('w')
        files.extend([f, err])
        p = subprocess.Popen(command, stdin=subprocess.PIPE if name == 'dns' else subprocess.DEVNULL,
                             stdout=f, stderr=err, text=True)
        processes.append(p)
        if name == 'dns':
            p.stdin.write(code)
            p.stdin.close()
    print('Load running for 180 seconds. Evidence:', out, flush=True)
    end = time.monotonic()+duration
    with (out/'deletions.jsonl').open('w') as events, (out/'pod-snapshots.jsonl').open('w') as snapshots:
        while time.monotonic() < end-10:
            time.sleep(8)
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Load client exited early; inspect stderr files')
            state = snapshot()
            snapshots.write(json.dumps({'time': time.time(), 'pods': state})+'\n')
            snapshots.flush()
            candidates = [p for p in state['items']
                          if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') in ('api', 'worker')
                          and not p['metadata'].get('deletionTimestamp')
                          and any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions', []))]
            if not candidates:
                raise RuntimeError('No Ready application pods available')
            pod = random.choice(candidates)
            event = dict(time=time.time(), pod=pod['metadata']['name'], ip=pod['status'].get('podIP'))
            run('-n', 'shop', 'delete', 'pod', event['pod'], '--wait=false')
            events.write(json.dumps(event)+'\n')
            events.flush()
            print('Deleted:', event['pod'], event['ip'], flush=True)
    for p in processes:
        if p.wait(timeout=40) != 0:
            raise RuntimeError('Load process failed; inspect stderr files')
    for f in files:
        f.close()
    for name in commands:
        rows = [json.loads(line) for line in (out/(name+'.jsonl')).read_text().splitlines()]
        errors = sum(r['status'] != 200 or bool(r['error']) for r in rows)
        print(f'{name}: requests={len(rows)} errors={errors}', flush=True)
        if not rows:
            raise RuntimeError('Empty load results')
    (out/'pods-after.json').write_text(json.dumps(snapshot(), indent=2))
    print('Results saved:', out)
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
    for f in files:
        f.close()
    subprocess.run(k+['-n', 'shop', 'delete', 'pod', client, '--ignore-not-found', '--wait=false'], check=False)
