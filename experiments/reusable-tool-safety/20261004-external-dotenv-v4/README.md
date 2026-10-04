# External python-dotenv v1.2.2 — final isolated recheck for dev.4

Source: `https://github.com/theskumar/python-dotenv`, fixed ref `v1.2.2`, commit `36004e0e34be7665ff2b11a8a4005144f76f176d`, BSD-3-Clause. The directory defect is an explicitly artificial change in a disposable copy; it is not an upstream vulnerability or CVE.

The runner stages the tracked snapshot outside the CredProof checkout and runs four independent copies: `before`, `after`, `reintroduced_defect`, and `unrelated_change`. The 2026-10-04 run after refreshing the reviewed isolation probe produced `FAIL`, `PASS`, `FAIL`, and `PASS`; each upstream pytest run exited 0. See [summary.json](summary.json) for all required checks, audit events, and limitations.

```powershell
python scripts/run-external-dotenv-case.py --output _runs/external-dotenv-outside-v4
```

This is one external project and one supported directory-read category. It is not a generalisation or a deployment claim.
