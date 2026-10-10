"""Authorised materials assistant: developer revision, Codex assisted.

Uses the fixed access component; this revision is not runtime-model output.
"""
import os
import logging
from credproof_access import read_text, get_json


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    material = read_text(path)
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    service_data = get_json(url, credential)
    logging.info("loaded %s", request["resource"])
    return {"resource": request["resource"], "material": material, "service": service_data}
