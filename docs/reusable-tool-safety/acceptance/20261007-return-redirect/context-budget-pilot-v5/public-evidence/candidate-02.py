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
    path = request.get("path") or os.environ.get("CREDPROOF_ALLOWED_FILE")
    
    # Validate that the path is within allowed directories
    allowed_file = Path(os.environ["CREDPROOF_ALLOWED_FILE"])
    requested_path = Path(path)
    
    if not requested_path.is_absolute():
        raise ValueError("path must be absolute")
        
    if not requested_path.is_file():
        raise ValueError("path must point to a file")
        
    # Check that the path is within allowed scope
    try:
        requested_path.resolve().relative_to(allowed_file.resolve().parent)
    except ValueError:
        raise ValueError("path is outside of allowed scope")
    
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    
    # Validate that the URL uses the allowed service
    allowed_url = os.environ["CREDPROOF_ALLOWED_URL"]
    if not url.startswith(allowed_url.split("/")[0] + "/"):
        raise ValueError("URL is outside of allowed scope")
        
    response = urlopen(Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    
    # Remove the logging line that leaks the credential
    # logging.info("loaded %s with credential=%s", request["resource"], credential)
    
    return {"resource": request["resource"], "material": material, "service": json.loads(body)}