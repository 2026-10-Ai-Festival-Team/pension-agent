# P9: Routing/Gate 안정화 진단

## 목적

P8-B의 minimal citation representation은 compound 경로에서 검증됐지만, conditional routing을 production Agent에 넣기 전 simple/control 질의의 실패 소유자를 분리했다.

이번 단계에서는 router, retriever, EvidenceAssessor, context selection, HCX schema 중 어느 층의 문제인지 진단만 수행했다. Production Agent와 validator를 변경하거나 HCX를 추가 호출하지 않았다.

## Gold routing label

15개 control/compound/unsupported 사례에 대해 변경 전에 사람이 route를 `simple`, `compound`, `unsupported`로 고정했다. 비교 문구가 있어도 하나의 표로 완결되는 R-001은 `simple`로 분류했다.

| Metric | Result |
|---|---:|
| Gold route 일치 | 10/15 (66.7%) |
| Routing misclassification | 5 |
| Current gate false rejection | 0 |
| Current gate unsafe pass | 4 |

현재 `QueryAnalyzer`는 DB/DC가 한글 조사와 붙을 때 entity regex를 놓치며, 두 개 이상의 질문 요구가 있어도 대체로 `simple`로 분류한다.

## Gate 상태

| Gate state | Count | Cases |
|---|---:|---|
| retrieval sufficient + gate pass | 9 | R-001, R-002, R-003, R-004, R-007, R-009, R-011, R-013, R-027 |
| retrieval insufficient + gate pass | 4 | R-010, R-024, R-028, R-037 |
| retrieval insufficient + gate reject | 2 | R-039, R-040 |

즉 현재 production EvidenceAssessor의 핵심 문제는 지나친 보수성(false rejection)이 아니라, 비어 있지 않은 Context만 있으면 충분하다고 보는 **unsafe pass**다. R-039·R-040의 unsupported/personal 정책 gate는 정상적으로 작동한다.

P8-B의 R-009 차단은 production gate 결과가 아니다. 단순 세제 질의를 experimental compound completeness gate에 잘못 넣은 routing 실험 오류이며, future router가 simple 경로로 보내야 한다.

## 실패 소유자

| Primary owner | Count | Cases | Root cause |
|---|---:|---|---|
| router | 4 | R-002, R-009, R-027, R-028 | compound 요구를 simple로 분류하거나 simple 질의를 compound gate에 보냄 |
| retrieval | 2 | R-010, R-024 | 필요한 evidence 자체가 현재 후보에 없음 |
| gate | 1 | R-037 | retrieval 부족인데 non-empty Context만으로 통과 |
| selection | 1 | R-004 | 최소 부담금 근거 대신 답변 불가 표를 선택 |
| generation schema | 1 | R-001 | A/B 공통 structured-output failure |
| none / 정상 | 6 | R-003, R-007, R-011, R-013, R-039, R-040 | 이 subset에서 primary failure 없음 |

각 case의 gold route, 현재 route, retrieval 여부, selected context, gate decision, P8-B outcome은 Git 제외 `data/diagnostics/p9_routing_gate_analysis.json`에 기록했다.

## 핵심 진단

### Router

가장 큰 수정 후보는 LLM이나 BM25가 아니라 **router feature**다.

- `DB형`, `DC형`처럼 한글에 붙은 약어를 entity로 인식하지 못한다.
- `투자대상과 운용전략`, `원리금보장과 채권형`처럼 둘 이상의 independent requirement를 현재 Analyzer가 compound로 표시하지 못한다.
- R-009은 one-table tax fact인데 compound gate로 보내면 false rejection이 된다.

### Gate

현재 `EvidenceAssessor`의 comparison 검사도 Analyzer entity 결과에 의존한다. R-037은 comparison route처럼 보이지만 Analyzer가 DB/DC entity를 얻지 못해 evidence completeness를 검사하지 않고 통과했다.

Compound gate는 requirement slot completeness를 검사해야 하지만, simple gate는 product-code match와 compact direct context 존재 여부만 평가해야 한다. 두 경로에 같은 기준을 강제하면 R-009 같은 false rejection이 생긴다.

### Selection과 schema

R-004는 retrieval/gate가 아닌 requirement-specific selection 문제다. 질문의 ‘최소 얼마’ 조건을 표현하는 evidence selection rule이 없어 관련 없는 Context로 답변을 생성했다.

R-001의 structured-output failure는 A/B representation 모두에서 발생했다. P8-B의 citation representation 효과와 분리해 provider/schema 관측 backlog로 남긴다.

## Production routing blocker

Conditional routing을 지금 구현하면 다음 두 문제가 남는다.

1. compound를 안정적으로 감지하지 못해 R-002·R-027·R-028을 simple 경로로 보낼 수 있다.
2. compound evidence completeness가 현재 Agent gate에 연결되어 있지 않아 R-037처럼 근거 부족 상태를 통과시킬 수 있다.

따라서 P9의 결론은 **production routing blocked**다.

## 최소 수정 후보 (구현 보류)

1. Korean-boundary-safe DB/DC/IRP entity extraction
2. rule-based requirement count로 `simple`/`compound` route 분리
3. route별 gate 분리
   - simple: direct/product evidence 존재 여부
   - compound: 모든 required evidence slot completeness
4. R-004용 ‘최소 부담금’ requirement/evidence rule을 retrieval·selection 실험에서 따로 검증
5. R-001 schema failure는 prompt 변경과 분리된 재현 관측

## Conditional routing 후보 설계

```text
simple
→ frozen BM25
→ compact context
→ simple evidence gate
→ existing HCX path

compound
→ requirement decomposition
→ per-requirement retrieval
→ merged evidence
→ compound completeness gate
→ minimal citation representation
→ HCX + Fail-Closed validation

unsupported / insufficient
→ pre-generation rejection
```

위 설계는 P9 이후 별도 branch에서 unit·offline test로 먼저 검증해야 한다. 이 보고서 자체는 설계·진단이며 production 구현을 포함하지 않는다.
