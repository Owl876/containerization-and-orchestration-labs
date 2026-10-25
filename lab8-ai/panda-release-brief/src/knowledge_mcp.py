"""MCP facade for runbooks and the release report store."""
import os
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP('PandaRelease knowledge', host='0.0.0.0', port=8000,
              stateless_http=True, json_response=True)
REPORTS = Path('/reports')


def report_path(report_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', report_id):
        raise ValueError('report_id must be a server-issued UUID hex')
    return REPORTS / f'{report_id}.md'


@mcp.tool()
def read_runbook(service: str) -> dict:
    """Read the release readiness policy for the pandarecovery service."""
    if service != 'pandarecovery':
        raise ValueError('Unsupported service')
    return {'service': service, 'policy': Path('/data/runbook.md').read_text()}


@mcp.tool()
def write_report(report_id: str, markdown: str) -> dict:
    """Atomically save a Markdown report. report_id: UUID hex; markdown: report text."""
    destination = report_path(report_id)
    if not 50 <= len(markdown) <= 20000:
        raise ValueError('Report must contain 50..20000 characters')
    # A temporary file plus atomic rename prevents partially written reports.
    with tempfile.NamedTemporaryFile(mode='w', dir=REPORTS, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(markdown)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(destination)
    return {'report_id': report_id, 'file': destination.name, 'saved': True}


@mcp.custom_route('/health', methods=['GET'])
async def health(request):
    return JSONResponse({'status': 'ok'})


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
