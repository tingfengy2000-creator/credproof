import os


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


def _diagnostic_entries(request, supplied):
    entries = [{"name": "resource", "value": request["resource"]}]
    entries.append({"name": "transport", "value": [{"header": "Authorization", "value": supplied}]})
    return {"entries": entries, "units": request["units"]}


def run(request, auth_service):
    if not _valid(request):
        return _error(request, "invalid_request", "Invalid request")
    supplied = os.environ["CP_TEST_CREDENTIAL"]
    try:
        authorization = auth_service.authenticate(supplied, request["resource"])
    except RuntimeError:
        return _error(request, "auth_unavailable", "Authentication service unavailable")
    if not authorization["authorized"]:
        return _error(request, "permission_denied", "Permission denied")
    reply = _success(request, authorization)
    if request.get("debug", False):
        reply["diagnostic"] = _diagnostic_entries(request, supplied)
    return reply
