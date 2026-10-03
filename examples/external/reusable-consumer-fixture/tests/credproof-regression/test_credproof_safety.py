"""CredProof reusable safety regression; generated from a reviewed project config."""
import os
from pathlib import Path
import pytest

@pytest.mark.credproof_safety
def test_credproof_safety_regression():
    if os.environ.get("CREDPROOF_INNER") == "1":
        pytest.skip("CredProof executes the project test suite in its outer sandbox")
    from credproof_safety import check_project
    configured_root = os.environ.get("CREDPROOF_PROJECT_ROOT")
    if configured_root:
        root = Path(configured_root)
    else:
        root = next((candidate for candidate in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents)
                     if (candidate / "credproof.toml").is_file()), Path(__file__).resolve().parents[1])
    report = check_project(root / "credproof.toml", project_root=root)
    assert report["verdict"] == "PASS", report
