"""Check TCP access and application health under the active policies."""
import json
import os
from pathlib import Path
import subprocess
import time

lab = Path(__file__).resolve().parents[1]
k = ['kubectl', '--kubeconfig', os.getenv('LAB5_KUBECONFIG', str(Path.home()/'.kube/lab5.yaml')),
     '--context', 'kind-lab5', '--request-timeout=20s', '-n', 'shop']
out = lab/'report/evidence'/time.strftime('matrix-%Y%m%d-%H%M%S')
out.mkdir(parents=True)
created = []
rows = []
def run(*args):
    return subprocess.check_output(k+list(args), text=True)
def check(pod, code, *args):
    return json.loads(run('exec', pod, '--', 'python', '-c', code, *args))
probe = '''import socket,sys,json
try:
 with socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=2): pass
 print(json.dumps({'allowed':True,'detail':'TCP connected'}))
except OSError as e:
 print(json.dumps({'allowed':False,'detail':str(e)}))
'''
try:
    suffix=str(int(time.time()))
    for role in ['client','camera']:
        name='panda-'+role+'-'+suffix
        run('run',name,'--image=registry.local/shop/app:1.0.0','--image-pull-policy=Never',
            '--restart=Never','--labels=app=panda-'+role,'--command','--','python','-c','import time; time.sleep(900)')
        created.append(name)
        run('wait','--for=condition=Ready','pod/'+name,'--timeout=120s')
    pods=json.loads(run('get','pods','-o','json'))['items']
    def group(role):
        return [p for p in pods if p['metadata'].get('labels',{}).get('app.kubernetes.io/name')==role
                and not p['metadata'].get('deletionTimestamp')
                and any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[]))]
    apis,workers=group('api'),group('worker')
    if len(apis)<2 or len(workers)<2:
        raise RuntimeError('Need at least two Ready API and worker pods to avoid self-connections')
    db=next(p for p in pods if p['metadata'].get('labels',{}).get('cnpg.io/cluster')=='shop-db')
    sources={'client':created[0],'camera':created[1],'api':apis[0]['metadata']['name'],'worker':workers[0]['metadata']['name']}
    targets={'api':(apis[1]['status']['podIP'],8000),'worker':(workers[1]['status']['podIP'],8000),'postgres':(db['status']['podIP'],5432)}
    (out/'pods.json').write_text(json.dumps(pods,indent=2))
    print(f'{"SOURCE":10} {"TARGET":10} {"EXPECTED":10} {"ACTUAL":10} RESULT',flush=True)
    for source,pod in sources.items():
        for target,(ip,port) in targets.items():
            expected=(source=='client' and target=='api') or (source in ('api','worker') and target=='postgres')
            actual=check(pod,probe,ip,str(port))
            row=dict(source=source,target=target,ip=ip,port=port,expected=expected,**actual)
            rows.append(row)
            print(f'{source:10} {target:10} {("ALLOW" if expected else "DENY"):10} {("ALLOW" if actual["allowed"] else "DENY"):10} {"PASS" if expected==actual["allowed"] else "FAIL"}',flush=True)
    # Confirm DNS+Service HTTP and real authenticated SQL, not just open ports.
    http=check(sources['client'],'''import urllib.request,json
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://shop-api.shop.svc.cluster.local.:8000/health',timeout=5) as r:
 print(json.dumps({'status':r.status,'body':r.read().decode()}))''')
    print('Client -> API via DNS:',http,flush=True)
    sql={}
    for role in ['api','worker']:
        sql[role]=check(sources[role],'''import os,psycopg,json
with psycopg.connect(host=os.environ['PGHOST'],dbname=os.environ['PGDATABASE'],user=os.environ['PGUSER'],password=os.environ['PGPASSWORD'],connect_timeout=5) as c:
 print(json.dumps({'select_1':c.execute('SELECT 1').fetchone()[0]}))''')
        print(role,'-> PostgreSQL:',sql[role],flush=True)
    (out/'matrix.json').write_text(json.dumps(rows,indent=2))
    (out/'application-checks.json').write_text(json.dumps(dict(http=http,sql=sql),indent=2))
    table=['| Source | Target | Expected | Actual | Result |','| --- | --- | --- | --- | --- |']
    for r in rows:
        table.append(f'| {r["source"]} | {r["target"]} | {r["expected"]} | {r["allowed"]} | {"PASS" if r["expected"]==r["allowed"] else "FAIL"} |')
    (out/'matrix.md').write_text('\n'.join(table)+'\n')
    print('Evidence:',out)
    if any(r['expected']!=r['allowed'] for r in rows):
        raise SystemExit('FAIL: access matrix mismatch')
finally:
    (out/'matrix.json').write_text(json.dumps(rows,indent=2))
    for name in created:
        subprocess.run(k+['delete','pod',name,'--ignore-not-found','--wait=false'],check=False)
