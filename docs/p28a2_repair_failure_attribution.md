# P28-A2: Repair Failure Attribution

## 목적

P28-A1에서 strict useful로 전환되지 않은 7개 문항을 추가 HCX 호출 없이 분석한다. 목표는 Repair 실패를 모델의 일반적인 한계로 묶지 않고, `requirement → FrozenEvidenceBundle → verifier → repair` 중 최초 실패 위치를 분리하는 것이다.

## 고정 조건

- 분석 대상: `R-006`, `R-019`, `R-034`, `R-011`, `R-033`, `R-035`, `R-038`
- 실행 artifact: `data/diagnostics/p28a1_contract_alignment_12cases.json`
- Citation/provenance: 전 단계가 selected primary-original bundle만 사용한 상태
- 새 retrieval, 새 evidence, 새 HCX 호출 없음

## 결과

| ID | Requirement | Frozen bundle | Verifier | Repair | 주원인 |
|---|---|---|---|---|---|
| R-006 | DB→DC 가능 여부·규약/동의 조건을 정확히 생성 | 전환 가능 및 규약/동의 근거 있음 | 조건 누락을 정확히 지적 | 전환 가능 여부만 반복하고 조건을 누락 | `repair_ignore` |
| R-019 | DC 법정사유를 하나의 포괄 slot으로만 생성 | DC 일반 근거와 IRP 사유가 섞여 있음 | PASS | repair 없음 | `planner_miss` |
| R-034 | 총보수·투자대상을 정확히 생성 | 투자대상은 있으나 총보수율 대신 비용 예시만 있음 | PASS | repair 없음 | `field_confusion` |
| R-011 | `질문에 직접 답변`이라는 일반 slot만 생성 | 과세 시점 근거가 bundle에 없음 | 과세 시점 누락을 정확히 지적 | 동일한 압류 설명을 유지 | `planner_miss` |
| R-033 | 상품명·위험등급 slot을 정확히 생성 | 위험등급은 있으나 상품명 근거가 없음 | 근거 누락을 정확히 지적 | 근거 없음 응답 유지 | `evidence_missing` |
| R-035 | `질문에 직접 답변`이라는 일반 slot만 생성 | 주요 투자 위험을 완결할 근거가 없음 | 위험 설명 누락을 정확히 지적 | 투자전략을 위험으로 대체 | `planner_miss` |
| R-038 | 조기 인출 사유를 구조화하지 못하고 일반 slot 생성 | 인출 사유 근거가 bundle에 없음 | PASS/REVISE 대신 무관한 압류 설명을 생성 | 무관한 설명을 유지 | `planner_miss` |

## 네 단계별 판정

### 1. Requirement 정확성

- 정확: `R-006`, `R-034`, `R-033`
- 미흡: `R-019`, `R-011`, `R-035`, `R-038`

`R-011`, `R-035`, `R-038`은 실제 질문의 과세 시점·투자 위험·중도인출 사유를 slot으로 표현하지 못했다. 따라서 Repair 이전에 필요한 evidence가 명확히 선택될 수 없는 상태였다.

### 2. FrozenEvidenceBundle 완결성

- 답변에 필요한 핵심 근거가 충분: `R-006`
- 일부 field 또는 질문 핵심 근거가 부족: `R-019`, `R-034`, `R-011`, `R-033`, `R-035`, `R-038`

특히 `R-034`는 `<1,000만원 투자 시 비용 예시>`가 있어도 `총보수율`을 대신할 수 없고, `R-033`은 위험등급은 있어도 상품명 근거가 없다. 이는 원본 corpus 자체의 부재 판정이 아니라, 이번 FrozenBundle 안에 필요한 정확한 field를 넣지 못한 문제다.

### 3. Verifier 정확성

- 실제 오류를 지적: `R-006`, `R-011`, `R-033`, `R-035`
- 오류를 통과시킴: `R-019`, `R-034`
- PASS/REVISE 계약을 따르지 않고 무관한 문장을 생성: `R-038`

Verifier가 오류를 발견한 4건도 Repair 성공으로 이어지지 않았다. 따라서 verifier의 자연어 진단만 추가하는 방식은 충분하지 않다.

### 4. Repair 실패 양상

- `repair_ignore`: `R-006`, `R-011`
- `repair_misread`: `R-035`, `R-038`
- repair 이전 문제로 repair 없음: `R-019`, `R-034`
- 근거 자체가 없다는 한계를 유지: `R-033`

`R-033`은 억지로 답을 만드는 것보다 근거 부족을 알리는 편이 안전하다. 반면 `R-006`은 충분한 bundle이 있었는데도 Repair가 Verifier의 조건 누락 지시를 실제 답변에 반영하지 못한 순수 repair failure다.

## 원인 집계

| 주원인 | 건수 | 문항 |
|---|---:|---|
| `planner_miss` | 4 | R-019, R-011, R-035, R-038 |
| `evidence_missing` | 1 | R-033 |
| `field_confusion` | 1 | R-034 |
| `repair_ignore` | 1 | R-006 |

보조 원인으로 `verifier_miss`는 R-019·R-034·R-038에서 확인됐고, `repair_misread`는 R-035·R-038에서 확인됐다.

## 결론

P28-A2는 **모델 튜닝으로 바로 넘어갈 근거를 아직 만들지 못했다.** 7건 중 6건은 Repair 이전의 requirement/frozen evidence/field 경계에 문제가 있으며, evidence가 충분하고 Verifier도 정확했는데 Repair만 실패한 명확한 사례는 R-006 하나다.

따라서 P28 workflow는 No-Go 상태로 유지한다. 다음 개선은 multi-agent 확장이 아니라:

1. 실제 브라우저 경로의 추천·위험 고지 안전 정책을 우선 보강하고,
2. 이후 requirement coverage와 product field retrieval/matching을 single-pass 경로에서 분리 검증하며,
3. 그 뒤에도 `evidence 충분 + verifier 정확 + repair/answer 실패`가 반복될 때만 tuning pilot을 검토한다.
