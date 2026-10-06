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


def test_file_and_service_boundaries_reject_alternate_inputs():
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"])
    forbidden_file = os.environ["CREDPROOF_FORBIDDEN_FILE"]
    forbidden_url = os.environ["CREDPROOF_FORBIDDEN_URL"]
    candidates = [
        forbidden_file,
        str(allowed.parent / ".." / "secrets" / "secret.txt"),
        str(allowed.parent / "link-to-forbidden.txt"),
    ]
    for path in candidates:
        try:
            tool.run({"resource": "boundary", "path": path,
                      "url": os.environ["CREDPROOF_ALLOWED_URL"]})
        except ValueError:
            pass
        else:
            raise AssertionError(f"outside file was accepted: {path}")
    try:
        tool.run({"resource": "boundary", "path": str(allowed), "url": forbidden_url})
    except ValueError:
        pass
    else:
        raise AssertionError("forbidden service was accepted")
