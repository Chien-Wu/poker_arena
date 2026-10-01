#!/usr/bin/env python3
"""Explicit, pinned build-time source acquisition. NEVER called by a match.

Raw Git blob hashes are checked before selecting strategy declarations. Source
files retain their upstream ownership/license. No third-party model is invented.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.upstream import git_blob_sha, extract_source

MAX_DOWNLOAD=16*1024*1024


def download_blob(repository: str, sha: str) -> bytes:
    url=f'https://api.github.com/repos/{repository}/git/blobs/{sha}'
    headers={'Accept':'application/vnd.github+json','User-Agent':'poker-arena-source-installer/1'}
    token=os.environ.get('GITHUB_TOKEN')
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                data=response.read(MAX_DOWNLOAD+1)
            if len(data)>MAX_DOWNLOAD:raise ValueError('Source download too large')
            payload=json.loads(data)
            if payload.get('encoding')!='base64':raise ValueError('Expected a base64 Git blob')
            raw=base64.b64decode(payload['content'])
            if git_blob_sha(raw)!=sha:raise ValueError('Upstream Git blob hash mismatch')
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code in (401,403,404):
                raise RuntimeError(f'{repository}: GitHub HTTP {exc.code}. Check access/rate limit; GITHUB_TOKEN is optional at install time.') from exc
            if attempt==2:raise
        except urllib.error.URLError:
            if attempt==2:raise
        time.sleep(2**attempt)
    raise RuntimeError('Unreachable download state')


def build_go(bot_dir: Path):
    if shutil.which('go') is None:raise RuntimeError('The PokerForBots handler requires Go >=1.22 at build time')
    bridge=bot_dir/'code'/'bridge'
    env={**os.environ,'CGO_ENABLED':'0','GOPROXY':'off','GOTOOLCHAIN':'local'}
    subprocess.run(['go','build','-trimpath','-o',str(bot_dir/'code'/'handler'),'.'],
                   cwd=bridge,env=env,check=True,timeout=120)


def install(bot_id: str, spec: dict, *, from_files: Path|None=None):
    bot_dir=ROOT/'bots'/bot_id
    destination=bot_dir/'code'/'upstream'
    temp=Path(tempfile.mkdtemp(prefix='.fetch-',dir=bot_dir/'code'))
    receipt={'repository':spec['repository'],'policy':spec['policy'],
             'verification':'raw_git_blob_verified','sources':[],'policies':[]}
    try:
        for file in spec['files']:
            suffix='.go' if file['path'].endswith('.go') else '.py'
            if from_files:
                raw=(from_files/f"{bot_id}.{file['name']}{suffix}").read_bytes()
            else:
                raw=download_blob(spec['repository'],file['blob_sha'])
            if git_blob_sha(raw)!=file['blob_sha']:
                raise ValueError(f"{bot_id}/{file['name']}: wrong Git blob; no source was installed")
            raw_dir=temp/'raw';raw_dir.mkdir(exist_ok=True)
            (raw_dir/(file['blob_sha']+suffix)).write_bytes(raw)
            receipt['sources'].append({'path':file['path'],'git_blob_sha':file['blob_sha'],
                                       'sha256':hashlib.sha256(raw).hexdigest()})
            if suffix=='.go':
                target=bot_dir/'code'/'bridge'/'sdk'/'bots'/'aggressive'/'handler.go'
                target.write_bytes(raw)
                build_go(bot_dir)
            else:
                code=extract_source(raw.decode('utf-8-sig'),file['selectors']).encode()
                compile(code,file['path'],'exec')
                name=file['name']+'.policy.py'
                (temp/name).write_bytes(code)
                receipt['policies'].append({'file':name,'sha256':hashlib.sha256(code).hexdigest(),
                                            'selectors':file['selectors']})
        (temp/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        backup=destination.with_name('upstream.backup')
        if backup.exists():shutil.rmtree(backup)
        if destination.exists():destination.rename(backup)
        try:temp.rename(destination)
        except BaseException:
            if backup.exists():backup.rename(destination)
            raise
        if backup.exists():shutil.rmtree(backup)
        return receipt
    finally:
        if temp.exists():shutil.rmtree(temp)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all',action='store_true')
    group.add_argument('--bot',action='append',dest='bots')
    parser.add_argument('--from-files',type=Path,help='Offline directory of BOT.SECTION.py/.go full pinned source files')
    args=parser.parse_args(argv)
    lock=json.loads((ROOT/'sources.lock.json').read_text())['sources']
    ids=list(lock) if args.all else args.bots
    unknown=set(ids)-set(lock)
    if unknown:parser.error(f'Unknown upstream bots: {sorted(unknown)}')
    print('Build-time download only. Review upstream licenses before redistributing fetched code.')
    failures=[]
    for bot_id in ids:
        try:
            install(bot_id,lock[bot_id],from_files=args.from_files)
            print(f'INSTALLED {bot_id}: {lock[bot_id]["policy"]}')
        except Exception as exc:
            failures.append(bot_id)
            print(f'FAILED {bot_id}: {exc}',file=sys.stderr)
    print(f'{len(ids)-len(failures)}/{len(ids)} source integrations installed')
    return 1 if failures else 0

if __name__=='__main__':raise SystemExit(main())
