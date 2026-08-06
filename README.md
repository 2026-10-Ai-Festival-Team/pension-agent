# 연금 Agent

제10회 2026 미래에셋증권 AI Festival 연금 Agent 프로젝트입니다. 사측 제공 연금 문서를 검색하고, 근거와 위치를 표시하는 답변을 생성합니다.

## 저장소 범위

- GitHub 비공개 저장소: 코드, 설정, 기술 문서의 기준 저장소
- `data/raw/연금`: 저장소에 포함되는 사측 제공 원본 데이터의 읽기 전용 위치
- `data/parsed`, `data/indexes`: 로컬에서 생성되는 파싱 결과와 검색 인덱스
- HyperCLOVA X: 제출 Agent의 답변 생성 LLM

API 키와 생성된 파싱·인덱스·진단 산출물은 Git에 커밋하지 않습니다. 원본 문서는 `data/raw/연금`에 변경 없이 포함합니다. 자세한 제약은 [AGENTS.md](AGENTS.md)를 따릅니다.

## 빠른 시작

1. 환경 파일을 만들고 HyperCLOVA X 자격 증명을 채웁니다.

   ```bash
   cp .env.example .env
   ```

3. `.env`의 `PENSION_DATA_ROOT`는 저장소 내 상대 경로로 유지합니다.

`PENSION_DATA_ROOT`는 읽기 전용 원본 위치이며, 생성 파일은 `PARSED_DATA_ROOT`와 `INDEX_DATA_ROOT`에만 저장해야 합니다.

## API 실행과 Docker

Corpus와 Simple BM25 인덱스를 생성한 뒤 개발 Smoke Test에는 `GENERATOR_BACKEND=fake`를 설정합니다.

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

컨테이너에는 원문·Corpus·인덱스를 포함하지 않습니다. 생성 데이터를 읽기 전용으로 마운트합니다.

```bash
docker build -t pension-agent .
docker run --rm -p 8000:8000 --env-file .env \
  -v "$(pwd)/data/parsed:/app/data/parsed:ro" \
  -v "$(pwd)/data/indexes:/app/data/indexes:ro" \
  pension-agent
```

필수 Corpus 또는 인덱스가 없으면 앱은 시작 시 실패합니다. evaluation/production 환경의 HCX 백엔드는 `feature/hcx-generation` 병합 후 활성화합니다. `.env`와 API 키는 이미지와 Git에 포함하지 않습니다.

### 검색 산출물 준비

컨테이너를 시작하려면 아래 파일이 필요합니다.

```text
data/parsed/chunks.jsonl
data/indexes/bm25/simple/index_meta.json
data/indexes/bm25/simple/tokenized_documents.jsonl
```

재생성 환경에서는 원본 문서를 준비한 뒤 다음을 실행합니다.

```bash
python scripts/build_corpus.py --all --output data/parsed/chunks.jsonl --report docs/corpus_build_report.md
python scripts/build_bm25_index.py \
  --corpus data/parsed/chunks.jsonl \
  --output data/indexes/bm25/simple \
  --tokenizer simple
```

검증 기준은 청크 23,421개와 아래 Corpus SHA-256입니다.

```text
c61ac0d54dc9af5ee339460b8b810076f6df998c76f54983d667660a1e8eaead
```

```bash
wc -l data/parsed/chunks.jsonl
sha256sum data/parsed/chunks.jsonl  # macOS: shasum -a 256 사용
```

시작 전 검증에서 Corpus 또는 인덱스가 없으면 `Required corpus or BM25 index is missing` 오류로 안전하게 종료됩니다. 대용량 산출물을 별도 스토리지로 제공하는 경우에도 위 상대 경로에 마운트한 뒤 같은 검증값을 확인합니다.

## 데이터 인벤토리

문서 파싱이나 모델 호출 전에 원본의 파일 구조를 인벤토리로 확인합니다. 원본은 읽기만 하며, 결과 파일에는 절대 경로를 기록하지 않습니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/check_data_path.py
python3 scripts/build_manifest.py
python3 scripts/analyze_inventory.py
```

위 명령은 다음 파일을 만듭니다.

- `data/manifest.csv`: 원본 파일의 상대 경로와 메타데이터
- `data/inventory_report.md`: 파일 형식, 상품코드 폴더, 빈 폴더, 중복 파일명, 대용량 파일 통계
- `data/representative_documents.csv`: 메타데이터로 선정한 12개 대표 문서 후보 (XLSX 2개 포함)
- `data/representative_document_requirements.csv`: 사람이 확인해 채울 파싱 요구사항 표

대표 문서의 표·이미지·스캔 여부는 파일명과 크기만으로 확정할 수 없습니다. 후보를 연 뒤 마지막 CSV의 `not_reviewed` 값을 검토 결과로 바꿉니다.

## 디렉터리 구조

```text
src/           애플리케이션 모듈
scripts/       운영 스크립트
tests/         자동화 테스트
evaluation/    평가 데이터와 코드
data/raw/      버전 관리되는 읽기 전용 사측 원본 문서
data/parsed/   생성된 파싱 문서(Git 제외)
data/indexes/  생성된 검색 인덱스(Git 제외)
docs/          프로젝트 문서
```

## 첫 Push 전 확인

Review the staged files and confirm that no `.env` file or generated artifact is included.

```bash
git status
git add AGENTS.md README.md .gitignore .dockerignore .env.example requirements.txt Dockerfile \\
  src scripts tests evaluation docs data/raw
git diff --cached
```
