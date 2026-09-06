# MCP API Deployment

The hosted MCP router (`server/backend/mcp_api.py`, mounted by
`server/backend/main.py`) is a standard ASGI app. Three deployment paths ship;
all serve the same endpoints (`/mcp/route`, `/mcp/capabilities`,
`/mcp/metrics`, `/healthz`, `/readyz`).

Adapter credentials are always sourced from the environment at runtime (see
`config/.env.example`) — never baked into the image or committed.

## Deployment invariant: diagnostic (no-auth) mode must never bind past loopback

This build ships with no login (`/api/auth/me` always 401s, `requires_auth` is
always `false`). The only thing standing between a network caller and a write
to `data/hub.db` is `PRII_WRITE_TOKEN` — and when it is unset, writes are
served to *any* local-network caller (loopback, RFC1918 private, link-local;
see `require_write_access` / `_is_local_network` in
`server/backend/main_core.py`). Publishing port 8000 to a public interface
without first setting `PRII_WRITE_TOKEN` exposes anonymous create/update/
**delete**/bulk-overwrite of every collection backing the UI. Both deployment
paths below default to loopback-only for this reason; widen the bind only
after `PRII_WRITE_TOKEN` is configured.

## Docker

```bash
docker build -t thehub-mcp .
docker run --rm -p 127.0.0.1:8000:8000 \
  -e MCP_CONTRACTS_API_KEY=... -e MCP_REGULATIONS_API_KEY=... \
  thehub-mcp
curl localhost:8000/healthz     # {"status":"ok"}
curl localhost:8000/readyz      # {"status":"ready"}
```

The image runs as a non-root user and declares a `HEALTHCHECK` against
`/healthz`. `git` is installed for the `github-bridge` live `fetch` action.

## Docker Compose

```bash
docker compose up --build
```

The `thehub` service publishes `127.0.0.1:8000:8000` (loopback-only — see the
invariant above), mounts `./data` for the SQLite store / aggregate outputs,
and restarts unless stopped. To supply credentials, copy
`config/.env.example` to `config/.env` and uncomment the `env_file` block in
`docker-compose.yml`.

## systemd (non-container host)

```bash
python -m venv /opt/thehub-pr/.venv
/opt/thehub-pr/.venv/bin/pip install -e "/opt/thehub-pr[server]"
sudo cp deploy/thehub-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now thehub-mcp
```

Put credentials in `/etc/thehub-pr/thehub.env` (referenced by the unit's
`EnvironmentFile`), mode `0600`.

## Health & readiness

- `GET /healthz` — process liveness (always `ok` when serving).
- `GET /readyz` — `ready` once the capability registry is loaded and at least
  one adapter is registered; `503` otherwise. Use it as the readiness gate in
  an orchestrator.

## Not covered here

Multi-replica orchestration (Kubernetes manifests), TLS termination, and an
external metrics/tracing backend are out of scope; the app exposes `/readyz`
and `/mcp/metrics` so a platform layer can drive them.
