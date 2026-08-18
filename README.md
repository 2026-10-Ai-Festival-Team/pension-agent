# Pension AI Agent Baseline

2026 미래에셋증권 AI Festival 연금 AI Agent 과제를 위한 최소 RAG 베이스라인입니다. 답변 생성 LLM은 HyperCLOVA X만 사용하며 웹 검색이나 다른 LLM API는 포함하지 않습니다.

> 현재 원본 158개(PDF 137, DOCX 18, XLSX 2, PPTX 1)를 파싱해 12,815개 chunk와 실제 문서 근거 기반 평가문제 30개를 구축했습니다.

## Architecture

```text
Question
  -> Question Analyzer (HyperCLOVA X, 실패 시 보수적 fallback)
  -> 1~3 Search Queries
  -> BM25 Retriever
  -> Evidence
  -> ANSWER / CLARIFY / ABSTAIN
  -> HyperCLOVA X Grounded Answer
```

검색기는 교체 가능한 `Retriever` 인터페이스를 사용합니다. baseline 한국어 토큰화는 어절·숫자·한글 bi-gram 조합이며, 모든 chunk는 문서 ID, 파일명, 페이지를 보존합니다. `eval/`은 평가 스크립트만 읽으며 production pipeline에서는 접근하지 않습니다.

## Setup

```bash
cd /home/yewon/jupyter/aset/pension-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

노트북에 있던 기존 API 키는 노출된 것으로 보고 폐기·재발급해야 합니다. 새 키는 Git에 포함되지 않는 `.env`에만 입력합니다. `HCX_API_KEY`에는 `Bearer ` 접두사가 있어도 없어도 됩니다.

## Data preparation

대회에서 제공한 원본 PDF, CSV, JSON, TXT, Markdown, XLSX 파일 전체를 `data/raw/` 아래에 원래 폴더 구조를 유지해 복사합니다. 이후 다음을 실행합니다.

```bash
python scripts/inspect_data.py
python scripts/build_index.py
```

`inspect_data.py`는 `data/metadata/document_inventory.csv`를 생성합니다. 자동으로 확정할 수 없는 문서 유형, 주제, 상품명, 시행일은 `unclassified` 또는 빈 값으로 남겨 수동 검토 대상으로 표시합니다. 표 자료는 원문과 index 결과를 반드시 표본 검수하세요.

## Evaluation dataset

실제 문서를 읽고 `eval/SCHEMA.md`의 분포와 schema에 맞춰 `eval/eval_questions.json`, `eval/eval_questions.csv`, `eval/gold_evidence.json`을 작성합니다. 문서가 없을 때 `generate_eval_set.py`는 임의 정답 생성을 거부합니다.

```bash
python scripts/generate_eval_set.py
python scripts/run_eval.py
```

`run_eval.py`는 Recall@1/3/5/10, MRR, 행동 정확도와 confusion matrix를 출력하고 `eval/results/baseline_results.json` 및 CSV를 저장합니다.

## Run server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
curl --get http://localhost:8000/answer \
  --data-urlencode 'question_id=Q-001' \
  --data-urlencode 'question=DC와 DB의 차이가 무엇인가요?'
```

Index가 없거나 근거가 검색되지 않으면 서버는 500 오류 대신 `ABSTAIN` 답변을 반환합니다. 추천에 필요한 조건이 부족하면 `CLARIFY`로 역질문합니다. `think_trace`는 내부 사고과정이 아닌 intent, 검색어, 사용 문서, 행동, 검증 항목의 JSON 문자열입니다.

## Test

```bash
pytest -q
```

테스트는 HyperCLOVA X를 실제 호출하지 않습니다.

## Docker

```bash
docker build -t pension-agent .
docker run --env-file .env -p 8000:8000 pension-agent
curl http://localhost:8000/health
```

## Environment variables

- `HCX_API_KEY`, `HCX_REQUEST_ID`: 필수 인증값
- `HCX_ENDPOINT`, `HCX_MODEL`: API endpoint와 모델
- `HCX_TIMEOUT_SECONDS`, `HCX_MAX_RETRIES`: timeout과 제한 재시도
- `RETRIEVAL_TOP_K`: 기본 검색 결과 수
- `MAX_QUESTION_LENGTH`: 입력 길이 상한

## Known limitations

- 현재 평가는 HCX 인증값 없이 retrieval과 보수적 fallback 행동을 측정했으며, 실제 생성 답변 품질 평가는 유효한 HCX 환경변수 설정 후 재실행해야 합니다.
- 일반 PDF text extraction만 제공하므로 복잡한 표는 파싱 품질 수동 검수가 필요합니다.
- lexical retrieval만 포함하며 reranker, vector DB, 멀티에이전트, 웹 검색은 의도적으로 제외했습니다.
