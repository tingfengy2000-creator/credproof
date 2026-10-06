"""CredProof reusable safety regression; generated from a reviewed project config."""
import os
from pathlib import Path
import tempfile
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
    report_dir = root / ".credproof"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_fd, report_name = tempfile.mkstemp(prefix="consumer-report-", suffix=".json",
                                              dir=report_dir)
    os.close(report_fd)
    report_path = Path(report_name)
    report_path.unlink()
    report = check_project(root / "credproof.toml", output=report_path, project_root=root)
    assert report["verdict"] == "PASS", report
