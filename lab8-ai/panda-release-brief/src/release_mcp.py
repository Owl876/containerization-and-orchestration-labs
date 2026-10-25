"""MCP facade for a local, read-only substitute for a GitLab project."""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP('PandaRelease catalog', host='0.0.0.0', port=8000,
              stateless_http=True, json_response=True)
DATA = Path('/data/releases.json')


def find_release(release_id: str) -> dict:
    releases = json.loads(DATA.read_text())
    if release_id not in releases:
        raise ValueError(f'Unknown release: {release_id}')
    return releases[release_id]


@mcp.tool()
def get_release(release_id: str) -> dict:
    """Read release metadata, changes and rollback plan for an exact release ID."""
    release = find_release(release_id)
    return {key: value for key, value in release.items() if key != 'checks'}


@mcp.tool()
def get_checks(release_id: str) -> dict:
    """Read CI checks and approval status for an exact release ID."""
    return {'release_id': release_id, **find_release(release_id)['checks']}


@mcp.custom_route('/health', methods=['GET'])
async def health(request):
    json.loads(DATA.read_text())
    return JSONResponse({'status': 'ok'})


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
