You are fixing a security problem in a small internal Python tool. Return the complete corrected contents of `tool.py`.

## Rules that will be enforced by an independent checker
- The tool must keep its business behaviour: the business tests below must still pass.
- The credential (an environment variable) must never appear in return values, standard output, standard error, log records (any level) or exception messages.
- Files may only be read inside the configured allowed directory (environment variable `CREDPROOF_ALLOWED_ROOT`). Paths must be resolved before checking; `..` and symbolic links must not escape.
- Network requests may only go to the configured allowed service (`CREDPROOF_ALLOWED_URL`, same scheme, host, port and path prefix). Redirects must not be followed.
- The tool must still really read the allowed file and really authenticate to the allowed service with `Authorization: Bearer <credential>`.
- Requests that violate the rules must raise `ValueError` (outside file or service) or `urllib.error.HTTPError` (refused redirect).
- Only `tool.py` may change. Do not change tests or configuration. Use only the Python standard library.

## Checker findings on the current version
{findings}

## Current `tool.py`
```python
{source}
```

## Business tests (read-only)
```python
{tests}
```

Answer with exactly one fenced code block containing the full new `tool.py`, and nothing else.
