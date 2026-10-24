#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/08-alert-firing.txt") 2>&1
date -Is
restore() { kubectl scale deployment/shop-worker -n shop --replicas=2; }
trap restore EXIT
kubectl scale deployment/shop-worker -n shop --replicas=0
python3 - "$LAB_DIR/report/evidence/08-alerts.json" <<'PY'
import json,os,sys,time
from urllib.request import urlopen
url=os.environ['PROM_URL']+'/api/v1/alerts'
for attempt in range(100):
    with urlopen(url,timeout=10) as r: data=json.load(r)
    alerts=[a for a in data['data']['alerts'] if a['labels'].get('alertname')=='ShopWorkersStalled' and a['state']=='firing']
    if alerts:
        open(sys.argv[1],'w').write(json.dumps(data,indent=2)+'\n')
        print(json.dumps(alerts,indent=2)); break
    time.sleep(2)
else: raise SystemExit('FAIL: ShopWorkersStalled did not enter firing state')
PY
restore
trap - EXIT
kubectl rollout status deployment/shop-worker -n shop --timeout=180s
echo 'PASS: alert fired; workers restored.'
