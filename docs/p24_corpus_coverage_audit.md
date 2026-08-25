# P24-A: 원문·Corpus 근거 커버리지 감사

## 목적

P23에서 근거 부족 또는 불완전으로 분류된 복합 질의 네 건(R-010, R-024, R-028, R-037)을 대상으로, 실패 위치를 원문부터 P22 후보 집합까지 추적했다. 이 감사는 검색, 매처, 프롬프트, HCX 호출을 변경하지 않는다.

판정 순서는 다음과 같다.

```text
원본 제공 문서
→ Parsed Corpus
→ P22 retrieval 후보
→ 선택된 근거와 requirement slot 매칭
```

`exact gold chunk`가 후보에 없더라도 질문에 필요한 사실을 지지하는 동등 근거가 후보에 있다면 retrieval 성공으로 본다. 이 구분은 데이터·파싱 문제를 검색 또는 매칭 문제로 잘못 진단하지 않기 위해 필요하다.

## 결과 요약

| 분류 | 건수 | 질문 |
|---|---:|---|
| 실제 데이터 부재 | 0 | - |
| 파싱/OCR/표 추출 누락 | 0 | - |
| Retrieval recall | 2 | R-024, R-037 |
| Evidence matcher | 2 | R-010, R-028 |

네 사례 모두 원문과 현재 Corpus에 질문에 필요한 근거가 있다. 따라서 이 표본에서 OCR 또는 원문 데이터 보강은 우선순위가 아니다.

## 케이스별 추적

| ID | 원문·Corpus | P22 후보/선택 상태 | 주 원인 | 결론 |
|---|---|---|---|---|
| R-010 | `doc20.docx`에 연금외수령, 기타소득세, 부득이한 사유가 있고 두 gold chunk도 존재 | 선택된 표에 `연금외수령시 과세`, `부득이한 연금외수령 사유`가 있음 | evidence matcher | `해지` + `부득이한 사유`라는 좁은 lexical slot이 의미상 동등한 예외 근거를 놓침 |
| R-024 | 상품 PDF 1·5쪽에 4등급/보통위험과 달러표시 채권 투자 근거가 있으며 두 chunk 존재 | 투자대상은 선택됐지만 위험등급 chunk가 후보에 없음 | retrieval recall | 파싱이나 OCR 문제가 아닌 위험등급 필드 회수 실패 |
| R-028 | 상품 PDF 17쪽 및 gold chunk에 국내 주식 투자와 운용전략 근거가 존재 | 38쪽의 동등 표 chunk가 선택되어 국내 주식 투자와 운용전략을 모두 포함 | evidence matcher | `투자대상`이라는 필드명 부재만으로 target slot을 불충족 처리 |
| R-037 | `doc11.pdf` 1쪽 비교표와 해당 Corpus chunk에 DB=회사, DC=근로자 운용 주체가 존재 | 해당 표 또는 동등 근거가 후보에 없음 | retrieval recall | ‘회사/내가 직접 굴리는’ 우회 표현에서 DB/DC 운용 주체 표를 회수하지 못함 |

## 원문 확인 방법

- PDF는 PyMuPDF의 native text 추출로 해당 페이지를 확인했다.
- DOCX는 문단 및 실제 Word 표의 텍스트를 함께 확인했다.
- 결과는 단어 존재 여부와 원본 위치만 기록한다. 원문 전체나 진단 추출 텍스트는 저장소에 복제하지 않는다.

재현 명령:

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
python3 scripts/audit_p24_corpus_coverage.py
```

기계 판정 결과는 [p24_corpus_coverage_audit.json](../evaluation/p24_corpus_coverage_audit.json)에 저장된다.

## 의사결정

1. 이 네 사례에 대해 OCR을 시작하지 않는다. 원문과 Corpus 모두 native text로 확인됐다.
2. R-024와 R-037은 다음 Retrieval backlog로 분리한다.
   - R-024: 상품코드 질의에서 위험등급 필드를 후보 집합으로 회수
   - R-037: 구어체 운용 주체 비교 표현에서 DB/DC 비교표를 회수
3. R-010과 R-028은 Retrieval 자체를 다시 튜닝하기 전에 requirement-to-evidence matcher의 의미 동등성 정책을 별도 실험한다. gate를 완화하거나 없는 근거를 충족으로 처리하지 않는다.
4. P24-B citation 계약, P24-C provider 안정성은 이 감사 결과와 분리해 진행한다.

## 한계

이 감사는 네 개의 P23 compound 사례를 대상으로 한 원인 분리다. 전체 자료의 OCR 필요성 또는 전체 Corpus coverage 비율을 추정하지 않는다. 이후 OCR 우선순위는 별도 페이지 수준 OCR triage 결과와 함께 판단해야 한다.
