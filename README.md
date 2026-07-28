# Pension Agent

제10회 2026 미래에셋증권 AI Festival 연금 Agent 프로젝트입니다. 사측 제공 연금 문서를 검색하고, 근거와 위치를 표시하는 답변을 생성합니다.

## Repository boundaries

- GitHub Private Repository: 코드, 설정, 기술 문서의 기준 저장소
- Google Drive: 사측 제공 원본 데이터의 읽기 전용 위치
- `data/parsed`, `data/indexes`: 로컬에서 생성되는 파싱 결과와 검색 인덱스
- HyperCLOVA X: 제출 Agent의 답변 생성 LLM

원본 문서와 API 키는 Git에 커밋하지 않습니다. 자세한 제약은 [AGENTS.md](AGENTS.md)를 따릅니다.

## Quick start

1. Google Drive 데스크톱 앱에서 사측 `연금` 폴더를 로컬에 동기화합니다.
2. 환경 파일을 만들고 로컬 경로와 HyperCLOVA X 자격 증명을 채웁니다.

   ```bash
   cp .env.example .env
   ```

3. `.env`의 `PENSION_DATA_ROOT`를 동기화된 Drive 폴더의 절대 경로로 변경합니다.

`PENSION_DATA_ROOT`는 읽기 전용 원본 위치이며, 생성 파일은 `PARSED_DATA_ROOT`와 `INDEX_DATA_ROOT`에만 저장해야 합니다.

## Data inventory

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
- `data/representative_documents.csv`: 메타데이터로 선정한 최대 10개 대표 문서 후보
- `data/representative_document_requirements.csv`: 사람이 확인해 채울 파싱 요구사항 표

대표 문서의 표·이미지·스캔 여부는 파일명과 크기만으로 확정할 수 없습니다. 후보를 연 뒤 마지막 CSV의 `not_reviewed` 값을 검토 결과로 바꿉니다.

## Layout

```text
src/           Application modules
scripts/       Operational scripts
tests/         Automated tests
evaluation/    Evaluation data and code
data/raw/      Optional local raw-data placeholder (ignored by Git)
data/parsed/   Generated parsed documents (ignored by Git)
data/indexes/  Generated retrieval indexes (ignored by Git)
docs/          Project documentation
```

## Before the first push

Review the staged files and confirm that no source documents, generated indexes, or `.env` file are included.

```bash
git status
git add AGENTS.md README.md .gitignore .dockerignore .env.example requirements.txt Dockerfile \\
  src scripts tests evaluation docs data/raw/.gitkeep data/parsed/.gitkeep data/indexes/.gitkeep
git diff --cached
```
