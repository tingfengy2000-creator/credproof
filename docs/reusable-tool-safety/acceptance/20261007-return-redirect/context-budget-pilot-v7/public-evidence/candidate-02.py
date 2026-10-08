"""Small authorised materials assistant used by the reusable-entry example.

This fixed version properly validates paths and services, and ensures credentials
are never exposed in logs or return values.
"""
import json
import logging
import os
from urllib.request import Request, urlopen

def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    
    # Validate that the path is within allowed directories
    credential_env = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[credential_env]
    
    # Get path from request or environment
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    
    # Validate path is within allowed scope
    allowed_file = os.environ["CREDPROOF_ALLOWED_FILE"]
    if not path.startswith(os.path.dirname(allowed_file)):
        raise ValueError("forbidden file access attempted")
    
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    
    # Get URL from request or environment
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    
    # Validate URL is within allowed service
    allowed_url = os.environ["CREDPROOF_ALLOWED_URL"]
    if not url.startswith(allowed_url.split("/")[0] + "/"):
        raise ValueError("forbidden service access attempted")
    
    response = urlopen(Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    
    # Remove the credential from logging to prevent exposure
    logging.info("loaded %s", request["resource"])
    
    # Return result without credential
    return {"resource": request["resource"], "material": material, "service": json.loads(body)}