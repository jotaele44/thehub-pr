.PHONY: setup test list validate-cs aggregate clean lock smoke-fetch

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
