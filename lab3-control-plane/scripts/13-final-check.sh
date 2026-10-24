#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/09-final-check.txt") 2>&1
date -Is
kubectl rollout status deployment/shop-api -n shop --timeout=180s
kubectl rollout status deployment/shop-worker -n shop --timeout=180s
kubectl wait --for=condition=Ready cluster/shop-db -n shop --timeout=120s
kubectl get pods,cluster -n shop
kubectl get clusterpolicy
helm list -A
python3 - <<'PY'
import base64,json,os,time,urllib.request

def get(url,auth=False):
    headers={'Authorization':'Basic '+base64.b64encode(b'admin:panda-admin').decode()} if auth else {}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=10) as response:
        return json.load(response)

api=os.environ['API_URL']; prom=os.environ['PROM_URL']
assert get(api+'/version')['version']=='1.1.0'
orders=get(api+'/orders')
assert len(orders)>=20 and all(o['status']=='processed' for o in orders)
print('Processed orders in PostgreSQL:',len(orders))
for attempt in range(45):
    targets=[t for t in get(prom+'/api/v1/targets')['data']['activeTargets']
             if t['labels'].get('namespace')=='shop']
    alerts=[a for a in get(prom+'/api/v1/alerts')['data']['alerts']
            if a['labels'].get('alertname','').startswith('Shop')]
    if len(targets)==5 and all(t['health']=='up' for t in targets) and not alerts:break
    time.sleep(2)
else:raise AssertionError('Monitoring did not recover: '+repr((targets,alerts)))
rules=[r for g in get(prom+'/api/v1/rules')['data']['groups'] for r in g['rules'] if r['name'].startswith('Shop')]
assert len(rules)==3 and all(r['health']=='ok' for r in rules)
dash=get('http://127.0.0.1:13000/api/dashboards/uid/shop-lab3',True)['dashboard']
assert len(dash['panels'])==8
print('Prometheus:',len(targets),'healthy Shop targets;',len(rules),'valid, inactive Shop alerts')
print('Grafana:',dash['title'],len(dash['panels']),'panels')
print('PASS: all workloads healthy; API 1.1.0; orders persisted; monitoring restored after experiments.')
PY
