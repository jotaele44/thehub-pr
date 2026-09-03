# Offline Validation Status

Vector: `RUN_THEHUB_STRICT_SCHEMA_VALIDATION_LOCAL_v1`

## Current status

Runtime validation could not be executed in this environment because the execution container cannot resolve `github.com` for branch checkout.

Observed clone failure:

```text
Could not resolve host: github.com
```

## Static Hub patch status

Implemented on `gpt/offline-operator-model-v1`:

- strict Hub schema authority set
- strict cross-file package validator
- max-acceptable source vocabulary wrapper
- `Makefile.offline` wired to the max validator

## Required local validation

```bash
cd ~/Developer/thehub-pr
git checkout gpt/offline-operator-model-v1
make -f Makefile.offline offline
```

Then run the six producer exports and Hub workspace validation:

```bash
cd ~/Developer/thehub-pr
make -f Makefile.offline federation-hub-validate
```

Patch producers only if the Hub validator reports invalid export fields.
