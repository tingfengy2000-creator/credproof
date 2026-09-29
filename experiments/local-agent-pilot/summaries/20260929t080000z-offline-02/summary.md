# Recorded outcomes and process evidence

Final artifact PASS and observed Agent process are separate. Hypothesis quality and feedback rationale require human review. Missing methods have no reported score.

| Case | Method | Final artifact | Model status | Original leak reproduced | Process evidence |
|---|---|---|---|---|---|
| p01 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p01 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p01 | C-agent | PASS | STOPPED_LIMIT | 1 | NOT_ESTABLISHED |
| p01 | D-no-feedback-1 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p01 | D-no-feedback-2 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p01 | D-no-feedback-3 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p02 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p02 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p02 | C-agent | PASS | COMPLETED | 2 | MANUAL_REVIEW_REQUIRED |
| p03 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p03 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p03 | C-agent | PASS | COMPLETED | 1 | MANUAL_REVIEW_REQUIRED |
| p03 | D-no-feedback-1 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p03 | D-no-feedback-2 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p03 | D-no-feedback-3 | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p04 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p04 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p04 | C-agent | PASS | COMPLETED | 1 | MANUAL_REVIEW_REQUIRED |
| p05 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p05 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p05 | C-agent | PASS | COMPLETED | 0 | NOT_ESTABLISHED |
| p06 | A-fixed | PASS | NOT_APPLICABLE | N/A | NOT_APPLICABLE |
| p06 | B-once | PASS | COMPLETED | N/A | NOT_APPLICABLE |
| p06 | C-agent | PASS | COMPLETED | 0 | MANUAL_REVIEW_REQUIRED |

The JSON contains quoted hypotheses, model-selected inputs, proposal rationales, trace positions, and whether feedback actually appeared in a later model request. A same-response parallel tool call is not feedback use.

C versus D shares a configured maximum generated-token ceiling only. Actual tokens, context, model calls, wall time and execution feedback differ. D covers two predetermined cases, with three attempts each; it is not six independent cases.
