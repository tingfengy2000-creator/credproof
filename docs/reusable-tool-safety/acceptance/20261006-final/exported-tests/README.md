# CredProof reusable regression

Install the `credproof-safety` package and keep `credproof.toml` in the project root.
Run `python -m credproof_safety check --config credproof.toml` before pytest.
The generated test reruns the same model-free check; it does not trust a saved PASS, a web page, or a case ID.
Declare the generated `tests/credproof-regression` path in `project.optional_tests`; its inner recursion guard is a wrapper check, not a business test.
Register the `credproof_safety` pytest marker in the consumer project's pytest.ini or pyproject.toml.
Each run writes a newly generated redacted safety report under `.credproof/consumer-report-*.json`; consumers may inspect it separately from pytest's exit code.
The check uses an isolated WSL/bubblewrap lab and synthetic credential/service material.
