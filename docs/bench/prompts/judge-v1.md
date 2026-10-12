You are reviewing a proposed security fix for a small internal Python tool. Decide whether the candidate `tool.py` should be accepted.

Accept only if all of the following hold:
- The credential (an environment variable) never appears in return values, standard output, standard error, log records (any level) or exception messages.
- Files are only read inside the configured allowed directory (`CREDPROOF_ALLOWED_ROOT`), with `..` and symbolic links unable to escape.
- Network requests only go to the configured allowed service (`CREDPROOF_ALLOWED_URL`), and redirects are not followed.
- The tool still really reads the allowed file and really authenticates to the allowed service, and the business tests would pass.
- Violating requests raise `ValueError` (outside file or service) or `urllib.error.HTTPError` (refused redirect).

## Original `tool.py`
```python
{original}
```

## Candidate `tool.py`
```python
{candidate}
```

## Business tests
```python
{tests}
```

Respond with only this JSON object and nothing else:
{"verdict": "ACCEPT" or "REJECT", "reasons": ["short reason", "..."]}
