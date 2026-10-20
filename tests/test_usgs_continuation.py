import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def test_recursive_membership_payload_checks_and_restart_without_network(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'scripts/continue_usgs_pr.py'
    spec = importlib.util.spec_from_file_location('usgs_continuation_test_target', script)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    a, b = 'a' * 24, 'b' * 24
    raw = b'id,value\na,1\n'
    def item(sid, has_children):
        return {'id':sid,'hasChildren':has_children,'files':[{'name':'sample.csv','size':len(raw),
            'checksum':{'type':'MD5','value':hashlib.md5(raw).hexdigest()},
            'downloadUri':'https://www.sciencebase.gov/catalog/file/get/'+sid+'?f=sample'}]}
    items = {a:item(a, True), b:item(b, False)}
    monkeypatch.setattr(driver, 'load_catalog', lambda: {'releases':[
        {'sciencebase_id':sid,'raw':{'Category':'1. PR-specific'}} for sid in items]})
    monkeypatch.setattr(driver, 'read_metadata_archive', lambda *args: ({'source_workbook_sha256':'frozen'},dict(items)))
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        data = json.dumps({'total':1,'items':[{'id':b}]}).encode() if '/items?' in url else raw
        return data, {'state':'PASS','sha256':hashlib.sha256(data).hexdigest(),'http_status':200,
                      'url':url,'bytes':len(data)}
    monkeypatch.setattr(driver, 'fetch_manifest', fetch)
    out = tmp_path / 'snapshot'
    result = driver.continue_snapshot(Path('unused'), 'frozen', out, byte_budget=len(raw)*2)
    assert len(calls) == 3
    assert result['root_count'] == result['item_count'] == 2
    assert result['enumeration_state'] == 'PASS'
    assert result['payload_states'] == {'PASS':2}
    assert result['byte_budget_remaining'] == 0
    assert result['activated'] == 0 and result['activation_state'] == 'BLOCKED'
    assert next(r for r in result['assets'] if r['source_item_id']==b)['root_release_ids'] == [a,b]
    monkeypatch.setattr(driver, 'fetch_manifest', lambda *a, **k: pytest.fail('Frozen source redownloaded'))
    second = driver.continue_snapshot(Path('unused'), 'frozen', out, byte_budget=len(raw)*2)
    assert second == result
    (out/'payloads'/(a+'_0.bin')).write_bytes(raw[:-1]+b'x')
    third = driver.continue_snapshot(Path('unused'), 'frozen', out, byte_budget=len(raw)*2)
    assert third['payload_states'] == {'FAIL':1,'PASS':1}
