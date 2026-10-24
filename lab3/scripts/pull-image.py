"""Fetch a public linux/amd64 image on the host and write a Docker archive.

Fallback for Docker Desktop registry networking and multiarch import issues.
Only Python's standard library is required; every blob is SHA256-verified.
"""
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

image, destination = sys.argv[1:]
registry, reference = image.split('/', 1)
repository, tag = reference.rsplit(':', 1)
api_registry = 'registry-1.docker.io' if registry == 'docker.io' else registry
root = f'https://{api_registry}/v2/{repository}'
token = None
accept = ', '.join(['application/vnd.oci.image.index.v1+json',
    'application/vnd.docker.distribution.manifest.list.v2+json',
    'application/vnd.oci.image.manifest.v1+json',
    'application/vnd.docker.distribution.manifest.v2+json'])


def request(url):
    global token
    headers = {'Accept': accept, 'User-Agent': 'lab3-image-loader/1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
        params = dict(re.findall(r'(\w+)="([^"]+)"', exc.headers['WWW-Authenticate']))
        realm = params.pop('realm')
        with urllib.request.urlopen(realm + '?' + urllib.parse.urlencode(params), timeout=30) as r:
            auth = json.load(r)
            token = auth.get('token') or auth['access_token']
        headers['Authorization'] = 'Bearer ' + token
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


with request(root + '/manifests/' + tag) as response:
    manifest = json.load(response)
if 'manifests' in manifest:
    digest = next(m['digest'] for m in manifest['manifests']
                  if m.get('platform', {}).get('architecture') == 'amd64'
                  and m.get('platform', {}).get('os') == 'linux')
    with request(root + '/manifests/' + digest) as response:
        manifest = json.load(response)
cache = Path(destination).parent / 'blobs'
cache.mkdir(parents=True, exist_ok=True)


def fetch(blob):
    digest = blob['digest'].split(':')[1]
    path = cache / digest
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
        return path
    for attempt in range(4):
        try:
            h = hashlib.sha256()
            with request(root + '/blobs/' + blob['digest']) as response, open(str(path)+'.partial', 'wb') as f:
                while chunk := response.read(1024 * 256):
                    h.update(chunk)
                    f.write(chunk)
            assert h.hexdigest() == digest, 'SHA256 mismatch'
            os.replace(str(path)+'.partial', path)
            print(f'{image}: verified {digest[:12]} ({path.stat().st_size // 1024} KiB)', flush=True)
            return path
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1)


blobs = [manifest['config'], *manifest['layers']]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    paths = list(pool.map(fetch, blobs))
with tarfile.open(destination, 'w') as archive:
    config = paths[0].name + '.json'
    archive.add(paths[0], arcname=config)
    layers = []
    for path in paths[1:]:
        name = path.name + '/layer.tar'
        archive.add(path, arcname=name)
        layers.append(name)
    content = json.dumps([{'Config': config, 'RepoTags': [image], 'Layers': layers}]).encode()
    info = tarfile.TarInfo('manifest.json')
    info.size = len(content)
    archive.addfile(info, io.BytesIO(content))
print(f'Archive ready: {destination}', flush=True)
