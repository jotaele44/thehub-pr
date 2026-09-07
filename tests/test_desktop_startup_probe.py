from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, Response

SPEC = importlib.util.spec_from_file_location(
    "desktop_probe", Path(__file__).resolve().parents[1] / "scripts/desktop_startup_probe.py"
)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def application(script_response=True, external_redirect=False):
    app = FastAPI()

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/')
    def index():
        return HTMLResponse('<html><script type="module" src="/assets/main.js"></script></html>')

    @app.get('/assets/main.js')
    def javascript():
        if external_redirect:
            return RedirectResponse('https://example.invalid/remote.js')
        if not script_response:
            return HTMLResponse('<html>SPA fallback</html>')
        return Response('document.body.dataset.loaded = "true";', media_type='text/javascript')

    return app


def test_real_server_and_asset_delivery_still_not_operator_certification():
    result = probe.probe(application(), '/health', timeout=5)
    assert result['state'] == 'PASS'
    assert result['operator_journey'] == 'UNVERIFIED'
    assert result['certification'] == 'AUDIT_ONLY'
    assert [row['path'] for row in result['requests']] == ['/health', '/', '/assets/main.js']
    assert all(len(row['sha256']) == 64 for row in result['requests'])


def test_spa_fallback_cannot_masquerade_as_javascript():
    with pytest.raises(ValueError, match='shadowed'):
        probe.probe(application(script_response=False), '/health', timeout=5)


def test_external_redirect_rejected_before_following():
    with pytest.raises(ValueError, match='redirect outside'):
        probe.probe(application(external_redirect=True), '/health', timeout=5)


def test_health_cannot_target_external_origin():
    with pytest.raises(ValueError, match='local'):
        probe.probe(application(), '//remote/health')
