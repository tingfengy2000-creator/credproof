# R3 part B evidence

Base: `2a94ef8d6777676aba22e3ed68c23817c5f6aed2`.
Branch: `feat/linux-runtime-5090`.

This directory separates software/protocol tests from real WSL namespace and
project execution. No model calls are made. The original model/bench records
are not changed. Dependency sources record official wheel bytes, not weights.

The initial fresh setup failed because system python3.12-venv was missing.
Its partial directory was preserved, not resumed. Installing the official
Ubuntu venv package is host preparation; subsequent setup/checks run non-root.
The original model runtime was not modified. Raw receipts will record actual
commands, failures, versions, code identity and final results.

Docker/AppArmor and native non-WSL Ubuntu have not been executed on this host:
there is no available Docker executable here. Those contract §6 items remain
pending real validation; candidate profile JSON tests are not substitutes.
C is not started in this PR. Its two hosted jobs must wait for A+B integration.

PR #11 Windows review: Python 3.12.14, pytest 8.4.2, jsonschema 4.26.0;
15 format tests passed, no skip. This is software validation of A at its exact
head SHA, not model or container safety evidence. The review requests factual
wording corrections; B does not silently modify A's implementation.
