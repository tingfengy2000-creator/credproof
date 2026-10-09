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
    # Validate path is within allowed directories
    allowed_dirs = [os.path.abspath(p) for p in os.environ.get("CREDPROOF_ALLOWED_DIRS", "data").split(":")]
    resolved_path = os.path.abspath(path)
    if not any(resolved_path.startswith(os.path.abspath(d)) for d in allowed_dirs):
        raise ValueError("path outside allowed directories")
    # Check for forbidden directories
    forbidden_dirs = [os.path.abspath(p) for p in os.environ.get("CREDPROOF_FORBIDDEN_DIRS", "secrets").split(":")]
    if any(resolved_path.startswith(os.path.abspath(d)) for d in forbidden_dirs):
        raise ValueError("path inside forbidden directories")
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    url = request.get("url") or os.environ["CREDPROOF_ALLOWED_URL"]
    # Validate service URL is within allowed services
    allowed_services = [
        {
            "scheme": "http",
            "host": "127.0.0.1",
            "path_prefix": "/api"
        }
    ]
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    service_allowed = False
    for svc in allowed_services:
        if (parsed_url.scheme == svc["scheme"] and
                parsed_url.hostname == svc["host"] and
                parsed_url.path.startswith(svc["path_prefix"])):
            service_allowed = True
            break
    if not service_allowed:
        raise ValueError("service URL outside allowed services")
    response = urlopen(Request(url, headers={"Authorization": "Bearer " + credential}), timeout=2)
    body = response.read().decode("utf-8")
    logging.info("loaded %s with credential=%s", request["resource"], credential)
    return {"resource": request["resource"], "material": material, "service": json.loads(body),
            "credential": None}
