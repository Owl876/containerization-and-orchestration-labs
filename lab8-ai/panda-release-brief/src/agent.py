"""Bounded LLM/tool loop. n8n owns the trigger and ordinary orchestration."""
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress
import json
import logging
import os
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

log = logging.getLogger('panda.agent')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
OLLAMA = os.getenv('OLLAMA_URL', 'http://ollama:11434')
SERVERS = {
    'release': os.getenv('RELEASE_MCP_URL', 'http://release-mcp:8000/mcp'),
    'knowledge': os.getenv('KNOWLEDGE_MCP_URL', 'http://knowledge-mcp:8000/mcp'),
}
EXPECTED = {'get_release', 'get_checks', 'read_runbook', 'write_report'}
REQUIRED = {'get_release', 'get_checks', 'read_runbook'}
REQUESTS = Counter('panda_workflow_runs_total', 'Agent runs, including rejected requests', ['status'])
DURATION = Histogram('panda_workflow_duration_seconds', 'Completed agent run latency',
                     buckets=(1, 5, 15, 30, 60, 120, 180, 300, 600))
TOOLS = Counter('panda_mcp_tool_calls_total', 'MCP calls by server, tool and status', ['server', 'tool', 'status'])
LLM = Counter('panda_llm_requests_total', 'Actual Ollama requests', ['status'])
TOKENS = Counter('panda_llm_tokens_total', 'Tokens reported by Ollama', ['kind'])
DEPENDENCY = Gauge('panda_dependency_up', 'Dependency health including model availability', ['dependency'])
INFLIGHT = Gauge('panda_workflow_inflight', 'Currently running reviews')
DECISIONS = Counter('panda_release_decisions_total', 'Policy decisions, not execution errors', ['decision'])
gate = asyncio.Lock()
dependencies = {}
for status in ('success', 'error', 'rejected'):
    REQUESTS.labels(status)
for decision in ('ready', 'blocked'):
    DECISIONS.labels(decision)


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    release_id: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}$', max_length=11)


def evaluate(release: dict, checks: dict) -> tuple[str, list[str]]:
    """Fail closed: a small model cannot override a missing/failed requirement."""
    required = {'pipeline': 'passed', 'tests': 'passed', 'image_scan': 'passed',
                'staging_smoke': 'passed', 'approval': 'approved'}
    reasons = [f'{name}={checks.get(name, "missing")}'
               for name, expected in required.items() if checks.get(name) != expected]
    if not str(release.get('rollback') or '').strip():
        reasons.append('rollback plan missing')
    return ('blocked' if reasons else 'ready'), reasons


def report_text(release_id: str, report_id: str, evidence: dict, summary: str) -> tuple[str, str]:
    release, checks = evidence['get_release'], evidence['get_checks']
    decision, reasons = evaluate(release, checks)
    text = (f'# PandaRecovery release {release_id}\n\n'
            f'- Report: `{report_id}`\n- Policy decision: **{decision.upper()}**\n'
            '- Scope: readiness review; this report does not deploy or approve a release.\n\n'
            '## Mandatory checks (authoritative)\n\n' +
            '\n'.join(f'- {key}: `{checks.get(key, "missing")}`'
                      for key in ('pipeline', 'tests', 'image_scan', 'staging_smoke', 'approval')) +
            f'\n- Rollback: {release.get("rollback") or "MISSING"}\n\n'
            '## Blocking reasons\n\n' + ('\n'.join(f'- {r}' for r in reasons) or 'None.') +
            '\n\n## AI analysis (advisory)\n\n' + summary +
            '\n\n## Evidence obtained through MCP\n\n```json\n' +
            json.dumps(evidence, ensure_ascii=False, indent=2) + '\n```\n')
    return text, decision


def unpack(result) -> dict:
    if result.isError:
        raise ValueError('; '.join(c.text for c in result.content if hasattr(c, 'text')))
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(c.text for c in result.content if hasattr(c, 'text')))


def request_error(exc: BaseException):
    """MCP's AnyIO task groups may wrap an application error on context exit."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for child in exc.exceptions:
            found = request_error(child)
            if found is not None:
                return found
    return None


async def probes():
    async with httpx.AsyncClient(timeout=4) as client:
        while True:
            for name, url in {**{k: v.rsplit('/mcp', 1)[0] + '/health' for k, v in SERVERS.items()},
                              'ollama': OLLAMA + '/api/tags'}.items():
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    healthy = name != 'ollama' or any(
                        m['name'] == MODEL for m in response.json()['models'])
                except Exception:
                    healthy = False
                dependencies[name] = healthy
                DEPENDENCY.labels(name).set(int(healthy))
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(probes())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title='PandaRelease agent', lifespan=lifespan)


@app.get('/health')
def health():
    ready = len(dependencies) == 3 and all(dependencies.values())
    return JSONResponse({'ready': ready, 'model': MODEL, 'dependencies': dependencies},
                        status_code=200 if ready else 503)


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), headers={'Content-Type': CONTENT_TYPE_LATEST})


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc):
    if request.url.path == '/runs':
        REQUESTS.labels('rejected').inc()
    return JSONResponse({'error': 'Expected {"release_id":"X.Y.Z"}; no extra fields'}, status_code=422)


async def review_release(release_id: str) -> dict:
    report_id = uuid.uuid4().hex
    evidence, trace = {}, []
    skill = (Path(__file__).parent.parent / 'skills/release-review.md').read_text()
    messages = [{'role': 'system', 'content': skill},
                {'role': 'user', 'content': f'Review release_id={release_id}. Your report_id={report_id}. '
                 'Collect the three evidence tools, then save a concise report using write_report.'}]
    async with AsyncExitStack() as stack:
        tools, routes = [], {}
        for server, url in SERVERS.items():
            read, write, _ = await stack.enter_async_context(streamablehttp_client(url))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            for tool in (await session.list_tools()).tools:
                if tool.name not in EXPECTED or tool.name in routes:
                    raise RuntimeError('Unexpected or duplicate MCP tool')
                routes[tool.name] = (server, session)
                tools.append({'type': 'function', 'function': {
                    'name': tool.name, 'description': tool.description,
                    'parameters': tool.inputSchema}})
        if set(routes) != EXPECTED:
            raise RuntimeError('Incomplete MCP toolkit')
        client = await stack.enter_async_context(httpx.AsyncClient(timeout=180))
        for turn in range(10):
            # A write must follow a model turn that has actually seen all evidence,
            # not merely follow reads in the same batch of generated tool calls.
            can_write = REQUIRED.issubset(evidence)
            try:
                response = await client.post(OLLAMA + '/api/chat', json={
                    'model': MODEL, 'messages': messages, 'tools': tools, 'stream': False,
                    'think': False, 'keep_alive': '10m',
                    'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 900,
                                'num_thread': int(os.getenv('OLLAMA_NUM_THREADS', '4'))}})
                response.raise_for_status()
                answer = response.json()
                message = answer['message']
                log.warning('LLM turn=%s finish=%s output_tokens=%s thinking_chars=%s tools=%s',
                            turn + 1, answer.get('done_reason'), answer.get('eval_count'),
                            len(message.get('thinking', '')),
                            [c.get('function', {}).get('name') for c in message.get('tool_calls', [])])
                LLM.labels('success').inc()
                TOKENS.labels('input').inc(answer.get('prompt_eval_count', 0))
                TOKENS.labels('output').inc(answer.get('eval_count', 0))
            except Exception:
                LLM.labels('error').inc()
                raise
            messages.append(message)
            calls = message.get('tool_calls', [])
            if not calls:
                if answer.get('done_reason') == 'length':
                    raise RuntimeError('Model exhausted its output budget without a tool call')
                messages.append({'role': 'user', 'content':
                                 'Task incomplete. Use the missing evidence tools, then write_report.'})
                continue
            for call in calls:
                function = call.get('function', {})
                name, args = function.get('name'), function.get('arguments', {})
                server = routes.get(name, ('unknown', None))[0]
                decision, markdown = None, None
                try:
                    if name not in routes:
                        raise ValueError('Tool is not in the allowed toolkit')
                    if not isinstance(args, dict):
                        raise ValueError('Tool arguments must be an object')
                    if name in ('get_release', 'get_checks') and args.get('release_id') != release_id:
                        raise ValueError(f'Only release_id={release_id} is allowed')
                    if name == 'read_runbook' and args.get('service') != 'pandarecovery':
                        raise ValueError('Only service=pandarecovery is allowed')
                    if name == 'write_report':
                        if not REQUIRED.issubset(evidence):
                            raise ValueError(f'Collect evidence first: {sorted(REQUIRED - evidence.keys())}')
                        if not can_write:
                            raise ValueError('Read the collected tool results, then call write_report in the next turn')
                        if args.get('report_id') != report_id:
                            raise ValueError(f'Use the issued report_id={report_id}')
                        summary = args.get('markdown', '')
                        if not isinstance(summary, str) or not 50 <= len(summary) <= 6000:
                            raise ValueError('Write a concise analysis of 50..6000 characters')
                        markdown, decision = report_text(release_id, report_id, evidence, summary)
                        args = {'report_id': report_id, 'markdown': markdown}
                    started = time.monotonic()
                    result = unpack(await routes[name][1].call_tool(name, args))
                    if name in ('get_release', 'get_checks') and result.get('release_id') != release_id:
                        raise ValueError('MCP returned evidence for another release')
                    TOOLS.labels(server, name, 'success').inc()
                    trace.append({'server': server, 'tool': name, 'status': 'success',
                                  'duration_seconds': round(time.monotonic() - started, 3)})
                    if name in REQUIRED:
                        evidence[name] = result
                    if name == 'write_report':
                        if result.get('saved') is not True or result.get('report_id') != report_id:
                            raise ValueError('Report persistence not confirmed')
                        DECISIONS.labels(decision).inc()
                        return {'report_id': report_id, 'release_id': release_id,
                                'decision': decision, 'model': MODEL,
                                'report_file': result['file'], 'markdown': markdown,
                                'tool_trace': trace, 'llm_turns': turn + 1}
                    output = json.dumps(result, ensure_ascii=False)
                except Exception as exc:
                    # Fixed labels: never put model-generated names or IDs in metrics.
                    label = name if name in EXPECTED else 'unknown'
                    TOOLS.labels(server, label, 'error').inc()
                    trace.append({'server': server, 'tool': label, 'status': 'error', 'error': str(exc)})
                    output = json.dumps({'error': str(exc)})
                    if name in ('get_release', 'get_checks') and 'Unknown release:' in str(exc):
                        raise HTTPException(404, 'Unknown release') from exc
                messages.append({'role': 'tool', 'tool_name': name or 'unknown', 'content': output})
        raise RuntimeError('Agent exhausted its 10-turn tool budget')


@app.post('/runs')
async def run(review: Review):
    if gate.locked():
        REQUESTS.labels('rejected').inc()
        raise HTTPException(429, 'One review at a time; retry after the current run')
    async with gate:
        started = time.monotonic()
        INFLIGHT.inc()
        try:
            async with asyncio.timeout(600):
                result = await review_release(review.release_id)
            result['duration_seconds'] = round(time.monotonic() - started, 3)
            REQUESTS.labels('success').inc()
            log.warning('Review finished: %s', json.dumps({k: v for k, v in result.items() if k != 'markdown'}))
            return result
        except HTTPException:
            REQUESTS.labels('rejected').inc()
            raise
        except Exception as exc:
            client_error = request_error(exc)
            if client_error is not None:
                REQUESTS.labels('rejected').inc()
                return JSONResponse({'detail': client_error.detail}, status_code=client_error.status_code)
            REQUESTS.labels('error').inc()
            log.exception('Review failed for release %s', review.release_id)
            return JSONResponse({'error': 'Review failed; inspect docker compose logs agent'}, status_code=502)
        finally:
            DURATION.observe(time.monotonic() - started)
            INFLIGHT.dec()
