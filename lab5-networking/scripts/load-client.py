"""One HTTP request per sample, without retries; JSONL output."""

import json
import sys
import time
import urllib.request

url, duration = sys.argv[1], float(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
end = time.monotonic() + duration
while time.monotonic() < end:
    start = time.time()
    status, error = 0, ""
    try:
        with opener.open(url, timeout=3) as response:
            status = response.status
            response.read()
    except Exception as exc:
        error = str(exc)
    print(
        json.dumps(
            dict(
                time=start,
                status=status,
                error=error,
                latency_ms=round((time.time() - start) * 1000, 2),
            )
        ),
        flush=True,
    )
    time.sleep(0.2)
