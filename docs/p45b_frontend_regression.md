# P45-B: Resolver Generalization Regression

P45-A에서 확정한 구조 failure 두 건만 수정·재검증했다. retrieval, direct-field evidence binding, selector prompt, answer-generation prompt, candidate/browser 경로는 변경하지 않았다.

## 일반 규칙

- canonical subject alias: `확정기여형`, `확정기여형퇴직연금`, `확정기여형퇴직연금제도` → `DC`
- exclusive scope: 정확히 두 explicit subject가 있고 `B 없이 A만`, `B 제외하고 A`, `A 단독` 형태일 때만 `A`를 active subject로 확정

단순 부정문과 genuine multi-subject comparison은 exclusive scope로 강제하지 않는다.

## Live selector regression

| 항목 | 결과 |
|---|---:|
| 대상 | P45-003, P45-004 |
| active scope 정확 | 2/2 |
| requirement exact | 2/2 |
| gold direct evidence candidate 포함 | 2/2 |
| schema / ontology valid | 2/2 / 2/2 |
| unknown requirement | 0 |
| answer-generation HCX 호출 | 0 |
| candidate/browser 변경 | 0 |

P45는 이미 개발 회귀셋이므로 이 결과는 일반화 증거가 아니다. 다음 일반화 판정은 P46 fresh single-subject Closed E2E에서만 한다.
