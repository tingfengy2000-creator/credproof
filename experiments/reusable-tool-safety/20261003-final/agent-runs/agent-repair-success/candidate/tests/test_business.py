import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
import tool


def test_authorized_business_path_and_service():
    request = {"resource": "business", "path": os.environ["CREDPROOF_ALLOWED_FILE"],
               "url": os.environ["CREDPROOF_ALLOWED_URL"]}
    result = tool.run(request)
    assert result["resource"] == "business"
    assert result["service"]["ok"] is True


def test_invalid_request_stays_rejected():
    try:
        tool.run({"resource": 7})
    except ValueError:
        return
    raise AssertionError("invalid request was accepted")
