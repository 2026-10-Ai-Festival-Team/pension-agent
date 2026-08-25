# P47-B Exclusive Scope Connector Generalization

## Scope

This change is limited to resolver-side exclusion connectors. It does not change retrieval, evidence binding, answer generation, citation validation, or the candidate/browser path.

Supported binary forms resolve `include=A`, `exclude=B` only when exactly two explicit subjects form a clear exclusion relation:

- `B 없이 A만`
- `B 제외하고 A`
- `B는 빼고 A만`
- `B를 빼고 A`
- `B 말고 A`
- `B가 아닌 A만`

Safety boundaries remain intact:

- `B 말고 A도 가능한가` remains additive, not exclusive.
- comparison cues such as `비교`, `차이`, and `각각` preserve plural scope.
- a single bare negative cannot invent an included subject.

## Regression

| Target | Scope correct | Requirement exact | Gold direct evidence |
| --- | ---: | ---: | ---: |
| P45-004 (`IRP를 함께 쓰지 않고 연금저축만`) | pass | pass | pass |
| P47-004 (`IRP는 빼고 연금저축 계좌에만`) | pass | pass | pass |

The two selector responses were live HCX-007 Structured Output responses. The first test-harness output omitted `allowed_requirements` while calling preparation, which caused a false `0/2` evidence result. The frozen selector responses were reused; preparation was recomputed offline with the required scoped catalog and produced `2/2` direct-gold coverage. No answer-generation HCX call was made.

## Decision

**Regression Go.** This is development evidence only. P48 must be a newly created and frozen single-subject Closed E2E holdout; P47 must not be re-scored as a generalization claim.
