import ast
import hashlib
import json
from pathlib import Path
import pytest
from utils.upstream import extract_source,git_blob_sha,load_policy,basic_environment
from simulation.registry import ROOT


def test_ast_extractor_preserves_selected_bodies_not_top_level_side_effects():
    src='import unavailable\nraise Exception()\nVALUE=3\ndef foo(x):\n return x+VALUE\nclass X:\n def bar(self,x):\n  return foo(x)\n'
    out=extract_source(src,['VALUE','foo','X.bar']);env={};exec(out,env)
    assert env['foo'](2)==5 and env['bar'](None,4)==7
    assert 'raise Exception' not in out and 'import unavailable' not in out
    with pytest.raises(ValueError):extract_source(src,['missing'])


def test_git_blob_hash_not_plain_sha1():
    assert git_blob_sha(b'')=='e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
    assert git_blob_sha(b'hello')!=hashlib.sha1(b'hello').hexdigest()


def test_catalog_twelve_distinct_original_repositories():
    sources=json.loads((ROOT/'sources.lock.json').read_text())['sources']
    assert len(sources)==12 and len({x['repository'] for x in sources.values()})==12
    for bot,spec in sources.items():
        assert (ROOT/'bots'/bot/'bot.json').exists()
        for file in spec['files']:
            assert len(file['blob_sha'])==40


def test_missing_source_is_fatal(tmp_path):
    with pytest.raises((RuntimeError,FileNotFoundError)):load_policy(tmp_path,basic_environment())


def test_bad_source_hash_never_installed(tmp_path,monkeypatch):
    from tools import fetch_upstreams
    monkeypatch.setattr(fetch_upstreams,'ROOT',tmp_path)
    (tmp_path/'bots'/'dummy'/'code').mkdir(parents=True)
    (tmp_path/'dummy.main.py').write_text('not the source')
    spec={'repository':'owner/repo','policy':'dummy','files':[{'name':'main','path':'x.py','blob_sha':'0'*40,'selectors':['f']}]}
    with pytest.raises(ValueError,match='wrong Git blob'):fetch_upstreams.install('dummy',spec,from_files=tmp_path)
    assert not (tmp_path/'bots'/'dummy'/'code'/'upstream').exists()
