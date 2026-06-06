.PHONY: setup test list validate-cs aggregate clean

PY ?= python3

setup:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

list:
	$(PY) -m hub list --registry registry/producers.yaml

# Validate the Contract-Sweeper federation.json from a sibling checkout.
validate-cs:
	$(PY) -m hub validate-manifest ../Contract-Sweeper/federation.json

# Aggregate any producer export packages found under the parent workspace.
aggregate:
	$(PY) -m hub aggregate --root .. --out data/aggregate

clean:
	rm -rf data/aggregate/*.jsonl data/aggregate/graph_summary.json
