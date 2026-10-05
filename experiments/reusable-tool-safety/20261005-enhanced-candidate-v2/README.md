# Enhanced preliminary candidate evidence v2 — 2026-10-05

This record covers the thin project-entry integration and the structured exported-regression correction. It is a controlled development check, not a new benchmark and not a claim of general deployment.

## Actual commands

- `.venv/Scripts/python.exe -m unittest discover -s tests -v` — 33 core tests, exit 0.
- `.venv/Scripts/python.exe -m unittest discover -s agent_pilot/tests -v` — 98 runtime/web tests, exit 0 on the complete rerun. One earlier suite invocation had one connection-level error in `test_host_origin_body_and_path_restrictions_never_launch`; the test passed in isolation and in the complete rerun. The earlier log is retained as `../20261005-enhanced-candidate-v1/agent-tests.txt`.
- `node --check agent_pilot/ui/app.js` — exit 0.
- `.venv/Scripts/python.exe scripts/run-exported-regression-check.py --output _runs/exported-regression-enhanced-v4` — exit 0. The fixed and unrelated copies pass; the reintroduced defect fails pytest and produces a new report with `no_forbidden_file_read`. The three case JSON files retain stdout, stderr, JUnit XML, complete generated report content and structured counts.
- `.venv/Scripts/python.exe scripts/run-reusable-safety-demo.py --output _runs/reusable-safety-demo-enhanced-v2` — vulnerable FAIL, fixed PASS, reintroduced file bypass FAIL.
- `python -m agent_pilot.launch --demo --mode recheck` — `/api/project/modes`, project selection and both registered projects were exercised. The original synthetic assistant returned FAIL; the prepared fixed copy returned PASS. The fixed project export endpoint returned a 2,226-byte ZIP with `PK` magic and no model call.
- New venv package check: installed `credproof_safety-0.3.0.dev11` into `C:\Users\Public\credproof-enhanced-clean-dev11a\venv`, installed pytest/requests, and ran `credproof-safety --help` (exit 0), `init` (exit 0), `check` on a clean consumer (exit 0, generated report PASS), `export-tests` (exit 0), and pytest on a fresh consumer after replacing the old generated wrapper (exit 0, 1 passed). The first attempt with the fixture's pre-existing generated wrapper is retained as an environment/setup failure: it produced UNKNOWN because the duplicate wrapper was not declared optional. The clean procedure is in `clean-package-recheck.py`.

## What the page now does

The project section lists only projects registered at process start (`--demo` gives two reviewed synthetic examples; a real user can pass `--project-config <authorized>/credproof.toml`). The browser can request a scope view, a new no-model isolated check, or an exported regression. It cannot submit an arbitrary path, command, URL, source file or verdict. The check is the same `credproof_safety.project.check_project()` implementation used by the CLI. A previous report is shown as applicable only when the current project tree identity is unchanged.

## Evidence status

`project-entry-first-run.json` preserves the original problem result. `project-entry-check.json` preserves both problem and fixed results. `project-entry-export.json` preserves the actual export response size and ZIP signature. Historical Agent and external-component records remain in their prior directories; this v2 record does not overwrite or relabel them.

Dynamic execution still requires the prepared WSL/bubblewrap runtime. The project entry never falls back to host execution. The existing video includes a real no-model recheck but predates this thin project-entry UI; `docs/preliminary-candidate/video/README.md` states that boundary instead of pretending the old video contains the new buttons.
