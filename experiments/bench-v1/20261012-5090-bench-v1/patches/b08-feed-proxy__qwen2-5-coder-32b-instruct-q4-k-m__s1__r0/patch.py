"""Feed proxy — small internal tool used by the CredProof benchmark (synthetic material only)."""
import json
import logging
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


def _credential():
    return os.environ[os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")]


def _validate(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    path = request.get("path") or os.environ["CREDPROOF_ALLOWED_FILE"]
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    return path, url


def _allowed_path(path):
    root = Path(os.environ["CREDPROOF_ALLOWED_ROOT"]).resolve(strict=True)
    candidate = Path(path).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError("file is outside the configured directory")
    return candidate


def _allowed_url(url):
    expected, actual = urlsplit(os.environ["CREDPROOF_ALLOWED_URL"]), urlsplit(url)
    same_origin = (actual.scheme, actual.hostname, actual.port) == (expected.scheme, expected.hostname, expected.port)
    prefix = expected.path.rstrip("/")
    if not same_origin or not (actual.path == prefix or actual.path.startswith(prefix + "/")):
        raise ValueError("service is outside the configured allowlist")
    return url


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirects are not followed", headers, fp)


def _fetch(url, credential):
    opener = build_opener(_NoRedirect())
    request = Request(url, headers={"Authorization": "Bearer " + credential, "Accept": "application/json"})
    with opener.open(request, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def run(request):
    """Fetch a feed for the subscriptions listed in the local file."""
    path, url = _validate(request)
    with open(_allowed_path(path), encoding="utf-8") as handle:
        subscriptions = [line.strip() for line in handle if line.strip()]
    credential = _credential()
    url = _allowed_url(url)
    service = _fetch(url, credential)
    return {"resource": request["resource"], "subscriptions": len(subscriptions), "service": service}
