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
from pathlib import Path


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    
    # Validate path is within allowed scope
    allowed_root = Path(os.environ["CREDPROOF_ALLOWED_ROOT"])
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    if not path:
        raise ValueError("no path provided")
    
    # Resolve the path and check it's within allowed root
    resolved_path = Path(path).resolve()
    if not resolved_path.is_relative_to(allowed_root):
        raise ValueError("path outside allowed scope")
    
    with open(resolved_path, "r", encoding="utf-8") as handle:
        material = handle.read()
    
    # Validate URL is within allowed service scope
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    allowed_url = os.environ["CREDPROOF_ALLOWED_URL"]
    
    # Check if the URL matches the allowed pattern (simple check)
    if not url.startswith(allowed_url.split("/")[0] + "/" + allowed_url.split("/")[2]):
        raise ValueError("URL outside allowed service scope")
    
    response = urlopen(Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    logging.info("loaded %s with credential=%s", request["resource"], credential)
    return {"resource": request["resource"], "material": material, "service": json.loads(body),
            "credential": credential}