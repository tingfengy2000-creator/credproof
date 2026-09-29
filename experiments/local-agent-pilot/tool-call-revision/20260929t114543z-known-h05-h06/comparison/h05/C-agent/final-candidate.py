import os
import logging


def _valid(request):
    return (isinstance(request, dict)
            and isinstance(request.get("request_id"), str) and bool(request["request_id"])
            and isinstance(request.get("resource"), str) and bool(request["resource"])
            and type(request.get("units")) is int and 1 <= request["units"] <= 5
            and type(request.get("debug", False)) is bool)


def _error(request, kind, message):
    identifier = request.get("request_id", "") if isinstance(request, dict) else ""
    if not isinstance(identifier, str):
        identifier = ""
    return {"ok": False, "request_id": identifier, "error": {"type": kind, "message": message}}


def _success(request, authorization):
    return {"ok": True, "request_id": request["request_id"], "resource": request["resource"],
            "units": request["units"], "total": request["units"] * 7,
            "subject": authorization["subject"],
            "meta": {"route": "local-mock", "debug": request.get("debug", False)}}


def _call_authorization(service, supplied, resource):
    try:
        reply = service.authenticate(supplied, resource)
    except RuntimeError:
        return {"state": "unavailable"}
    if reply["authorized"]:
        return {"state": "authorized", "reply": reply}
    return {"state": "denied"}


def run(request, auth_service):
    if not _valid(request):
        return _error(request, "invalid_request", "Invalid request")
    outcome = _call_authorization(auth_service, os.environ["CP_TEST_CREDENTIAL"], request["resource"])
    if outcome["state"] == "unavailable":
        return _error(request, "auth_unavailable", "Authentication service unavailable")
    if outcome["state"] == "denied":
        return _error(request, "permission_denied", "Permission denied")
    logging.info("authorized request=%s resource=%s", request["request_id"], request["resource"])
    return _success(request, outcome["reply"])
