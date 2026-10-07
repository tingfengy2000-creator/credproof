"""Small authorised materials assistant used by the reusable-entry example.

This initial version is intentionally vulnerable for the local lab: it reads a
path supplied by the request, follows a redirect, and includes its credential
in a debug message. The lab provides only synthetic material and loopback mock
services. The file is never run on a real account.
"""
import json
import logging
import os
from urllib.request import Request, urlopen


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    response = urlopen(Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    logging.info("loaded %s with credential=%s", request["resource"], credential)
    return {"resource": request["resource"], "material": material, "service": json.loads(body),
            "credential": credential}