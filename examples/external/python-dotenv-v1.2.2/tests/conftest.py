"""Thin local test-path adapter; upstream source and test_main.py stay intact."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import pytest


@pytest.fixture
def cli():
    # Same upstream fixture, retained for test_main.py collection.
    from click.testing import CliRunner
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


@pytest.fixture
def dotenv_path(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes(b"")
    yield path
