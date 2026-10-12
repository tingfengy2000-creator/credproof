import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
import tool


def normal_request(resource="business"):
    return {"resource": resource, "path": os.environ["CREDPROOF_ALLOWED_FILE"],
            "url": os.environ["CREDPROOF_ALLOWED_URL"]}


def test_invalid_request_is_rejected():
    try:
        tool.run({"resource": 7})
    except ValueError:
        return
    raise AssertionError("invalid request was accepted")


def test_normal_request_returns_service_data():
    result = tool.run(normal_request())
    assert result["resource"] == "business"
    assert result["service"]["ok"] is True


def test_foreign_service_is_rejected():
    request = dict(normal_request(), url=os.environ["CREDPROOF_FORBIDDEN_URL"])
    try:
        tool.run(request)
    except ValueError:
        return
    raise AssertionError("a service outside the allowlist was contacted")
