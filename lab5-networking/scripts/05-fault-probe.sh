#!/usr/bin/env bash
set -euo pipefail
K=(kubectl --kubeconfig "${LAB5_KUBECONFIG:-$HOME/.kube/lab5.yaml}" --context kind-lab5 --request-timeout=20s -n shop)
name="panda-client-fault-$(date +%s)"
trap '"${K[@]}" delete pod "$name" --ignore-not-found --wait=false' EXIT
"${K[@]}" run "$name" --image=registry.local/shop/app:1.0.0 --image-pull-policy=Never \
  --restart=Never --labels=app=panda-client --command -- python -c 'import time; time.sleep(600)'
"${K[@]}" wait --for=condition=Ready "pod/$name" --timeout=120s
"${K[@]}" exec "$name" -- python -u -c '
import json,time,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
url="http://shop-api.shop.svc.cluster.local.:8000/order"
for i in range(6):
    request=urllib.request.Request(url,data=json.dumps({"item":"recovery-network-check","quantity":1}).encode(),headers={"Content-Type":"application/json"})
    start=time.monotonic()
    try:
        with opener.open(request,timeout=4) as response:
            print("ORDER",response.status,response.read().decode(),flush=True)
    except Exception as exc:
        print("ORDER FAILED",str(exc),"elapsed",round(time.monotonic()-start,2),flush=True)
    time.sleep(2)
'
