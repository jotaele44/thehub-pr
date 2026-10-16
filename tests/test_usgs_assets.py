import hashlib
import io
import json
import zipfile

import pytest

from hub.usgs_assets import (approved_download_url, doi_identifiers, file_inventory, inspect_csv,
                            inspect_payload, inspect_zip, read_metadata_archive, root_membership, verify_payload)


def test_frozen_metadata_archive_closes_root_identity_and_bytes():
    from hub.usgs_catalog import ROOT, load_catalog
    summary, items = read_metadata_archive(ROOT / "data/usgs/snapshots/20261016_runner_metadata.zip",
        "47488d1d72a2a43b8c2a4d3b44b600d4852ceca99e6796aae334814f95e7f7c8")
    assert set(items) == {r['sciencebase_id'] for r in load_catalog()['releases']}
    inventory = file_inventory(items)
    assert summary['attempted'] == 174
    assert len(inventory) == 943
    assert len({r['asset_id'] for r in inventory}) == 943
    assert sum(r['raw_descriptor']['size'] for r in inventory) == 409375206604
    assert all(r['activation_state'] == 'BLOCKED' for r in inventory)


def test_size_and_authoritative_checksum_must_both_match():
    raw = b'id,value\na,1\n'
    d = {'size': len(raw), 'checksum': {'type': 'MD5', 'value': hashlib.md5(raw).hexdigest()}}
    assert verify_payload(raw, d)['state'] == 'PASS'
    with pytest.raises(ValueError, match='size'):
        verify_payload(raw + b'x', d)
    with pytest.raises(ValueError, match='checksum'):
        verify_payload(raw[:-1] + b'x', d)
    with pytest.raises(ValueError, match='unavailable'):
        verify_payload(raw, {'size': len(raw)})


def test_csv_preserves_preamble_blank_rows_and_no_invented_header():
    raw = b'"Study note","raw preamble"\r\n"id","value"\r\n"a","1"\r\n\r\n'
    result = inspect_csv(raw)
    assert result['parsed_rows'] == 4 and result['blank_rows'] == 1
    assert result['preamble_and_header_candidates'][0] == ['Study note', 'raw preamble']
    assert result['header_state'] == 'UNRESOLVED' and result['record_denominator'] is None
    assert inspect_csv(b'\x81\xff')['state'] == 'OPEN'


def test_zip_member_hashes_and_duplicate_path_refusal():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('nested/a.txt', b'original')
    result = inspect_zip(stream.getvalue())
    assert result['members'] == [{'path': 'nested/a.txt', 'uncompressed_size': 8,
                                  'sha256': hashlib.sha256(b'original').hexdigest()}]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('../outside', b'bad')
    with pytest.raises(ValueError, match='Unsafe'):
        inspect_zip(stream.getvalue())


def test_file_url_must_bind_to_returned_source_id():
    sid = '61ae5641d34eb622f69a7220'
    url = 'https://www.sciencebase.gov/catalog/file/get/' + sid + '?f=file'
    assert approved_download_url(sid, {'downloadUri': url}) == url
    for other in ['https://example.com/catalog/file/get/' + sid, url.replace(sid, 'different')]:
        with pytest.raises(ValueError):
            approved_download_url(sid, {'url': other})


def test_geojson_null_and_geometry_types_preserved_without_spatial_promotion():
    result = inspect_payload(json.dumps({'type':'FeatureCollection','features':[
        {'type':'Feature','geometry':None,'properties':{}},
        {'type':'Feature','geometry':{'type':'Point','coordinates':[-66,18,12]},'properties':{}}]}).encode(), 'sample.geojson')
    assert result['feature_count'] == 2
    assert result['geometry_types'] == {'NULL_EMPTY':1,'Point':1}
    assert result['spatial_state'] == 'UNRESOLVED'


def test_shared_descendant_preserves_all_roots_and_cycles_fail_closed():
    edges = [{'parent':'a','child':'c'}, {'parent':'b','child':'c'}, {'parent':'c','child':'d'}]
    result = root_membership({'a','b'}, edges)
    assert result['d'] == ['a','b'] and result['c'] == ['a','b']
    with pytest.raises(ValueError, match='Cyclic'):
        root_membership({'a'}, edges + [{'parent':'d','child':'a'}])
    with pytest.raises(ValueError, match='Duplicate'):
        root_membership({'a'}, edges + [edges[0]])


def test_identifier_type_case_is_taxonomy_not_identity():
    item={'id':'stable-item','identifiers':[{'type':'doi','key':'doi:10.5066/P9HQKKFO'},
        {'type':'DOI','key':'doi:10.5066/P9NSUI97'}, {'type':'name','key':'not-an-identifier'}]}
    values=doi_identifiers(item)
    assert len(values)==2 and values[0]['value']=='10.5066/P9HQKKFO'
    assert values[0]['raw']['type']=='doi' and item['id']=='stable-item'


def test_frozen_native_geojson_adapter_preserves_source_features_and_refuses_duplicate_keys():
    import gzip
    from pathlib import Path
    from hub.usgs_assets import adapt_native_geojson
    staged = Path(__file__).resolve().parents[1] / 'data/usgs/staging'
    counts = []
    for path in sorted(staged.glob('*.native.json')):
        expected = json.loads(path.read_text())
        raw = gzip.decompress(path.with_name(path.name.replace('.native.json','.geojson.gz')).read_bytes())
        actual = adapt_native_geojson(raw, expected['source_descriptor_raw'], expected['source_key'])
        assert actual['native_feature_collection'] == json.loads(raw)
        assert actual['source_keys'] == expected['source_keys']
        assert actual['activation_state'] == actual['production_export_state'] == 'BLOCKED'
        assert actual['spatial_state'] == 'UNRESOLVED'
        counts.append(actual['feature_count'])
    assert sorted(counts) == [6,35,51]
    raw = b'{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"ID":1}},{"type":"Feature","properties":{"ID":1}}]}'
    descriptor = {'size':len(raw),'checksum':{'type':'MD5','value':hashlib.md5(raw).hexdigest()}}
    with pytest.raises(ValueError, match='Duplicate source feature key'):
        adapt_native_geojson(raw, descriptor, 'ID')
