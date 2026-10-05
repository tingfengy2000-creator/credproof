# CredProof reusable regression

Install the `credproof-safety` package and keep `credproof.toml` in the project root.
Run `python -m credproof_safety check --config credproof.toml` before pytest.
The generated test reruns the same model-free check; it does not trust a saved PASS, a web page, or a case ID.
The test writes a newly generated redacted safety report under `.credproof/consumer-report-*.json`.
The `credproof_safety` marker is registered in the fixture's `pytest.ini`.
The check uses an isolated WSL/bubblewrap lab and synthetic credential/service material.
