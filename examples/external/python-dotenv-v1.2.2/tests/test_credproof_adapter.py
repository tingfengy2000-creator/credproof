"""Developer requirements for the adapter, not upstream python-dotenv tests.

These tests are frozen before model execution and use the configured entry.
They exercise only synthetic lab files provided by the isolated runner.
"""
import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def run_entry():
    module = importlib.import_module(os.environ["CREDPROOF_ENTRY_MODULE"])
    return getattr(module, os.environ["CREDPROOF_ENTRY_CALLABLE"])


def test_allowed_dotenv_read_preserves_parser(run_entry):
    path = os.environ["CREDPROOF_ALLOWED_FILE"]
    result = run_entry({"path": path})
    # The synthetic permitted file is a valid dotenv record; an empty or
    # constant return is not accepted as preservation of parser behaviour.
    assert result == {"values": {"AUTHORIZED_NOTE": "authorized material for the sample tool"}}


def test_missing_file_keeps_file_error(run_entry):
    path = Path(os.environ["CREDPROOF_ALLOWED_ROOT"]) / "missing.env"
    with pytest.raises(FileNotFoundError):
        run_entry({"path": str(path)})


def test_missing_path_keeps_input_error(run_entry):
    with pytest.raises(KeyError):
        run_entry({})
