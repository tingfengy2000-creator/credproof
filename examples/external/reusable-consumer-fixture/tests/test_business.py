import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
import tool


def test_external_consumer_business_path():
    result = tool.run({"resource": "business"})
    assert result["resource"] == "business"
    assert result["credential_used"] is True


def test_external_consumer_rejects_forbidden_file():
    try:
        tool.run({"resource": "boundary", "path": os.environ["CREDPROOF_FORBIDDEN_FILE"]})
    except ValueError:
        return
    raise AssertionError("forbidden file was accepted")
