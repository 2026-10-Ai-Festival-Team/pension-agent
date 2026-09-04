# Bounded Answer Policy

## 목적

근거가 일부 부족한 경우에도 확인된 원본 근거를 버리지 않고, 확인할 수 없는
항목을 명시한 뒤 검증된 범위까지만 답한다. 이 정책은 추천·개인 세무 판단·외부
예측처럼 사용자 조건 또는 서비스 범위 자체가 문제인 요청을 완화하지 않는다.

## Evidence outcome

| Evidence status | Outcome | 동작 |
| --- | --- | --- |
| `full` | `supported_answer` | 기존의 근거 기반 정상 답변 |
| `partial` | `bounded_answer` | 확인 불가 requirement 고지 + 지원 requirement만 답변 |
| `none` | `no_evidence_boundary` | 핵심 정보를 확인할 수 없다고 고지하고 추측 금지 |

`partial`은 requirement-aware matcher가 primary-original chunk에 직접 결속한
지원 requirement가 하나 이상 있을 때만 가능하다. 관련 있어 보이는 일반 안내문,
다른 상품·제도 문서, 보강 자료만으로는 `partial`을 만들지 않는다.

## Writer contract

`bounded_answer`에서는 HCX에 다음만 전달한다.

- matcher가 확정한 지원 requirement와 해당 원본 context
- 사용자에게 공개할 확인 불가 requirement 이름
- context에 없는 값·조건·미래 결과를 만들지 않는다는 지시

응답은 `[답변] / [근거] / [유의사항]` 형식을 유지한다. 한계 고지는 policy가
생성문 앞에 붙여 모델이 누락하더라도 숨겨지지 않으며, citation validator는 기존과
같이 실제 입력 context의 primary-original chunk만 허용한다.

## 제외 경로

- 추천 또는 개인 조건 부족: `clarification_required`
- 개인계좌 조회·실시간 외부 정보·프롬프트 공격: 기존 safe block
- primary-original 근거 부재: 기존 fail-closed
- Generator/schema/citation 검증 실패: 기존 generation failure 안내

## 관찰 필드

candidate trace에는 `evidence_status`, `outcome`,
`supported_requirement_slots`, `missing_requirement_slots`를 남긴다.
이 필드는 partial answer가 근거 부족을 정상 답변처럼 표시하지 않았는지 운영에서
점검하는 데 사용한다.
