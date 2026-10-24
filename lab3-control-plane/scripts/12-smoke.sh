#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/02-shop-smoke.txt") 2>&1
date -Is
kubectl get nodes
kubectl get pods,svc,cluster -n shop
helm list -A
python3 - <<'PY'
import concurrent.futures,json,os,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
base=os.environ['API_URL']
def create(i):
    req=Request(base+'/order',data=json.dumps({'item':f'bamboo-{i}','quantity':i+1}).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=10) as r:
        assert r.status==201
        return json.load(r)['id']
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    ids=set(pool.map(create,range(20)))
assert len(ids)==20
for attempt in range(30):
    with urlopen(base+'/orders',timeout=10) as r: orders=json.load(r)
    matched=[r for r in orders if r['id'] in ids]
    if len(matched)==20 and all(r['status']=='processed' for r in matched):break
    time.sleep(1)
else:raise AssertionError('Workers did not process all new orders')
try:
    urlopen(Request(base+'/order',data=b'{"item":"bad","quantity":-1}',headers={'Content-Type':'application/json'}),timeout=5)
    raise AssertionError('Negative quantity was accepted')
except HTTPError as e:assert e.code==422
for url in (base,os.environ['WORKER_URL']):
    with urlopen(url+'/health',timeout=5) as r:assert r.read()==b'ok'
    with urlopen(url+'/metrics',timeout=5) as r:assert b'shop_http_requests_total' in r.read()
with urlopen(base+'/version',timeout=5) as r:print('Version:',json.load(r))
print('New order IDs:',sorted(ids))
print('Workers that processed these orders:',sorted({r['processed_by'] for r in matched}))
print('PASS: 20 concurrent orders persisted and processed; invalid quantity rejected; both health and metrics endpoints work.')
PY
