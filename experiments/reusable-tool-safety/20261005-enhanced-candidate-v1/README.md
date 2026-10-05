# Enhanced preliminary candidate evidence — 2026-10-05

This directory records the finite integration checks for the enhanced preliminary candidate. It is a development evidence record, not a new Agent benchmark and not a claim of general security coverage.

## Environment and commands

- Source checkout: `feat/reusable-tool-safety` (version `0.3.0-dev.10` in the working tree before the delivery commit).
- Tests: `.venv/Scripts/python.exe -m unittest discover -s tests -v` and `.venv/Scripts/python.exe -m unittest discover -s agent_pilot/tests -v`.
- Exported regression: `.venv/Scripts/python.exe scripts/run-exported-regression-check.py --output _runs/exported-regression-enhanced-v3`.
- Safety demo: `.venv/Scripts/python.exe scripts/run-reusable-safety-demo.py --output _runs/reusable-safety-demo-enhanced-v1`.
- External component record: `.venv/Scripts/python.exe scripts/run-external-dotenv-case.py --output _runs/external-dotenv-enhanced-v1`.
- Startup smoke: local view-mode server on loopback; requests include the required same-origin headers. No model was called.

## Results

- Core unit tests: 33 tests, exit 0.
- Agent/runtime tests: 98 tests, exit 0.
- Exported consumer regression: three generated consumer reports were checked in addition to pytest/JUnit. Fixed and unrelated copies report `PASS`; the reintroduced file-read defect reports `FAIL` with `no_forbidden_file_read`. Process exit 0 means the expected security regression was observed and verified, not that all three inputs passed.
- Reusable safety demo: vulnerable `FAIL`, fixed `PASS`, reintroduced file bypass `FAIL`.
- External python-dotenv record: `before=FAIL`, `after=PASS`, `reintroduced=FAIL`, `unrelated=PASS`; this is a controlled external component record and does not use the model.
- Startup smoke: index, health, bootstrap and project-mode endpoints returned HTTP 200 with non-empty bodies in view mode.

The JSON files are the machine-readable records. Historical Agent runs and the complete prior batch remain in their original versioned directories; this finite record does not overwrite them.
