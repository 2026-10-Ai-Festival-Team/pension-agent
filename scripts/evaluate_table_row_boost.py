"""Evaluate BM25 table-row-key weights on dev only."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_dataset import load_dataset_metadata, load_questions
from src.evaluation.retrieval_evaluator import evaluate_retriever, load_saved_retriever, sha256_file, summarize_results
from src.retrieval.fielded_bm25_index import TableRowKeyIndex
from src.retrieval.fielded_bm25_retriever import FieldedBm25Retriever
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
from src.retrieval.tokenizer import SimpleKoreanTokenizer

p=argparse.ArgumentParser(); p.add_argument("--corpus",type=Path,default=Path("data/parsed/chunks.jsonl")); p.add_argument("--base-index",type=Path,default=Path("data/indexes/bm25/simple")); p.add_argument("--row-key-index",type=Path,required=True); p.add_argument("--output",type=Path,default=Path("data/diagnostics/table_row_boost.json")); p.add_argument("--report",type=Path,default=Path("docs/experiments/bm25_004_table_row_boost.md")); a=p.parse_args()
sha=sha256_file(a.corpus)
if load_dataset_metadata(Path("evaluation/retrieval_dataset_meta.json"))["corpus_sha256"]!=sha: raise RuntimeError("평가셋과 Corpus SHA-256이 일치하지 않습니다.")
chunks=load_chunks(a.corpus); token=SimpleKoreanTokenizer(); base=load_saved_retriever(a.base_index,chunks,token,sha).index; rows=TableRowKeyIndex.load(a.row_key_index,chunks,token,sha); retriever=FieldedBm25Retriever(base,rows); questions=[q for q in load_questions(Path("evaluation/retrieval_questions.jsonl")) if q.split=="dev"]
weights=(0.0,0.25,0.5,0.75,1.0); result={}
for weight in weights:
    evaluated=evaluate_retriever(questions, lambda_search:=type("R",(),{"search":lambda _,q,top_k,query_normalizer=None: retriever.search(q,top_k,weight,query_normalizer)})(),10,build_default_pension_query_normalizer())
    result[str(weight)]={"summary":summarize_results(evaluated),"rows":evaluated}
a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
lines=["# BM25-004: Table Row-Key Boosting","","## Scope","","- 원본 Corpus·Simple·`pension-v1`을 유지했고 dev 30개만 평가했다.","","## Weight Results","","| Variant | Weight | R@5 | R@10 | MRR |","|---|---:|---:|---:|---:|"]
for weight,item in result.items():
 s=item["summary"]; lines.append(f"| RK{int(float(weight)*100):03d} | {weight} | {s['direct_hit_at_5']*100:.1f}% | {s['direct_hit_at_10']*100:.1f}% | {s['direct_mrr']:.3f} |")
lines += ["","## Decision","","결과 파일의 질문별 순위와 회귀를 검토한 뒤 채택 여부를 결정한다."]
a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
