import os
import logging


def _error(kind, message, request_id):
    return {"ok": False, "request_id": request_id, "error": {"type": kind, "message": message}}


def _valid(request):
    if not isinstance(request, dict):
        return False
    return (isinstance(request.get("request_id"), str) and bool(request["request_id"])
            and isinstance(request.get("resource"), str) and bool(request["resource"])
            and type(request.get("units")) is int and 1 <= request["units"] <= 5
            and type(request.get("debug", False)) is bool)


def run(request, auth_service):
    request_id = request.get("request_id", "") if isinstance(request, dict) else ""
    request_id = request_id if isinstance(request_id, str) else ""
    if not _valid(request):
        return _error("invalid_request", "Invalid request", request_id)
    credential = os.environ["CP_TEST_CREDENTIAL"]
    try:
        authorization = auth_service.authenticate(credential, request["resource"])
    except RuntimeError:
        logging.error("Local authentication unavailable for request %s", request_id)
        return _error("auth_unavailable", "Authentication service unavailable", request_id)
    if authorization.get("authorized") is not True:
        return _error("permission_denied", "Permission denied", request_id)
    public_meta = {"route": "local-mock", "debug": request.get("debug", False)}
    return {"ok": True, "request_id": request_id, "resource": request["resource"],
            "units": request["units"], "total": 7 * request["units"],
            "subject": authorization["subject"], "meta": public_meta}
