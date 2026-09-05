"""Allowlisted same-origin transport for GIS providers.

This is deliberately not a generic URL proxy. A request is accepted only when
`source_id` is registered below and `target` stays inside one of that source's
frozen URL prefixes. The frontend preserves the target URL in its query receipt;
this route exists only to cross browser CORS / HTTPS→HTTP mixed-content barriers.
"""
from __future__ import annotations

import http.client
import re
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/gis", tags=["gis"])
_MAX_TEXT_BYTES = 32 * 1024 * 1024
_MAX_RANGE_BYTES = 1024 * 1024
_RANGE_RE = re.compile(r"^bytes=(\d+)-(\d*)$")
_MAX_PATH_DECODE_PASSES = 4


@dataclass(frozen=True)
class AllowedSource:
    prefixes: tuple[str, ...]


_ALLOWED: dict[str, AllowedSource] = {
    "pr-sige-municipios": AllowedSource(("https://sige.pr.gov/server/rest/services/MIPR/LimitesAdministrativos_v10/FeatureServer/0",)),
    "pr-sige-represas": AllowedSource(("https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1",)),
    "pr-sige-aeropuertos": AllowedSource(("https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/17",)),
    "pr-sige-helipuertos": AllowedSource(("https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/18",)),
    "pr-geodata-barrios-2015-simpl": AllowedSource(("http://geoserver2.pr.gov/geoserver/pr_geodata/wfs",)),
    "pr-geodata-barrios-2015": AllowedSource(("http://geoserver2.pr.gov/geoserver/pr_geodata/ows",)),
    "pr-geodata-municipios-2015": AllowedSource(("http://geoserver2.pr.gov/geoserver/pr_geodata/ows",)),
    "census-tigerweb-pr-state-2025": AllowedSource(("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0",)),
    "census-tigerweb-pr-municipios-2025": AllowedSource(("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1",)),
    "usgs-landsat-stac-sr": AllowedSource(("https://landsatlook.usgs.gov/stac-server", "https://landsatlook.usgs.gov/data/")),
    "copernicus-cdse-sentinel-2-l2a": AllowedSource(("https://stac.dataspace.copernicus.eu/v1",)),
    "noaa-pr-naip-2021-2023-stac": AllowedSource((
        "https://coast.noaa.gov/htdata/raster7/imagery/PR_NAIP_2021_9825/",
        "https://coastalimagery.blob.core.windows.net/digitalcoast/PR_NAIP_2021_9825/",
    )),
}


def _canonical_parts(url: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("target must be an absolute HTTP(S) URL")
    if parts.username or parts.password or parts.fragment:
        raise ValueError("userinfo and fragments are not allowed")
    path = parts.path
    for _ in range(_MAX_PATH_DECODE_PASSES):
        if "\\" in path or "\x00" in path or any(
            segment in {".", ".."} for segment in path.split("/")
        ):
            raise ValueError("dot-segments and ambiguous separators are not allowed")
        decoded = urllib.parse.unquote(path, errors="strict")
        if decoded == path:
            break
        path = decoded
    else:
        raise ValueError("target path exceeds the decoding bound")
    return parts


def _matched_source(
    source_id: str, target: str
) -> Optional[tuple[urllib.parse.SplitResult, urllib.parse.SplitResult]]:
    source = _ALLOWED.get(source_id)
    if source is None:
        return None
    try:
        target_parts = _canonical_parts(target)
    except ValueError:
        return None
    for prefix in source.prefixes:
        prefix_parts = _canonical_parts(prefix)
        same_origin = (
            target_parts.scheme == prefix_parts.scheme
            and target_parts.hostname == prefix_parts.hostname
            and (target_parts.port or (443 if target_parts.scheme == "https" else 80))
            == (prefix_parts.port or (443 if prefix_parts.scheme == "https" else 80))
        )
        if not same_origin:
            continue
        prefix_path = prefix_parts.path.rstrip("/")
        target_path = target_parts.path
        if target_path == prefix_path or target_path.startswith(prefix_path + "/"):
            return target_parts, prefix_parts
    return None


def _target_allowed(source_id: str, target: str) -> bool:
    return _matched_source(source_id, target) is not None


def _validated_range(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    match = _RANGE_RE.fullmatch(value)
    if not match:
        raise HTTPException(status_code=400, detail="invalid byte_range")
    start = int(match.group(1))
    end_text = match.group(2)
    end = int(end_text) if end_text else start + _MAX_RANGE_BYTES - 1
    if end < start or end - start + 1 > _MAX_RANGE_BYTES:
        raise HTTPException(status_code=400, detail="byte_range exceeds 1 MiB bound")
    return f"bytes={start}-{end}"


def _read_bounded(response, limit: int) -> bytes:
    body = response.read(limit + 1)
    if len(body) > limit:
        raise HTTPException(status_code=413, detail="upstream response exceeds bounded proxy limit")
    return body


@contextmanager
def _open_upstream(source_id: str, target: str, headers: dict[str, str], timeout: int):
    matched = _matched_source(source_id, target)
    if matched is None:
        raise ValueError("target is outside the registered GIS source boundary")
    target_parts, prefix_parts = matched
    connection_type = (
        http.client.HTTPSConnection
        if prefix_parts.scheme == "https"
        else http.client.HTTPConnection
    )
    hostname = prefix_parts.hostname
    if hostname is None:
        raise ValueError("registered GIS source is missing a hostname")
    connection = connection_type(hostname, port=prefix_parts.port, timeout=timeout)
    request_target = urllib.parse.urlunsplit(("", "", target_parts.path, target_parts.query, ""))
    try:
        connection.request("GET", request_target, headers=headers)
        upstream = connection.getresponse()
        try:
            yield upstream
        finally:
            upstream.close()
    finally:
        connection.close()


@router.get("/proxy")
def gis_proxy(
    source_id: str = Query(..., min_length=1, max_length=128),
    target: str = Query(..., min_length=1, max_length=8192),
    byte_range: Optional[str] = Query(None, max_length=64),
):
    if source_id not in _ALLOWED:
        raise HTTPException(status_code=404, detail="unregistered GIS source_id")
    if not _target_allowed(source_id, target):
        raise HTTPException(status_code=403, detail="target is outside the registered GIS source boundary")
    normalized_range = _validated_range(byte_range)
    headers = {"User-Agent": "thehub-pr-gis/2", "Accept": "*/*"}
    if normalized_range:
        headers["Range"] = normalized_range
    try:
        with _open_upstream(source_id, target, headers, timeout=45) as upstream:
            if 300 <= upstream.status < 400:
                raise HTTPException(status_code=502, detail="upstream redirects are not allowed")
            if normalized_range and upstream.status != 206:
                raise HTTPException(status_code=502, detail="upstream did not honor byte_range")
            limit = _MAX_RANGE_BYTES if normalized_range else _MAX_TEXT_BYTES
            body = _read_bounded(upstream, limit)
            response_headers = {}
            for source_name, response_name in (("Content-Range", "Content-Range"), ("Content-Length", "X-GIS-Upstream-Content-Length"), ("ETag", "X-GIS-Upstream-ETag"), ("Last-Modified", "X-GIS-Upstream-Last-Modified")):
                value = upstream.headers.get(source_name)
                if value:
                    response_headers[response_name] = value
            response_headers["X-GIS-Source-Id"] = source_id
            response_headers["X-GIS-Transport"] = "allowlisted-proxy"
            return Response(content=body, status_code=getattr(upstream, "status", 200), media_type=upstream.headers.get_content_type() if upstream.headers else "application/octet-stream", headers=response_headers)
    except HTTPException:
        raise
    except (http.client.HTTPException, TimeoutError, OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"upstream transport failure: {exc}") from exc
