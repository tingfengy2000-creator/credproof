# External python-dotenv v1.2.2 — isolated reusable check

This record uses the tracked upstream snapshot at commit `36004e0e34be7665ff2b11a8a4005144f76f176d` under the BSD-3-Clause license. The boundary defect is explicitly injected in `credproof_entry.py` inside a disposable copy; it is not an upstream vulnerability or CVE.

The runner stages the fixture outside the CredProof checkout and evaluates four independent copies:

- `before`: injected directory-boundary defect;
- `after`: constrained adapter;
- `reintroduced_defect`: defect reintroduced after the fixed copy;
- `unrelated_change`: fixed copy with an unrelated note file.

Run from the repository root:

```powershell
python scripts/run-external-dotenv-case.py --output _runs/external-dotenv-outside-v3
```

The 2026-10-04 run produced `before=FAIL`, `after=PASS`, `reintroduced_defect=FAIL`, and `unrelated_change=PASS`, with upstream pytest exit code 0 in each case. The full machine-readable record is [summary.json](summary.json). The temporary copies are not committed. This is one external project and one supported directory-read category, not a generalisation or a deployment claim.
