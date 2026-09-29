import os
import logging

def _valid(request):
    return (isinstance(request, dict) and isinstance(request.get("request_id"), str)
            and bool(request["request_id"]) and isinstance(request.get("resource"), str)
            and bool(request["resource"]) and type(request.get("units")) is int
            and 1 <= request["units"] <= 5 and type(request.get("debug", False)) is bool)

def _authenticate(auth_service, credential, resource):
    return auth_service.authenticate(credential, resource)

def run(request, auth_service):
    request_id = request.get("request_id", "") if isinstance(request, dict) else ""
    request_id = request_id if isinstance(request_id, str) else ""
    if not _valid(request):
        return {"ok": False, "request_id": request_id,
                "error": {"type": "invalid_request", "message": "Invalid request"}}
    credential = os.environ["CP_TEST_CREDENTIAL"]
    try:
        identity = _authenticate(auth_service, credential, request["resource"])
    except RuntimeError as error:
        return {"ok": False, "request_id": request_id,
                "error": {"type": "auth_unavailable", "message": "Authentication service unavailable"}}
    if not identity["authorized"]:
        return {"ok": False, "request_id": request_id,
                "error": {"type": "permission_denied", "message": "Permission denied"}}
    return {"ok": True, "request_id": request_id, "resource": request["resource"],
            "units": request["units"], "total": request["units"] * 7, "subject": identity["subject"],
            "meta": {"route": "local-mock", "debug": request.get("debug", False)}}