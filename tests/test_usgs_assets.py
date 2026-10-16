import hashlib
import io
import json
import zipfile

import pytest

from hub.usgs_assets import (approved_download_url, file_inventory, inspect_csv,
                            inspect_payload, inspect_zip, read_metadata_archive, verify_payload)


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
