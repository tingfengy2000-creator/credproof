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


def test_file_outside_the_directory_is_rejected():
    request = dict(normal_request(), path=os.environ["CREDPROOF_FORBIDDEN_FILE"])
    try:
        tool.run(request)
    except ValueError:
        return
    raise AssertionError("a file outside the configured directory was read")


def test_traversal_and_links_are_rejected():
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"])
    for path in (str(allowed.parent / ".." / "secrets" / "secret.txt"),
                 str(allowed.parent / "link-to-forbidden.txt")):
        if not Path(path).exists() and not Path(path).is_symlink():
            continue
        try:
            tool.run(dict(normal_request(), path=path))
        except (ValueError, OSError):
            continue
        raise AssertionError(f"path escaped the configured directory: {path}")
