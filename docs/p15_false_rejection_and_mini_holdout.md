# P15: False Rejection 분리 수정 및 Mini-holdout 검증

## 목적과 고정 범위

P14에서 남은 false rejection 두 건을 서로 다른 계층으로 분리해 진단·수정했다.

- **P15-A / H-009**: 지원 범위 분류의 한국어 소유어 경계
- **P15-B / H-015**: requirement별 evidence candidate 부족
- **P15-C**: 새 12문항 mini-holdout으로 Router/Gate만 재검증

전역 BM25 파라미터, tokenizer, Corpus, chunking, production `PensionAgent`, HCX 요청,
prompt, citation validator, Fail-Closed 정책은 변경하지 않았다. 모든 평가는 HCX를 호출하지
않는 offline shadow다.

## P15-A: H-009 지원 범위 오분류

H-009는 문서 기반으로 답할 수 있는 DB/DC 제도 비교다. P14의
`personal_account_lookup` 판정은 `제`를 단순 부분문자열로 찾으면서 `DB제도`의 `제`를
소유 대명사로 잘못 읽은 구현 결함이었다.

수정은 특정 질문 또는 특정 제도명을 예외 처리하지 않았다. 한국어 소유 표현만 다음 경계에서
인식하도록 했다.

```text
제 IRP 계좌 / 제가 다니는 회사 / 내 계좌 / 우리 회사
```

따라서 `제도`, `세액공제`처럼 명사 내부에 포함된 `제`는 개인계좌 요청으로 분류하지 않는다.
P13의 실제 개인계좌 2건과 최신·예측·무조건 추천 unsupported 사례는 계속 reject된다.

## P15-B: H-015 evidence 후보 진단과 보강

원 질문의 BM25 Top-10에는 연령·기간을 같이 뒷받침하는 IRP 법정 수급요건이 없었다.
Top-10의 `최소 5년` 표는 구(舊) 개인연금저축 자료로 IRP 근거로 사용할 수 없었다. 따라서
matcher 완화나 gate 완화는 안전하지 않다.

Corpus에는 다음 직접 근거가 존재했다.

```text
개인형퇴직연금제도(IRP) / 근로자퇴직급여 보장법 시행령 제18조
55세 이상 가입자에게 지급, 연금 지급기간은 5년 이상
```

P15는 `IRP 연금 연령·기간` requirement에만 canonical query
`개인형퇴직연금 연금 지급기간 5년 이상`으로 같은 frozen BM25를 추가 호출하는 experimental
candidate expansion을 적용했다. 원 질문 Top-10은 그대로 보존하고, 확장 후보도 selector의
IRP·55세·5년·연금 조건을 모두 충족할 때만 선택된다.

H-015는 이 방식으로 `ef05c9c97fbadd27-paragraph_group-98497575ff11`을 선택했으며,
두 requirement slot이 모두 충족됐다. 없는 근거를 통과시키는 예외는 추가하지 않았다.

## P13 development 회귀

P13은 수정 설계에 사용됐으므로 일반화 성능으로 해석하지 않는다. baseline artifact는 보존했고,
P15 결과는 별도 파일로 저장했다.

| Metric | P14 | P15 development regression |
|---|---:|---:|
| Routing accuracy | 19/20 (95.0%) | 20/20 (100.0%) |
| Compound recall | 7/8 (87.5%) | 8/8 (100.0%) |
| Unsupported recall | 4/4 | 4/4 |
| False rejection | 2/16 (12.5%) | 0/16 |
| Unsafe pass | 0/4 | 0/4 |
| Requirement-slot recall | 16/19 (84.2%) | 19/19 (100.0%) |

H-009의 추가 `dc_benefit` slot 하나는 P13 gold slot보다 더 세분화된 requirement 표현이라
generation recall에는 영향이 없지만, P13의 슬롯 정의가 완전한 reference schema가 아니라는
한계로 별도 기록했다.

## P15-C: 독립 mini-holdout

P13/P14의 문항과 다른 표면 표현으로 구성한 12개 질의를 평가했다. 이 세트는 P15 구현을
완료한 뒤 최초 1회 실행했으며, 결과를 보고 추가 규칙을 조정하지 않았다.

| Route / policy group | Questions | Result |
|---|---:|---:|
| Simple (근거 충분 3 + insufficient 1) | 4 | routing 4/4, insufficient reject 1/1 |
| Compound | 5 | routing 5/5, slot coverage 14/14 |
| Unsupported | 3 | routing/reject 3/3 |
| Total | 12 | routing 12/12, false rejection 0, unsafe pass 0 |

추가 지표는 다음과 같다.

| Metric | P15 mini-holdout |
|---|---:|
| Routing accuracy | 12/12 (100.0%) |
| Compound recall | 5/5 (100.0%) |
| Unsupported recall | 3/3 (100.0%) |
| Entity precision / recall | 100.0% / 100.0% |
| False rejection | 0/8 |
| Unsafe pass | 0/4 |
| Requirement-slot recall | 14/14 (100.0%) |

이 mini-holdout은 작고 1인 수동 라벨이라는 한계가 있어 최종 발표 수치나 일반화 보장으로
사용하지 않는다. 다만 P13의 두 false rejection 수정이 다른 표면 표현에서도 같은 안전 정책을
유지하는지 확인한 독립 offline check다.

## 판단

**P15 Router/Gate 실험은 통과. P16 HCX Shadow E2E의 진입 조건을 충족했다.**

단, 이번 결과는 production 통합 자체가 아니다. P16에서는 baseline Agent와 conditional-routing
shadow를 같은 고정 설정으로 비교하고, 실제 semantic correctness·requirement coverage·citation
support·Strict End-to-End Useful Answer Rate를 별도로 측정해야 한다.

## 재현

```bash
# P15 development regression — P13 baseline 파일을 덮어쓰지 않는다.
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py \
  --requirement-retrieval-top-k 5 \
  --output evaluation/p15_p13_development_results.jsonl

# P15 independent mini-holdout
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py \
  --questions evaluation/p15_mini_holdout_questions.json \
  --labels evaluation/p15_mini_holdout_labels.json \
  --requirement-retrieval-top-k 5 \
  --output evaluation/p15_mini_holdout_results.jsonl
```
