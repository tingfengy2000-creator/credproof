"""The reviewed candidate repair for the material assistant example."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise HTTPError(request.full_url, code, "redirect is outside the configured service", headers, fp)


def _allowed_path(path):
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"]).resolve(strict=True).parent
    candidate = Path(path).resolve(strict=True)
    return candidate.is_relative_to(allowed) and candidate.is_file()


def _allowed_url(url):
    expected = urlsplit(os.environ["CREDPROOF_ALLOWED_URL"])
    actual = urlsplit(url)
    same_origin = (actual.scheme, actual.hostname, actual.port or 80) == (
        expected.scheme, expected.hostname, expected.port or 80)
    same_path = actual.path == expected.path or actual.path.startswith(expected.path.rstrip("/") + "/")
    return same_origin and same_path


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    if not _allowed_path(path) or not _allowed_url(url):
        raise ValueError("resource or service is outside the configured allowlist")
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    response = build_opener(_NoRedirect()).open(
        Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    return {"resource": request["resource"], "material": material,
            "service": json.loads(body), "credential_used": True}
