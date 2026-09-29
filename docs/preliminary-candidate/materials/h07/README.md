# Portable CredProof recheck bundle

From this directory, using ordinary Python 3.10+ (no Qwen dependencies):

    python -m agent_pilot.bundle recheck --bundle . --output recheck-01.json

The output path must be new. Candidate source is `current.py`; the original is
`original.py`. To inspect a changed candidate, edit only `current.py`, then use
a different output filename. The historical report becomes inapplicable after
an object change, but a fresh verdict can still be PASS, FAIL, or UNKNOWN.

This package contains the verifier source and fixed 13-test judge. It does not
contain model weights, .env files, raw private executions, or an inference server.
It requires an already prepared/probed isolation runtime. Select it using
`config/local-runtime.json` or a JSON path in `CREDPROOF_CONFIG`.
`config/runtime.example.json` contains portable defaults, not a recorded account
or an installed runtime. Copy the example to your own configuration and set its
runtime root/WSL settings for the prepared environment. No original checkout is
used. Configuration is not permission to execute a candidate outside isolation.
The runner verifies its probe receipt and runtime hashes; missing or changed
isolation produces UNKNOWN, never a host execution fallback. Recheck does not
download, install, start a model, or silently prepare/re-probe the environment.

The fixed judge checks runtime synthetic credential leakage and the constrained
tool response/authentication contract. It is not a general vulnerability proof,
nor evidence that an Agent diagnosed correctly or completed its whole task.
Current fresh validation cannot overwrite the historical task status.
Recheck reports three separate facts: `prior_report_applicable` binds the old
report to the current objects; `historical_evidence_integrity` checks only the
historical files listed by the supplied manifest; `validation` is the fresh
fixed-judge result. Missing or changed optional trace files are explicitly listed
but do not automatically fail the candidate. INTACT does not prove that every
original event was collected or that the supplied manifest is authentic.

The operator and bundled verifier/judge/isolation source must be trusted. Hashes
detect changes against the supplied manifest, but are not authentication. A party
that replaces both the verifier and its manifest can forge this package. Review
or independently pin the verifier source before executing a received bundle.
Do not treat arbitrary third-party bundles as trusted programs.

Configuration and requirements are archived explanatory material, not authority
to edit the judge or shrink its fixed matrix. Raw synthetic credentials exist
only in memory during recheck; output contains verdicts and reason codes only.
Published trace is a sanitized copy; do not assume this export is a general
real-secret discovery service. Only reviewed synthetic reliability runs apply.
Older bundles remain unchanged and can use their own bundled verifier. A newer
checkout refuses a bundle whose verifier bytes differ; it does not relax this
check to force compatibility or silently upgrade old material.

CLI exit codes: 0 exported/fresh PASS, 1 fresh FAIL, 2 fresh UNKNOWN/blocked,
3 invalid arguments, input, or output path. Existing files are never overwritten.
