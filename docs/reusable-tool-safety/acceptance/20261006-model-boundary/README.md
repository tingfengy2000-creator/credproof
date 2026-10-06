# Model-process boundary evidence (2026-10-06)

This directory records one fresh run of the local model path. It is a boundary and tool-protocol evidence run, not a success-rate benchmark. Inputs are an authorized synthetic project; no real credential or network target is used.

The runner staged only `worker.py`, `agent_pilot/tools.py`, `agent_pilot/model_client.py` and the package marker. The model namespace received read-only Python runtime/dependencies, Ollama, the manifest and four model blobs, and the read-only GPU driver directory. `/work` stores run output and `/rpc` is a native WSL RPC directory; the checkout, candidate history, labels, reference patches, host `/mnt`, service home, proxy and API-key variables are excluded.

## Commands and results

```powershell
python -m unittest agent_pilot.tests.test_model_boundary tests.test_reusable_tool_safety agent_pilot.tests.test_runtime_config -v
# 33 tests, OK

python -m credproof_safety repair --config <synthetic-project>/credproof.toml --output <run>/report.json
# one fresh WSL+bubblewrap model run; report status INCOMPLETE after 11 tool requests
```

The repository-wide `unittest discover -s agent_pilot` command was also attempted from the host Python and failed during import because that interpreter did not have `qwen_agent`; this is an environment dependency failure, not a model result. The actual model run used the reviewed WSL Python 3.12 runtime and completed the native Qwen-Agent/Ollama calls recorded here.

## Boundary observations

`model-boundary-probe.raw.json` is written by the process inside its own namespace before Ollama starts. It records `lo` as the only interface, failed IPv4/IPv6 external connects, no visible host sentinel, no writable model code, and no unapproved Windows/host mount. `model-boundary-plan.raw.json` is the supervisor's explicit mount plan. `manifest.json` covers every public record in this directory.

`integration-receipt.json` is a second, smaller probe run that starts Ollama and performs one real local `api/generate` call inside the same boundary. `service-boundary.raw.json` records matching mount/network/PID/user namespace IDs for the controller and Ollama, and `process-tree-after-inference.raw.json` records the inference process namespace IDs. `live-generation.raw.json` is the bounded local response; it is not a repair result.

`model-run-summary.json` is the compact interpretation of the raw run. The model made 11 native tool requests: two rejected path reads, four accepted tool responses, three candidate submissions, and three trusted `FAIL` verifications. It reached the three-candidate limit and ended `INCOMPLETE`; it did not receive permission to declare success. `model-run.raw.json` and `model-events.raw.jsonl` preserve the complete sanitized trace. `ollama-stderr.raw.log` records `OLLAMA_NO_CLOUD=true` and the local server. This run reported CPU inference; it is not a GPU speed result.

`boundary-attempt-log.json` records the earlier finite boundary bring-up failures and the final successful integration run; no failed attempt was removed from the local development record.

The boundary evidence closes the previous handoff blocker for this limited run. It does not prove a general sandbox, kernel-level audit, or automatic repair success. Historical Agent failures and prior deterministic checks remain in their original versioned directories.
