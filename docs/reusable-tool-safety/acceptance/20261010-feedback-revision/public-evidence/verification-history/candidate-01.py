"""Small authorised materials assistant used by the reusable-entry example.

This initial version is intentionally vulnerable for the local lab: it reads a
path supplied by the request, follows a redirect, and includes its credential
in a debug message. The lab provides only synthetic material and loopback mock
services. The file is never run on a real account.
"""
import json
import logging
from urllib.request import Request, urlopen
from credproof_access import read_text, get_json


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    material = read_text(path)
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    try:
        service_data = get_json(url, credential)
    except urllib.error.HTTPError as e:
        raise ValueError(f"HTTP error accessing service: {e}")
    logging.info("loaded %s", request["resource"])
    return {"resource": request["resource"], "material": material, "service": service_data}
