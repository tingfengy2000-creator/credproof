from pathlib import Path

from credproof_safety.config import load_config
from credproof_safety.project import _scenario_requirements


def test_registered_material_assistant_declares_normal_and_redirect_scenarios():
    config = load_config(Path("examples/material_assistant/credproof.toml"))
    assert [scenario.name for scenario in config.entry.scenarios] == [
        "normal_allowed_output", "allowed_file_redirect"
    ]
    assert config.entry.scenarios[0].expected_error is None
    assert config.entry.scenarios[1].expected_error == "HTTPError"
    assert config.entry.scenarios[1].require_network is True


def test_required_scenarios_need_each_declared_outcome():
    config = load_config(Path("examples/material_assistant/credproof.toml"))
    base = {
        "name": "normal_allowed_output",
        "entry_returned": {"ok": True},
        "raised": None,
    }
    redirect = {
        "name": "allowed_file_redirect",
        "entry_returned": None,
        "raised": {"type": "HTTPError", "message": "blocked"},
        "request_observations": [{"service": "allow", "path": "/api/redirect"}],
    }
    assert _scenario_requirements(config, {"entry_scenarios": [base, redirect]})
    assert not _scenario_requirements(config, {"entry_scenarios": [base]})
    redirect["raised"] = None
    assert not _scenario_requirements(config, {"entry_scenarios": [base, redirect]})
