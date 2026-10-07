import os
from pathlib import Path

def run(request):
    # Validate request structure
    if not isinstance(request, dict):
        raise ValueError("Invalid request format")
    
    resource = request.get("resource")
    path = request.get("path")
    url = request.get("url")

    if not all([resource, path, url]):
        raise ValueError("Missing required fields in request")

    # Validate allowed file path
    allowed_file = os.environ.get("CREDPROOF_ALLOWED_FILE")
    if path != allowed_file:
        raise ValueError("Forbidden file access attempted")

    # Validate service URL
    allowed_url = os.environ.get("CREDPROOF_ALLOWED_URL")
    if url != allowed_url:
        raise ValueError("Forbidden service access attempted")

    # Check for credential in request (should not be present)
    credential = os.environ.get("CREDPROOF_TEST_CREDENTIAL")
    if credential and credential in repr(request):
        raise ValueError("Credential found in request")

    # Simulate business logic
    return {
        "resource": resource,
        "service": {"ok": True},
        "material": "processed",
        "credential": None  # Never return credential
    }