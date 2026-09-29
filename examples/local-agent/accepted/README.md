# Portable CredProof recheck bundle

From this directory, using ordinary Python 3.10+ (no Qwen dependencies):

    python -m agent_pilot.bundle recheck --bundle . --output recheck-01.json

The output path must be new. Candidate source is `current.py`; the original is
`original.py`. To inspect a changed candidate, edit only `current.py`, then use
a different output filename. The historical report becomes inapplicable after
an object change, but a fresh verdict can still be PASS, FAIL, or UNKNOWN.

This package contains the verifier source and fixed 13-test judge. It does not
contain model weights, .env files, raw private executions, or an inference server.
It requires the already prepared/probed isolation runtime: on Windows, WSL
Ubuntu-24.04, user tingfeng; Linux profile at
`/home/tingfeng/credproof-agent-runtime/isolation`. No original checkout is used.
The runner verifies its probe receipt and runtime hashes; missing or changed
isolation produces UNKNOWN, never a host execution fallback. Recheck does not
download, install, start a model, or silently prepare/re-probe the environment.

The fixed judge checks runtime synthetic credential leakage and the constrained
tool response/authentication contract. It is not a general vulnerability proof,
nor evidence that an Agent diagnosed correctly or completed its whole task.
Current fresh validation cannot overwrite the historical task status.

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

CLI exit codes: 0 exported/fresh PASS, 1 fresh FAIL, 2 fresh UNKNOWN/blocked,
3 invalid arguments, input, or output path. Existing files are never overwritten.
