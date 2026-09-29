# Rejected preparation export — NOT executed

The first preparation used `git archive` and checked every extracted file against
its raw Git blob before execution. That check failed for `requirements-lock.txt`:
the archive contained CRLF bytes (1383 bytes), while the raw blob had LF (1319).
The assertion stopped preparation with exit 1 before any model or candidate ran.

`source-manifest.json` is the originally generated pre-check manifest. Its claim
of exact Git blob equality is explicitly **retracted** by
`failed-extraction.json`. The failed copy is retained, not silently replaced.
Do not use this directory for the fixed-source reproduction. The accepted copy
is `../frozen-original6-source-raw`, exported with `git ls-tree` / `git cat-file`.
This is a packaging/preparation failure, not a repair-model result.
