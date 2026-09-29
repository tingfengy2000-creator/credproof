# CredProof synthetic mechanism pilot

All 16 cases were visible during development; there is no independent final holdout. These are locally generated fixtures, not a real-world detection benchmark. A/B are constructed comparators, not claims about product defaults.

Protocol SHA-256: `6cad7b130f348a991c9cb1deaaf99f9cd78c184c3083042de71d1f4be63083ef`  
Gitleaks: `8.28.0`  
Cases: 16; repeated trials: 48; errors: 0; C/oracle disagreements: 0.

Frozen inputs unchanged throughout run: True; B-fresh/new-input oracle disagreements: 0.

Repeats test stability; they do not increase the number of independent case families. UNKNOWN cases represent missing/misbound evidence and are separate from bad patches.

## Case-level counts

False acceptance counts a case if any repeat passes. Valid acceptance and stable UNKNOWN require every repeat. Mixed/error outcomes remain visible; repeats do not increase these denominators.

| Mode | Bad-patch false acceptance | Valid acceptance | Insufficient/misbound evidence false acceptance | Overall stable UNKNOWN | Mixed cases |
|---|---|---|---|---|---|
| A | 4/6 | 4/4 | 6/6 | 0/16 | 0/16 |
| B | 1/6 | 4/4 | 5/6 | 1/16 | 0/16 |
| C | 0/6 | 4/4 | 0/6 | 6/16 | 0/16 |
| C-no-binding | 0/6 | 4/4 | 5/6 | 1/16 | 0/16 |

Fresh has ten complete, same-scope cases. The six evidence-completeness/delivery cases exercise simplified supplied-evidence aggregation; they are not claims about a reasonable CI pipeline that reruns its fixed scope.

## fresh

| Case | Expected C | A | B | C | C-no-binding | B-fresh | Oracle / originals |
|---|---|---|---|---|---|---|---|
| good_basic | PASS | PASS | PASS | PASS | PASS | PASS | OK |
| good_format | PASS | PASS | PASS | PASS | PASS | PASS | OK |
| good_order | PASS | PASS | PASS | PASS | PASS | PASS | OK |
| constant_zero_alert | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | OK |
| fallback_retained | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | OK |
| syntax_broken | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | OK |
| residual_other_file | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | OK |
| unrelated_change | FAIL | PASS | PASS | FAIL | FAIL | PASS | OK |
| index_residual_local_pass | PASS | PASS | PASS | PASS | PASS | PASS | OK |
| wrong_environment_name | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | OK |

## evidence_completeness

| Case | Expected C | A | B | C | C-no-binding | B-fresh | Oracle / originals |
|---|---|---|---|---|---|---|---|
| scope_omission | UNKNOWN | PASS | PASS | UNKNOWN | PASS | PASS | OK |
| function_not_checked | UNKNOWN | PASS | UNKNOWN | UNKNOWN | UNKNOWN | PASS | OK |

## delivery

| Case | Expected C | A | B | C | C-no-binding | B-fresh | Oracle / originals |
|---|---|---|---|---|---|---|---|
| stale_pass_replay | UNKNOWN | PASS | PASS | UNKNOWN | PASS | FAIL | OK |
| cross_object_evidence | UNKNOWN | PASS | PASS | UNKNOWN | PASS | PASS | OK |
| cross_scope_evidence | UNKNOWN | PASS | PASS | UNKNOWN | PASS | PASS | OK |
| cross_rule_evidence | UNKNOWN | PASS | PASS | UNKNOWN | PASS | PASS | OK |

## Independent fresh overhead samples

One valid two-file fixture; each mode independently recollects only its required checks. Order rotates. These descriptive local samples do not establish a speed advantage.

| Mode | N | Mean ms | Min ms | Max ms | Sample variance ms² |
|---|---|---|---|---|---|
| A | 3 | 334.885 | 329.045 | 343.003 | 52.604 |
| B | 3 | 334.675 | 333.218 | 337.427 | 5.688 |
| C | 3 | 333.329 | 327.450 | 343.709 | 81.287 |

Observed mean C − B: -1.346 ms; all timing checks passed: True.

## Interpretation limits

- The index-residual case is a valid local-copy PASS with unchanged original risk, not a rejected bad fix.
- B-fresh recollects current candidate evidence for scan/syntax/function on the full intended scope. It is judged against its new-input oracle, not the old delivered-evidence UNKNOWN label. Read this column before attributing delivery-fault benefits uniquely to binding checks.
- Shared full-collection timings and assess timings are recorded separately. No per-mode execution-speed ranking is claimed.
- No precision/recall, cloud-validity, SOTA, or population confidence-interval claim follows from this pilot.
- JSON retains all trial errors, exact verdicts, obligation reports and independent oracle facts.

Unstable cases: none observed
