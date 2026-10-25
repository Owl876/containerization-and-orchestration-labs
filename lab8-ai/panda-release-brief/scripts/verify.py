"""Run inside the agent container: real n8n -> LLM -> MCP end-to-end checks."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


def request(url, payload=None):
    req = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=660) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


results = []
for release, expected in [('1.1.0', 'ready'), ('1.2.0', 'blocked')]:
    status, result = request('http://n8n:5678/webhook/panda-release-brief', {'release_id': f' {release} '})
    assert status == 200, (status, result)
    assert result['decision'] == expected, result
    assert result['llm_turns'] >= 2, result
    successful = {(row['server'], row['tool']) for row in result['tool_trace'] if row['status'] == 'success'}
    assert successful == {('release', 'get_release'), ('release', 'get_checks'),
                          ('knowledge', 'read_runbook'), ('knowledge', 'write_report')}, result
    assert f'Policy decision: **{expected.upper()}**' in result['markdown']
    results.append(result)

status, invalid = request('http://n8n:5678/webhook/panda-release-brief', {'release_id': '../../etc/passwd'})
assert status == 422, (status, invalid)
status, unknown = request('http://n8n:5678/webhook/panda-release-brief', {'release_id': '9.9.9'})
assert status == 404, (status, unknown)
_, targets = request('http://prometheus:9090/api/v1/targets')
assert all(t['health'] == 'up' for t in targets['data']['activeTargets']), targets
_, dashboard = request('http://grafana:3000/api/dashboards/uid/panda-release')
assert len(dashboard['dashboard']['panels']) >= 3, dashboard
graphs = {}
for name, query in {
    'runs': 'sum(panda_workflow_runs_total)',
    'latency': 'histogram_quantile(0.95, sum by (le) (rate(panda_workflow_duration_seconds_bucket[15m])))',
    'tools': 'sum by (server) (panda_mcp_tool_calls_total)',
}.items():
    _, graph = request('http://prometheus:9090/api/v1/query?' + urlencode({'query': query}))
    assert graph['data']['result'], (name, graph)
    assert all(row['value'][1] != 'NaN' for row in graph['data']['result']), (name, graph)
    graphs[name] = graph['data']['result']
print(json.dumps({'results': results, 'invalid_request': invalid, 'unknown_release': unknown,
                  'prometheus_targets': targets, 'dashboard_graphs': graphs}, ensure_ascii=False, indent=2))
