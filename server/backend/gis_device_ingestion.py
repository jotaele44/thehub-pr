"""Fail-closed device GIS ingestion for KML/KMZ/SHP ZIP/GPKG/GPX.

RAW bytes are hashed before parsing. Parsed/normalized geometry receives a
separate deterministic hash. Canonical identity is never inferred from format,
name, proximity, or successful parsing.
"""
from __future__ import annotations

import codecs
import hashlib
import io
import json
import math
import sqlite3
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

MAX_ARCHIVE_MEMBERS = 256
MAX_ARCHIVE_UNCOMPRESSED = 128 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200.0
GPKG_APPLICATION_ID = 0x47503130  # b"GP10": the real GeoPackage 1.0-1.2 SQLite application_id


class GisIngestionError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_hash(fc: dict[str, Any]) -> str:
    payload = json.dumps(fc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return _sha(payload)


def _receipt(fmt: str, raw: bytes, fc: dict[str, Any], *, crs: str | None, schema: list[str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_sha = _sha(raw)
    normalized_sha = _normalized_hash(fc)
    canonical_status = "CANDIDATE_NOT_IDENTITY"
    return {
        "format": fmt,
        "status": "PARSED_WITH_SCHEMA",
        "rawSha256": raw_sha,
        "normalizedSha256": normalized_sha,
        "rawByteLength": len(raw),
        "featureCount": len(fc["features"]),
        "crs": crs,
        "schema": sorted(schema),
        "canonicalIdentityStatus": canonical_status,
        "stages": {
            "RAW": {"sha256": raw_sha, "byteLength": len(raw), "preserved": True},
            "NORMALIZED": {
                "sha256": normalized_sha,
                "manifestation": "GEOJSON_FEATURE_COLLECTION",
                "featureCount": len(fc["features"]),
            },
            "CANONICAL": {"status": canonical_status, "canonicalId": None},
        },
        **(extra or {}),
    }


def _feature(geometry: dict[str, Any] | None, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties or {}}


def _parse_coords(text: str) -> list[list[float]]:
    out: list[list[float]] = []
    for token in text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        vals = [float(parts[0]), float(parts[1])]
        if len(parts) >= 3 and parts[2] != "":
            vals.append(float(parts[2]))
        if not all(math.isfinite(v) for v in vals):
            raise GisIngestionError("non-finite coordinate")
        out.append(vals)
    return out


def parse_kml(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GisIngestionError(f"malformed KML: {exc}") from exc
    features: list[dict[str, Any]] = []
    schema: set[str] = set()
    for pm in root.findall(".//{*}Placemark"):
        props: dict[str, Any] = {}
        name = pm.find("{*}name")
        if name is not None and name.text:
            props["name"] = name.text
            schema.add("name")
        point = pm.find("{*}Point/{*}coordinates")
        line = pm.find("{*}LineString/{*}coordinates")
        poly = pm.find("{*}Polygon/{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
        if point is not None and point.text:
            coords = _parse_coords(point.text)
            if len(coords) != 1:
                raise GisIngestionError("KML Point must contain exactly one coordinate")
            features.append(_feature({"type": "Point", "coordinates": coords[0]}, props))
        elif line is not None and line.text:
            coords = _parse_coords(line.text)
            if len(coords) < 2:
                raise GisIngestionError("KML LineString requires >=2 coordinates")
            features.append(_feature({"type": "LineString", "coordinates": coords}, props))
        elif poly is not None and poly.text:
            coords = _parse_coords(poly.text)
            if len(coords) < 4 or coords[0][:2] != coords[-1][:2]:
                raise GisIngestionError("KML Polygon ring must be closed")
            features.append(_feature({"type": "Polygon", "coordinates": [coords]}, props))
    fc = {"type": "FeatureCollection", "features": features}
    return fc, _receipt(
        "KML", raw, fc, crs="EPSG:4326", schema=list(schema),
        extra={"encodingStatus": "XML_DECLARATION_BOM_OR_UTF8"},
    )


def parse_gpx(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GisIngestionError(f"malformed GPX: {exc}") from exc
    features: list[dict[str, Any]] = []
    for wpt in root.findall(".//{*}wpt"):
        lat, lon = float(wpt.attrib["lat"]), float(wpt.attrib["lon"])
        coords: list[float] = [lon, lat]
        ele = wpt.find("{*}ele")
        if ele is not None and ele.text:
            coords.append(float(ele.text))
        props: dict[str, Any] = {}
        name = wpt.find("{*}name")
        if name is not None and name.text:
            props["name"] = name.text
        features.append(_feature({"type": "Point", "coordinates": coords}, props))
    for trkseg in root.findall(".//{*}trkseg"):
        seg_coords: list[list[float]] = []
        for pt in trkseg.findall("{*}trkpt"):
            vals: list[float] = [float(pt.attrib["lon"]), float(pt.attrib["lat"])]
            ele = pt.find("{*}ele")
            if ele is not None and ele.text:
                vals.append(float(ele.text))
            seg_coords.append(vals)
        if seg_coords:
            features.append(_feature({"type": "LineString", "coordinates": seg_coords}))
    fc = {"type": "FeatureCollection", "features": features}
    schema = sorted({k for f in features for k in f["properties"]})
    return fc, _receipt(
        "GPX", raw, fc, crs="EPSG:4326", schema=schema,
        extra={"encodingStatus": "XML_DECLARATION_BOM_OR_UTF8"},
    )


def _safe_zip(raw: bytes) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise GisIngestionError("malformed ZIP archive") from exc
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise GisIngestionError("archive member limit exceeded")
    total = 0
    for info in members:
        if info.is_dir():
            continue
        total += info.file_size
        if info.file_size > MAX_MEMBER_UNCOMPRESSED or total > MAX_ARCHIVE_UNCOMPRESSED:
            raise GisIngestionError("archive uncompressed-size limit exceeded")
        if info.compress_size == 0 and info.file_size:
            raise GisIngestionError("archive compression ratio unresolved")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise GisIngestionError("archive compression ratio limit exceeded")
        p = Path(info.filename)
        if p.is_absolute() or ".." in p.parts:
            raise GisIngestionError("unsafe archive member path")
    return zf


def parse_kmz(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    zf = _safe_zip(raw)
    kmls = [i for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith(".kml")]
    if len(kmls) != 1:
        raise GisIngestionError("KMZ requires exactly one KML manifestation")
    kml_raw = zf.read(kmls[0])
    fc, _ = parse_kml(kml_raw)
    receipt = _receipt(
        "KMZ", raw, fc, crs="EPSG:4326",
        schema=sorted({k for f in fc["features"] for k in f["properties"]}),
        extra={
            "kmlMember": kmls[0].filename,
            "kmlMemberSha256": _sha(kml_raw),
            "encodingStatus": "KML_XML_DECLARATION_BOM_OR_UTF8",
        },
    )
    return fc, receipt


def _parse_shp_bytes(data: bytes) -> list[dict[str, Any] | None]:
    if len(data) < 100 or struct.unpack(">i", data[:4])[0] != 9994:
        raise GisIngestionError("invalid SHP header")
    shape_type = struct.unpack("<i", data[32:36])[0]
    pos = 100
    geoms: list[dict[str, Any] | None] = []
    while pos + 8 <= len(data):
        _, content_words = struct.unpack(">2i", data[pos:pos + 8])
        size = content_words * 2
        content = data[pos + 8:pos + 8 + size]
        if len(content) != size or size < 4:
            raise GisIngestionError("truncated SHP record")
        rec_type = struct.unpack("<i", content[:4])[0]
        if rec_type == 0:
            geoms.append(None)
        elif rec_type == 1:
            if len(content) < 20:
                raise GisIngestionError("truncated SHP point")
            x, y = struct.unpack("<2d", content[4:20])
            geoms.append({"type": "Point", "coordinates": [x, y]})
        elif rec_type in (3, 5):
            if len(content) < 44:
                raise GisIngestionError("truncated multipart SHP record")
            num_parts, num_points = struct.unpack("<2i", content[36:44])
            parts_off = 44
            pts_off = parts_off + 4 * num_parts
            expected = pts_off + 16 * num_points
            if len(content) < expected:
                raise GisIngestionError("truncated SHP coordinate array")
            parts = list(struct.unpack(f"<{num_parts}i", content[parts_off:pts_off])) if num_parts else []
            pts = [list(struct.unpack("<2d", content[pts_off + 16*i:pts_off + 16*(i+1)])) for i in range(num_points)]
            ends = parts[1:] + [num_points]
            lines = [pts[s:e] for s, e in zip(parts, ends)]
            geoms.append({"type": "MultiLineString" if rec_type == 3 else "Polygon", "coordinates": lines})
        else:
            raise GisIngestionError(f"unsupported SHP shape type {rec_type}; declared {shape_type}")
        pos += 8 + size
    return geoms


def _parse_dbf(data: bytes, encoding: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(data) < 33:
        raise GisIngestionError("invalid DBF header")
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        raise GisIngestionError(f"unsupported DBF encoding from .cpg: {encoding}") from exc
    record_count = struct.unpack("<I", data[4:8])[0]
    header_len = struct.unpack("<H", data[8:10])[0]
    record_len = struct.unpack("<H", data[10:12])[0]
    if header_len < 33 or record_len < 1 or header_len > len(data):
        raise GisIngestionError("invalid DBF dimensions")
    fields: list[dict[str, Any]] = []
    pos = 32
    while pos + 32 <= header_len and data[pos] != 0x0D:
        desc = data[pos:pos + 32]
        name = desc[:11].split(b"\0", 1)[0].decode("ascii", "strict").strip()
        if not name:
            raise GisIngestionError("DBF field name is empty")
        fields.append({"name": name, "type": chr(desc[11]), "length": desc[16], "decimals": desc[17]})
        pos += 32
    if not fields:
        raise GisIngestionError("DBF schema is empty")
    if header_len + record_count * record_len > len(data):
        raise GisIngestionError("truncated DBF records")

    rows: list[dict[str, Any]] = []
    for idx in range(record_count):
        rec = data[header_len + idx * record_len:header_len + (idx + 1) * record_len]
        if not rec or rec[0:1] == b"*":
            raise GisIngestionError("deleted or missing DBF row cannot be silently dropped")
        cursor = 1
        row: dict[str, Any] = {}
        for field in fields:
            raw_value = rec[cursor:cursor + field["length"]]
            cursor += field["length"]
            text = raw_value.decode(encoding, "strict").strip()
            ftype = field["type"]
            if text == "":
                value: Any = None
            elif ftype in ("N", "F"):
                value = float(text) if field["decimals"] or "." in text else int(text)
            elif ftype == "L":
                upper = text.upper()
                value = True if upper in ("T", "Y") else False if upper in ("F", "N") else None
            else:
                value = text
            row[field["name"]] = value
        rows.append(row)
    return rows, fields


def parse_shapefile_zip(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    zf = _safe_zip(raw)
    names = [i.filename for i in zf.infolist() if not i.is_dir()]
    shp = [n for n in names if n.lower().endswith(".shp")]
    if len(shp) != 1:
        raise GisIngestionError("SHP ZIP requires exactly one .shp member")
    stem = str(Path(shp[0]).with_suffix(""))

    def matching(suffix: str) -> str | None:
        return next(
            (n for n in names if str(Path(n).with_suffix("")) == stem and n.lower().endswith(suffix)), None
        )

    prj = matching(".prj")
    dbf = matching(".dbf")
    cpg = matching(".cpg")
    if not prj:
        raise GisIngestionError("ambiguous SHP CRS: .prj is required")
    if not dbf:
        raise GisIngestionError("SHP attribute schema unresolved: .dbf is required")
    if not cpg:
        raise GisIngestionError("SHP encoding unresolved: .cpg is required")
    crs = zf.read(prj).decode("utf-8", "strict").strip()
    if not crs:
        raise GisIngestionError("ambiguous SHP CRS: .prj is empty")
    encoding = zf.read(cpg).decode("ascii", "strict").strip()
    geoms = _parse_shp_bytes(zf.read(shp[0]))
    rows, fields = _parse_dbf(zf.read(dbf), encoding)
    if len(geoms) != len(rows):
        raise GisIngestionError("SHP/DBF record-count conservation failure")
    fc = {"type": "FeatureCollection", "features": [_feature(g, row) for g, row in zip(geoms, rows)]}
    schema = [field["name"] for field in fields]
    return fc, _receipt(
        "SHP_ZIP", raw, fc, crs=crs, schema=schema,
        extra={
            "shpMember": shp[0], "prjMember": prj, "dbfMember": dbf, "cpgMember": cpg,
            "encoding": encoding, "encodingStatus": "EXPLICIT_CPG_BOUND",
            "fieldSchema": fields,
        },
    )


def _wkb(data: bytes, offset: int = 0) -> tuple[dict[str, Any], int]:
    if offset + 5 > len(data):
        raise GisIngestionError("truncated WKB")
    endian = data[offset]
    order = "<" if endian == 1 else ">" if endian == 0 else None
    if order is None:
        raise GisIngestionError("invalid WKB byte order")
    geom_type = struct.unpack(order + "I", data[offset + 1:offset + 5])[0] % 1000
    p = offset + 5
    if geom_type == 1:
        if p + 16 > len(data):
            raise GisIngestionError("truncated WKB Point")
        x, y = struct.unpack(order + "2d", data[p:p + 16])
        p += 16
        return {"type": "Point", "coordinates": [x, y]}, p
    if geom_type == 2:
        if p + 4 > len(data):
            raise GisIngestionError("truncated WKB LineString count")
        n = struct.unpack(order + "I", data[p:p + 4])[0]
        p += 4
        coords = []
        for _ in range(n):
            if p + 16 > len(data):
                raise GisIngestionError("truncated WKB LineString")
            x, y = struct.unpack(order + "2d", data[p:p + 16])
            p += 16
            coords.append([x, y])
        return {"type": "LineString", "coordinates": coords}, p
    if geom_type == 3:
        if p + 4 > len(data):
            raise GisIngestionError("truncated WKB Polygon count")
        nr = struct.unpack(order + "I", data[p:p + 4])[0]
        p += 4
        rings = []
        for _ in range(nr):
            if p + 4 > len(data):
                raise GisIngestionError("truncated WKB ring count")
            n = struct.unpack(order + "I", data[p:p + 4])[0]
            p += 4
            ring = []
            for _ in range(n):
                if p + 16 > len(data):
                    raise GisIngestionError("truncated WKB Polygon")
                x, y = struct.unpack(order + "2d", data[p:p + 16])
                p += 16
                ring.append([x, y])
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}, p
    raise GisIngestionError(f"unsupported WKB geometry type {geom_type}")


def _gpkg_geom(blob: bytes) -> tuple[dict[str, Any], int]:
    if len(blob) < 8 or blob[:2] != b"GP":
        raise GisIngestionError("invalid GeoPackage geometry header")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    envelope_doubles = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}.get(envelope_code)
    if envelope_doubles is None:
        raise GisIngestionError("invalid GeoPackage envelope code")
    srs_id = struct.unpack("<i" if flags & 1 else ">i", blob[4:8])[0]
    offset = 8 + envelope_doubles * 8
    if offset > len(blob):
        raise GisIngestionError("truncated GeoPackage envelope")
    geom, _ = _wkb(blob, offset)
    return geom, srs_id


def parse_gpkg(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.NamedTemporaryFile(suffix=".gpkg") as fh:
        fh.write(raw)
        fh.flush()
        try:
            con = sqlite3.connect(fh.name)
        except sqlite3.DatabaseError as exc:
            raise GisIngestionError("malformed GeoPackage SQLite container") from exc
        try:
            application_id = con.execute("PRAGMA application_id").fetchone()[0]
            if application_id != GPKG_APPLICATION_ID:
                raise GisIngestionError("SQLite container is not GeoPackage-bound by application_id")
            tables = con.execute("SELECT table_name, column_name, srs_id FROM gpkg_geometry_columns ORDER BY table_name").fetchall()
            if len(tables) != 1:
                raise GisIngestionError("GeoPackage parser requires exactly one feature table")
            table, geom_col, declared_srs = tables[0]
            if not str(table).replace("_", "").isalnum() or not str(geom_col).replace("_", "").isalnum():
                raise GisIngestionError("unsafe GeoPackage identifier")
            srs_row = con.execute(
                "SELECT organization, organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
                (declared_srs,),
            ).fetchone()
            if not srs_row:
                raise GisIngestionError("GeoPackage SRS dictionary is missing declared geometry CRS")
            organization, organization_id = srs_row
            crs = f"{organization}:{organization_id}" if organization and organization_id is not None else f"SRS_ID:{declared_srs}"
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
            rows = con.execute(f'SELECT * FROM "{table}"').fetchall()
            gi = cols.index(geom_col)
            features = []
            observed_srs: set[int] = set()
            for row in rows:
                if row[gi] is None:
                    features.append(_feature(None, {c: row[i] for i, c in enumerate(cols) if i != gi}))
                    continue
                geom, srs = _gpkg_geom(row[gi])
                observed_srs.add(srs)
                props = {c: row[i] for i, c in enumerate(cols) if i != gi}
                features.append(_feature(geom, props))
            if observed_srs and observed_srs != {int(declared_srs)}:
                raise GisIngestionError("GeoPackage geometry/header CRS contradicts gpkg_geometry_columns")
            fc = {"type": "FeatureCollection", "features": features}
            return fc, _receipt(
                "GPKG", raw, fc, crs=crs, schema=[c for c in cols if c != geom_col],
                extra={
                    "featureTable": table,
                    "geometryColumn": geom_col,
                    "gpkgApplicationId": application_id,
                    "declaredSrsId": declared_srs,
                    "encodingStatus": "SQLITE_TYPED_VALUES",
                },
            )
        except sqlite3.DatabaseError as exc:
            raise GisIngestionError(f"malformed GeoPackage schema: {exc}") from exc
        finally:
            con.close()


def ingest_device_bytes(filename: str, raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    ext = Path(filename).suffix.lower()
    if ext == ".kml":
        return parse_kml(raw)
    if ext == ".kmz":
        return parse_kmz(raw)
    if ext == ".gpx":
        return parse_gpx(raw)
    if ext == ".gpkg":
        return parse_gpkg(raw)
    if ext == ".zip":
        return parse_shapefile_zip(raw)
    raise GisIngestionError(f"unsupported device GIS format: {ext or '<none>'}")
