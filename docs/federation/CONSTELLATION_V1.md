# Federation Constellation v1

`/constellation` draws the seven federation apps as one animated graph. It follows the
"code constellation" flythrough videos: a dark starfield, ring-dot nodes with two-line
monospace labels (`name` / `repo · path`), edges keyed by a legend with pulses travelling
along them, and a camera that flies from stage to stage. Each stage has a two-tone English
caption with a Spanish subtitle.

A **Code | Content** toggle switches between two lenses on the same graph:

- **Code** draws the program components of each app and how they hand work along.
- **Content** draws the records those components move, with real counts and real sample
  rows from the Hub store.

The app anchors are shared, so toggling morphs the graph in place. A selection crosses
lenses through lineage.

## API

`GET /api/constellation` (`server/backend/constellation_api.py`, over `hub.constellation`,
contract `federation-constellation-v1`). It is read-only and takes no parameters. The
response has these fields:

| Field | Contents |
|---|---|
| `apps` | The seven apps: id, program id, name, domain, home stage and registry status from `registry/producers.yaml` |
| `stages` | The tour in order. Each stage has an English title (`lead` plus a highlighted `accent`), a Spanish subtitle, a summary, and the node ids it frames in each lens (`focus.code`, `focus.content`) |
| `lenses.code` | Component nodes and `call` / `handoff` / `result` edges, plus the legend |
| `lenses.content` | Stream, Hub-stream, correlation-strategy, UI-collection and seam nodes, with `flow` / `correlation` / `projection` edges, plus the legend |
| `links` | `{code, content}` pairs that join the two lenses |
| `store_status` | `AVAILABLE`, or `EMPTY` when the Hub store holds no canonical rows |
| `totals` | `exported` (graph_summary), `stored` (rows in this store), `correlations` |

## The spec

`registry/constellation.v1.json` holds everything that is not data. It lives under
`registry/` because the Docker image and the desktop bundle both ship that directory. It
declares:

- the stage tour;
- the code components of each app (`id, app, name, path, kind, stage, summary`);
- the code edges, with an optional `artifact`, `contract` and seam `status`
  (`dormant` or `manual`, drawn dashed);
- the six correlation strategies and how stored correlation rows map onto them;
- the UI collections that ingest projects;
- the declared seams that hold no rows in the Hub store.

`tests/test_constellation.py` keeps the spec true to the repo:

- App ids and names match the federation manager catalog, and program ids match
  `registry/producers.yaml`.
- Every Hub component path exists on disk, except `data/hub.db`, which is marked
  `generated`.
- Every sibling-repo component cites a Hub document or data file (`cites.doc`) that
  contains its `cites.mentions` text. Editing `docs/FOUR_REPO_PIPELINE_LOGIC.md` so that a
  cited path disappears fails the test.
- Every cross-app `handoff` is a declared edge in `governance/federation_dependencies.yaml`.
  Runtime RPC between producers is forbidden there, so the legend reads CALL · HANDOFF ·
  RESULT rather than RPC.
- Package paths follow each producer's registry `export_path`.
- Correlation strategy functions exist in `src/hub/correlate.py`.
- `projections` agree with `hub.ingest`.
- This document names every stage title.

To show a new component, add it to the spec with a citation, and add its edges. The page
needs no change.

## The stages

| # | Title | Subtitle | Frames |
|---|---|---|---|
| 1 | SIGNAL INTAKE | Captura de señales · Centinelas | Centinelas ingest, classify, route and dispatch, and its streams |
| 2 | FINANCE ANCHOR | Ancla financiera · MoneySweep | MoneySweep's Centinelas intake lane and its streams |
| 3 | SPATIAL SCORING | Puntuación espacial · Spiderweb | The contract-finance bundle (manual transport) and Spiderweb's scoring |
| 4 | DOMAIN PRODUCERS | Productores de dominio · OVNIS, AguaYLuz, Skywatcher | Their declared hub-callable commands and their streams |
| 5 | CANONICAL EXPORTS | Paquetes canónicos hacia TheHub | Each producer's `federation_export.py` and package, and every record flow into the Hub |
| 6 | HUB AGGREGATE | Agregación y validación | fetch, validate and aggregate, and the Hub's aggregate streams |
| 7 | CROSS-PRODUCER CORRELATION | Correlación entre productores | The six correlation strategies and their candidates |
| 8 | INGEST & SERVE | Ingesta y servicio | `ingest_aggregate`, `hub.db`, the read APIs and the UI collections |
| 9 | THE FEDERATION | La federación completa | Everything |

A stage frames only its own nodes. An edge to another stage leaves the frame, which is how
handoffs read on screen.

## Rules

- **Counts are the store's.**
  - `total` is the producer's exported row count from `graph_summary`.
  - `stored` is the number of rows this Hub store holds. The committed aggregate is a bounded
    sample, so both are shown.
  - Seams with no rows in the store show their declared status and no count.
- **Sample records are stored rows.** Each one is trimmed to an id, a label, a type, a
  municipality and a date, and links to its Evidence Object at `/evidence/{collection}/{id}`.
- **Correlations are candidates.**
  - Every Hub correlation is `synthetic` and adjudicated only as a CANDIDATE, and the page
    says so.
  - A pair edge joins the producer streams of both endpoints. Correlation rows carry no
    `_producers`, so each endpoint is resolved through its own stored row.
- **The lenses join only through recorded lineage.** A content node links to the
  component whose `path` matches its rows' `lineage.producer_script` for that app, or to a
  component that declares it in `produces`. Nothing else links the two.

## The page

- **Tour.** The tour autoplays: a camera flight, then a dwell, for each stage. Play, Pause,
  Previous, Next and the numbered stage buttons drive it.
- **Exploring.** Dragging, scrolling or pinching, or selecting a node, pauses the tour and
  hands the camera to the viewer. Play resumes it.
- **Keyboard.** With the stage focused:
  - Space plays or pauses;
  - ← and → change stage;
  - L switches lens;
  - + and − zoom;
  - F fits the stage;
  - Esc clears the selection.
- **Details panel.** It shows the stage, or the selected node's connections, counts,
  lineage and sample records. It also offers the node's counterparts in the other lens.
- **Node list.** The list of nodes in the stage is the non-visual equivalent of the
  canvas.
- **Deep links.** The URL records the lens, stage and selected node:
  `/constellation?lens=content&stage=hub-aggregate&node=…`. A deep link opens paused.
- **Reduced motion.** It is honoured in JavaScript: no autoplay, no pulses or record
  particles, and the camera jumps instead of flying.
- **Colours.** Every colour comes from tokens: the `--constellation-*` tokens in
  `server/frontend/src/index.css`, and each app's `--fd-accent` from the federation design
  layer. The stage is a dark surface in both themes.
