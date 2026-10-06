"""Reusable, model-free safety checks for small authorised Python projects.

The package deliberately keeps the trusted surface small: configuration is
validated before execution, project tests and the configured entry point run in
the reviewed WSL/bubblewrap profile, and a result is PASS only when the
required observations and business checks are present.
"""

from .config import SafetyConfig, load_config
from .project import check_project, export_regression_tests

__all__ = ["SafetyConfig", "load_config", "check_project", "export_regression_tests"]
__version__ = "0.3.0-dev.13"
