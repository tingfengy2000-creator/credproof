# Complete case index

All 16 development-visible cases and all 48 historical trials are retained. These are direct field-preserving exports, not new experiment results.

[Original results.json](../../experiments/results/20260929T014733Z_00c48b93/results.json) | [CSV index](cases/case-index.csv)

| Case | Layer | Original trial indices (zero-based) | Three repeats: A / B / B-fresh / C / C-no-binding |
|---|---|---|---|
| [good_basic](cases/good-basic.json) | fresh | 0, 16, 32 | PASS / PASS / PASS / PASS / PASS |
| [good_format](cases/good-format.json) | fresh | 1, 17, 33 | PASS / PASS / PASS / PASS / PASS |
| [good_order](cases/good-order.json) | fresh | 2, 18, 34 | PASS / PASS / PASS / PASS / PASS |
| [constant_zero_alert](cases/constant-zero-alert.json) | fresh | 3, 19, 35 | PASS / FAIL / FAIL / FAIL / FAIL |
| [fallback_retained](cases/fallback-retained.json) | fresh | 4, 20, 36 | FAIL / FAIL / FAIL / FAIL / FAIL |
| [syntax_broken](cases/syntax-broken.json) | fresh | 5, 21, 37 | PASS / FAIL / FAIL / FAIL / FAIL |
| [residual_other_file](cases/residual-other-file.json) | fresh | 6, 22, 38 | FAIL / FAIL / FAIL / FAIL / FAIL |
| [unrelated_change](cases/unrelated-change.json) | fresh | 7, 23, 39 | PASS / PASS / PASS / FAIL / FAIL |
| [scope_omission](cases/scope-omission.json) | evidence_completeness | 8, 24, 40 | PASS / PASS / PASS / UNKNOWN / PASS |
| [function_not_checked](cases/function-not-checked.json) | evidence_completeness | 9, 25, 41 | PASS / UNKNOWN / PASS / UNKNOWN / UNKNOWN |
| [index_residual_local_pass](cases/index-residual-local-pass.json) | fresh | 10, 26, 42 | PASS / PASS / PASS / PASS / PASS |
| [wrong_environment_name](cases/wrong-environment-name.json) | fresh | 11, 27, 43 | PASS / FAIL / FAIL / FAIL / FAIL |
| [stale_pass_replay](cases/stale-pass-replay.json) | delivery | 12, 28, 44 | PASS / PASS / FAIL / UNKNOWN / PASS |
| [cross_object_evidence](cases/cross-object-evidence.json) | delivery | 13, 29, 45 | PASS / PASS / PASS / UNKNOWN / PASS |
| [cross_scope_evidence](cases/cross-scope-evidence.json) | delivery | 14, 30, 46 | PASS / PASS / PASS / UNKNOWN / PASS |
| [cross_rule_evidence](cases/cross-rule-evidence.json) | delivery | 15, 31, 47 | PASS / PASS / PASS / UNKNOWN / PASS |
