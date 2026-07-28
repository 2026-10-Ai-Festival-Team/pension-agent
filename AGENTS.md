# Pension Agent Project Instructions

## Project

제10회 2026 미래에셋증권 AI Festival의 연금 Agent 과제다.

## Core Goal

사측이 Google Drive로 제공한 연금 상품·제도·세제 문서를 검색하고,
자연어 질의에 대해 근거 기반 답변을 생성하는 AI Agent를 개발한다.

## Mandatory Constraints

1. 제출 시스템에서 사용하는 LLM은 HyperCLOVA X로 제한한다.
2. 다른 LLM을 평가용 실행 파이프라인에 포함하지 않는다.
3. 답변은 사측 제공 문서를 최종 근거로 사용한다.
4. 문서에 없는 사실을 생성하지 않는다.
5. 정보가 부족하면 한계를 고지하거나 필요한 조건을 질문한다.
6. 단정적인 금융상품 추천을 하지 않는다.
7. 모든 답변에 근거 문서와 근거 위치를 표시한다.
8. `data/raw/연금`의 원본 데이터는 Git으로 배포하되, 수정하지 않고 읽기 전용으로 취급한다.
9. API 응답은 `question_id`, `question`, `retrieved_context`, `think_trace`, `answer` 필드를 지원한다.

## Data Structure

- `data/raw/연금`: 저장소에 포함되는 사측 원본 데이터
- `data/parsed`: 파싱·정제된 데이터
- `data/indexes`: 검색 인덱스
- `evaluation`: 내부 평가셋과 평가 코드

## Development Rules

- 코드 변경 후 테스트를 실행한다.
- 비밀키와 생성된 파싱·인덱스·진단 산출물은 Git에 커밋하지 않는다.
- `data/raw/연금`의 사측 원본은 변경 없이 저장소에 포함한다.
- 파서 결과에는 `source_id`, 파일명, 페이지, 섹션 정보를 보존한다.
- 검색 품질을 생성 답변 품질과 분리하여 평가한다.
