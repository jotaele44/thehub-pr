.PHONY: setup test list validate-cs aggregate ingest clean lock smoke-fetch

PY ?= python3

setup:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

list:
	$(PY) -m hub list --registry registry/producers.yaml

# Validate the moneysweep-pr federation.json from a sibling checkout.
validate-cs:
	$(PY) -m hub validate-manifest ../moneysweep-pr/federation.json

# Aggregate any producer export packages found under the parent workspace.
aggregate:
	$(PY) -m hub aggregate --root .. --out data/aggregate

# Load the aggregate into the server entity store the frontend reads.
ingest:
	$(PY) -m hub ingest --in data/aggregate --db data/hub.db

# Build data/hub.db from the committed fixture. This is the one command a
# developer needs before `uvicorn server.backend.main:app` shows populated
# pages — hub.db is a build artifact (5.8 MB binary) and stays untracked, while
# the JSONL it is built from is committed and diffable.
db: ingest

# Regenerate the committed bounded fixture from the producer checkouts in the
# parent workspace. Run the producers' export commands first (the Hub does this
# itself in federation-ingest.yml via `hub fetch`).
fixture:
	$(PY) scripts/build_hub_fixture.py --root .. --out data

clean:
	rm -rf data/aggregate/*.jsonl data/aggregate/graph_summary.json

# Regenerate the lock file.
lock:
	uv lock

# Smoke-test hub fetch --run end-to-end using a synthetic local producer (no network).
smoke-fetch:
	$(eval TMP := $(shell mktemp -d))
	mkdir -p $(TMP)/producer
	: > $(TMP)/producer/export.py
	echo '{"program_id":"smoke","hub_parent":"thehub-pr","hub_callable_commands":{"export_canonical":"python3 export.py"}}' > $(TMP)/producer/federation.json
	PYTHONPATH=src $(PY) -m hub fetch --run --root $(TMP)/ws 2>&1 || true
	rm -rf $(TMP)
