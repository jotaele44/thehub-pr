from __future__ import annotations

import io
import sqlite3
import struct
import tempfile
import zipfile

import pytest

from server.backend.gis_device_ingestion import GisIngestionError, ingest_device_bytes


def _zip(files: dict[str, bytes], compression=zipfile.ZIP_DEFLATED) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return out.getvalue()


def _point_shp(x=-66.4, y=18.2) -> bytes:
    header = bytearray(100)
    struct.pack_into(">i", header, 0, 9994)
    struct.pack_into(">i", header, 24, 64)  # 128 bytes / 2
    struct.pack_into("<i", header, 28, 1000)
    struct.pack_into("<i", header, 32, 1)
    struct.pack_into("<4d", header, 36, x, y, x, y)
    record = struct.pack(">2i", 1, 10) + struct.pack("<i2d", 1, x, y)
    return bytes(header) + record


def _point_dbf(name="A") -> bytes:
    header_len = 65
    record_len = 11
    data = bytearray(header_len + record_len)
    data[0] = 0x03
    struct.pack_into("<I", data, 4, 1)
    struct.pack_into("<H", data, 8, header_len)
    struct.pack_into("<H", data, 10, record_len)
    field = bytearray(32)
    field[:4] = b"NAME"
    field[11] = ord("C")
    field[16] = 10
    data[32:64] = field
    data[64] = 0x0D
    data[65] = 0x20
    data[66:76] = name.encode("utf-8").ljust(10, b" ")
    return bytes(data)


def _shp_zip(*, include_prj=True, include_dbf=True, include_cpg=True) -> bytes:
    files = {"points.shp": _point_shp()}
    if include_prj:
        files["points.prj"] = b"EPSG:4326"
    if include_dbf:
        files["points.dbf"] = _point_dbf()
    if include_cpg:
        files["points.cpg"] = b"UTF-8"
    return _zip(files, compression=zipfile.ZIP_STORED)


def _gpkg_point() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".gpkg") as fh:
        con = sqlite3.connect(fh.name)
        con.executescript(
            "PRAGMA application_id=1196437808;"
            "CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY, organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL, definition TEXT NOT NULL, description TEXT);"
            "INSERT INTO gpkg_spatial_ref_sys VALUES('WGS 84',4326,'EPSG',4326,'EPSG:4326','fixture');"
            "CREATE TABLE gpkg_geometry_columns(table_name TEXT, column_name TEXT, geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER);"
            "CREATE TABLE points(id INTEGER PRIMARY KEY, name TEXT, geom BLOB);"
            "INSERT INTO gpkg_geometry_columns VALUES('points','geom','POINT',4326,0,0);"
        )
        gpkg_header = b"GP\x00\x01" + struct.pack("<i", 4326)
        wkb = b"\x01" + struct.pack("<I2d", 1, -66.4, 18.2)
        con.execute("INSERT INTO points(name, geom) VALUES(?, ?)", ("A", gpkg_header + wkb))
        con.commit(); con.close()
        fh.seek(0)
        return fh.read()


def _assert_stage_conservation(receipt):
    assert receipt["stages"]["RAW"]["sha256"] == receipt["rawSha256"]
    assert receipt["stages"]["RAW"]["preserved"] is True
    assert receipt["stages"]["NORMALIZED"]["sha256"] == receipt["normalizedSha256"]
    assert receipt["stages"]["CANONICAL"] == {"status": "CANDIDATE_NOT_IDENTITY", "canonicalId": None}


def test_kml_gpx_and_kmz_actual_parsing():
    kml = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>A</name><Point><coordinates>-66.4,18.2,5</coordinates></Point></Placemark></kml>'
    fc, receipt = ingest_device_bytes("a.kml", kml)
    assert fc["features"][0]["geometry"]["coordinates"] == [-66.4, 18.2, 5.0]
    assert receipt["crs"] == "EPSG:4326"
    assert receipt["rawSha256"] != receipt["normalizedSha256"]
    _assert_stage_conservation(receipt)

    gpx = b'<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="18.2" lon="-66.4"><name>A</name></wpt><trk><trkseg><trkpt lat="18.2" lon="-66.4"/><trkpt lat="18.3" lon="-66.5"/></trkseg></trk></gpx>'
    fc, receipt = ingest_device_bytes("a.gpx", gpx)
    assert [f["geometry"]["type"] for f in fc["features"]] == ["Point", "LineString"]
    assert receipt["canonicalIdentityStatus"] == "CANDIDATE_NOT_IDENTITY"
    _assert_stage_conservation(receipt)

    kmz = _zip({"doc.kml": kml})
    fc, receipt = ingest_device_bytes("a.kmz", kmz)
    assert len(fc["features"]) == 1
    assert receipt["kmlMember"] == "doc.kml"
    assert len(receipt["kmlMemberSha256"]) == 64
    _assert_stage_conservation(receipt)


def test_shapefile_zip_binds_crs_dbf_schema_and_cpg_encoding():
    fc, receipt = ingest_device_bytes("points.zip", _shp_zip())
    assert fc["features"][0]["geometry"] == {"type": "Point", "coordinates": [-66.4, 18.2]}
    assert fc["features"][0]["properties"] == {"NAME": "A"}
    assert receipt["crs"] == "EPSG:4326"
    assert receipt["schema"] == ["NAME"]
    assert receipt["encoding"] == "UTF-8"
    assert receipt["encodingStatus"] == "EXPLICIT_CPG_BOUND"
    assert receipt["featureCount"] == 1
    _assert_stage_conservation(receipt)

    with pytest.raises(GisIngestionError, match="ambiguous SHP CRS"):
        ingest_device_bytes("points.zip", _shp_zip(include_prj=False))
    with pytest.raises(GisIngestionError, match="attribute schema unresolved"):
        ingest_device_bytes("points.zip", _shp_zip(include_dbf=False))
    with pytest.raises(GisIngestionError, match="encoding unresolved"):
        ingest_device_bytes("points.zip", _shp_zip(include_cpg=False))


def test_geopackage_actual_sqlite_geometry_and_srs_dictionary_parsing():
    fc, receipt = ingest_device_bytes("points.gpkg", _gpkg_point())
    assert fc["features"][0]["geometry"] == {"type": "Point", "coordinates": [-66.4, 18.2]}
    assert fc["features"][0]["properties"]["name"] == "A"
    assert receipt["crs"] == "EPSG:4326"
    assert receipt["featureTable"] == "points"
    assert receipt["gpkgApplicationId"] == 1196437808
    _assert_stage_conservation(receipt)


def test_malformed_and_archive_bomb_controls_fail_closed():
    with pytest.raises(GisIngestionError, match="malformed KML"):
        ingest_device_bytes("bad.kml", b"<kml><broken>")

    bomb = _zip({"doc.kml": b" " * (2 * 1024 * 1024)})
    with pytest.raises(GisIngestionError, match="compression ratio"):
        ingest_device_bytes("bomb.kmz", bomb)

    traversal = _zip({"../doc.kml": b"<kml/>"}, compression=zipfile.ZIP_STORED)
    with pytest.raises(GisIngestionError, match="unsafe archive member path"):
        ingest_device_bytes("bad.kmz", traversal)

    with pytest.raises(GisIngestionError, match="GeoPackage"):
        ingest_device_bytes("bad.gpkg", b"not sqlite")
