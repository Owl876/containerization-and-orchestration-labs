"""Continuously probe the Service, and fail if even one request fails."""
import json
import os
import signal
import time
from urllib.request import urlopen

running = True
def stop(*_):
    global running
    running = False
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
ok = failed = 0
while running:
    try:
        with urlopen(os.environ.get("API_URL", "http://127.0.0.1:18000") + "/health", timeout=2) as response:
            assert response.status == 200 and response.read() == b"ok"
        ok += 1
    except Exception as exc:
        failed += 1
        print(json.dumps({"time": time.time(), "error": str(exc)}), flush=True)
    time.sleep(0.1)
print(json.dumps({"successful_requests": ok, "failed_requests": failed}), flush=True)
raise SystemExit(bool(failed) or not ok)
