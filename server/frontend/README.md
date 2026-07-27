# TheHub PR Frontend

This frontend has been detached from the proprietary app-builder runtime and now targets the PRII federation backend layer.

## Backend target

| Field | Value |
|---|---|
| Program id | `thehub-pr` |
| Canonical backend repo | `jotaele44/thehub-pr` |
| Frontend role | Federation hub control-plane frontend |
| Runtime client | `src/api/federationClient.js` |

## Runtime configuration

```bash
cp .env.example .env.local
VITE_HUB_API_BASE_URL=http://localhost:8000/api
VITE_FEDERATION_PROGRAM_ID=thehub-pr
VITE_FEDERATION_MODE=diagnostic
```

## Backend endpoints

`src/api/federationClient.js` is written against the full federation contract, but
`server/backend/main.py` implements a subset. Verified against a running server:

| Endpoint | Implemented? |
|---|---|
| `GET /api/health`, `GET /health` | yes |
| `GET /api/apps/public-settings` | yes — reports `requires_auth: false`, `mode: diagnostic` |
| `GET /api/auth/me` | yes, but always **401** in diagnostic mode |
| `GET /api/entities/:entity` | yes |
| `POST /api/entities/:entity/filter` | yes (a read, despite the verb) |
| `POST /api/entities/:entity` | yes — **write-guarded** |
| `PATCH /api/entities/:entity/:id` | yes — **write-guarded** |
| `DELETE /api/entities/:entity/:id` | yes — **write-guarded** |
| `POST /api/entities/:entity/bulk` | yes — **write-guarded** |
| `GET /api/notifications` | yes |
| `POST /api/notifications/ack`, `PUT /api/notifications/preferences` | yes — **write-guarded** |
| `POST /api/functions/:name/invoke` | yes |
| `/api/agents/*`, `/api/integrations/*` | yes |
| `POST /api/files/upload` | yes, returns a diagnostic stub |
| `GET /api/connectors/:name/connection` | yes, hardcoded `not_connected` |
| `POST /api/auth/login` | **no — 404** |
| `POST /api/auth/register` | **no — 404** |
| `POST /api/auth/verify-otp`, `/auth/resend-otp`, `/auth/password/*` | **no — 404** |

### Authentication

There is no authentication backend. Because the six `/auth/*` endpoints the client
calls all return 404, the `/login`, `/register`, `/forgot-password` and
`/reset-password` routes are **not rendered** while
`public_settings.requires_auth` is false — `src/App.jsx` redirects them to `/`.
The pages remain in the tree; set `VITE_FEDERATION_REQUIRE_AUTH=true`, or have the
backend report `requires_auth: true`, and they come back. Do not re-enable them
without an authenticating backend, or you are shipping a sign-in form that cannot
succeed.

### Write authorization

Mutating routes are guarded by `require_write_access` in `server/backend/main.py`:

- `PRII_WRITE_TOKEN` **set** → every mutating request needs `Authorization: Bearer <token>`
- `PRII_WRITE_TOKEN` **unset** → writes are served to local-network clients
  (loopback, RFC1918 private, link-local) and refused for public addresses

Reads are never affected. Note that with the token set, this UI cannot currently
supply it — `federationClient` carries only the federation access token, and
`AuthContext` drops that when `/api/auth/me` 401s. Token mode therefore suits
API/CLI callers today; see `docs/MATURITY_AUDIT.md` for the tracked fix.

## Development

```bash
npm install
npm run lint
npm run build
```

## Migration status

Removed proprietary runtime packages, generated config folders, app-builder branding, function shims, and direct SDK imports. This app now relies on the backend repository and the Hub federation contract for data, authentication, functions, and review operations.
