"""Run a reproducible retrieval ablation and emit JSON + Markdown reports."""
from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

MODES = ("bm25", "bm25_rewrite", "dense", "hybrid_raw", "hybrid", "full")
LABELS = {
    "bm25": "BM25 baseline",
    "bm25_rewrite": "BM25 + query rewrite",
    "dense": "Dense only",
    "hybrid_raw": "BM25 + Dense + RRF",
    "hybrid": "Rewrite + BM25 + Dense + RRF",
    "full": "Full pipeline (+ conservative rerank)",
}
METRICS = ("recall_at_k", "precision_at_k", "mrr", "ndcg_at_k")


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def pct_change(value: float, baseline: float) -> float | None:
    return round((value / baseline - 1) * 100, 2) if baseline else None


def score(retrieved: list[str], relevant: set[str], k: int) -> dict[str, float]:
    hits = [item in relevant for item in retrieved[:k]]
    recall = sum(hits) / max(len(relevant), 1)
    precision = sum(hits) / k
    reciprocal = next((1 / rank for rank, hit in enumerate(hits, 1) if hit), 0.0)
    dcg = sum((1 if hit else 0) / math.log2(rank + 1) for rank, hit in enumerate(hits, 1))
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return {
        "recall_at_k": recall,
        "precision_at_k": precision,
        "mrr": reciprocal,
        "ndcg_at_k": dcg / ideal if ideal else 0.0,
    }


def request_with_retry(client: httpx.Client, payload: dict, attempts: int = 4) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            response = client.post("/api/v1/search", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            if attempt == attempts:
                raise
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError("unreachable")


def markdown(report: dict) -> str:
    base = report["results"]["bm25"]["metrics"]
    modes = report["modes"]
    lines = [
        "# RAGForge Retrieval Baseline / Ablation Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Git revision: `{report['environment']['git_revision']}`",
        f"- Dataset: `{report['dataset']['name']}` / `{report['dataset']['questions_file']}` "
        f"({report['dataset']['documents']} documents, "
        f"{report['dataset']['questions']} questions)",
        f"- Knowledge base: `{report['knowledge_base_id']}`",
        f"- K: `{report['k']}`; retrieve_k: `{report['retrieve_k']}`",
        "- Baseline: `BM25` on the original query",
        "",
        "## Absolute metrics",
        "",
        "| Variant | Recall@10 | Precision@10 | MRR | NDCG@10 | Time |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in modes:
        item = report["results"][mode]
        m = item["metrics"]
        lines.append(
            f"| {LABELS[mode]} | {m['recall_at_k']:.4f} | {m['precision_at_k']:.4f} | "
            f"{m['mrr']:.4f} | {m['ndcg_at_k']:.4f} | {item['elapsed_seconds']:.1f}s |"
        )
    lines += [
        "",
        "## Relative change vs. BM25 baseline",
        "",
        "| Variant | Recall | Precision | MRR | NDCG |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode in modes[1:]:
        m = report["results"][mode]["metrics"]
        values = [pct_change(m[key], base[key]) for key in METRICS]
        formatted = ["n/a" if value is None else f"{value:+.2f}%" for value in values]
        lines.append(f"| {LABELS[mode]} | " + " | ".join(formatted) + " |")
    lines += [
        "",
        "## Variant definition",
        "",
        "- **BM25 baseline:** original query, lexical retrieval only.",
        "- **BM25 + query rewrite:** rewritten query, lexical retrieval only.",
        "- **Dense only:** original query, pgvector cosine retrieval only.",
        "- **Raw hybrid:** original query, BM25 and dense retrieval, then RRF fusion.",
        "- **Rewrite hybrid:** rewritten query, BM25 and dense retrieval, then RRF fusion.",
        "- **Full:** rewrite hybrid followed by a CrossEncoder/base-rank blended reranker.",
        "",
        "## Reproduce",
        "",
        "```bash",
        report["reproduce_command"],
        "```",
        "",
        "The JSON file beside this report is the machine-readable source of truth. "
        "All variants use the same knowledge-base image, questions, relevance labels, K, and API process.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--knowledge-base-id", default="auto")
    parser.add_argument("--dataset", default="ragforge-zh-v1")
    parser.add_argument("--questions-file", choices=("qa.jsonl", "qa_hard.jsonl"), default="qa_hard.jsonl")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--retrieve-k", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    if "bm25" not in args.modes:
        parser.error("--modes must include bm25 because it is the report baseline")

    backend_root = Path(__file__).resolve().parents[1]
    root = backend_root.parent
    data_dir = backend_root / "eval_data"
    documents = read_jsonl(data_dir / "documents.jsonl")
    questions = read_jsonl(data_dir / args.questions_file)
    output_dir = backend_root / "reports" if args.output_dir is None else Path(args.output_dir)
    if args.output_dir is not None and not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report_stem = "retrieval-ablation-hard" if args.questions_file == "qa_hard.jsonl" else "retrieval-ablation"
    checkpoint_path = output_dir / f"{report_stem}.checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"answers": {}}
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "git_revision": git_revision(root),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "api": args.api,
        },
        "dataset": {
            "name": args.dataset,
            "questions_file": args.questions_file,
            "documents": len(documents),
            "questions": len(questions),
        },
        "knowledge_base_id": args.knowledge_base_id,
        "k": args.k,
        "retrieve_k": args.retrieve_k,
        "modes": args.modes,
        "results": {},
        "reproduce_command": (
            "python backend/scripts/run_ablation.py "
            f"--api {args.api} --knowledge-base-id {args.knowledge_base_id} "
            f"--dataset {args.dataset} --questions-file {args.questions_file} "
            f"--k {args.k} --retrieve-k {args.retrieve_k}"
        ),
    }
    with httpx.Client(base_url=args.api, timeout=args.timeout) as client:
        client.get("/health").raise_for_status()
        dashboard = client.get("/api/v1/dashboard").raise_for_status().json()
        complete = [item for item in dashboard["knowledge_bases"] if item["documents"] == len(documents) and item["build_state"] == "succeeded"]
        knowledge_base = complete[0] if args.knowledge_base_id == "auto" and complete else next(
            (item for item in complete if item["id"] == args.knowledge_base_id), None
        )
        if not knowledge_base:
            raise SystemExit("no succeeded benchmark knowledge base with exactly 100 documents was found")
        args.knowledge_base_id = knowledge_base["id"]
        report["knowledge_base_id"] = args.knowledge_base_id
        checkpoint_config = {
            "knowledge_base_id": args.knowledge_base_id,
            "questions_file": args.questions_file,
            "k": args.k,
            "retrieve_k": args.retrieve_k,
        }
        if checkpoint.get("config") != checkpoint_config:
            checkpoint = {"config": checkpoint_config, "answers": {}}
            checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
        report["reproduce_command"] = (
            "python backend/scripts/run_ablation.py "
            f"--api {args.api} --knowledge-base-id {args.knowledge_base_id} "
            f"--dataset {args.dataset} --questions-file {args.questions_file} "
            f"--k {args.k} --retrieve-k {args.retrieve_k}"
        )
        print(f"Using knowledge base {knowledge_base['name']} ({args.knowledge_base_id})", flush=True)
        for mode in args.modes:
            started = time.perf_counter()
            saved = checkpoint["answers"].setdefault(mode, {})
            totals = {key: 0.0 for key in METRICS}
            failures = []
            for index, item in enumerate(questions, 1):
                qa_id = item["qa_id"]
                if qa_id not in saved:
                    try:
                        result = request_with_retry(client, {
                            "query": item["question"],
                            "knowledge_base_id": args.knowledge_base_id,
                            "top_k": args.k,
                            "retrieve_k": args.retrieve_k,
                            "mode": mode,
                        })
                        retrieved = list(dict.fromkeys(row["source_uri"] for row in result["results"]))
                        saved[qa_id] = score(retrieved, {item["source_uri"]}, args.k)
                    except httpx.HTTPError as exc:
                        failures.append({"qa_id": qa_id, "error": type(exc).__name__})
                        print(f"[{mode}] {index}/{len(questions)} failed after retries: {qa_id}", flush=True)
                        continue
                    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
                for key in METRICS:
                    totals[key] += saved[qa_id][key]
                if index == 1 or index % 10 == 0 or index == len(questions):
                    print(f"[{mode}] {index}/{len(questions)} complete", flush=True)
            completed = len(saved)
            metrics = {key: round(value / max(completed, 1), 6) for key, value in totals.items()}
            report["results"][mode] = {
                "metrics": metrics,
                "evaluated_examples": completed,
                "failed_examples": failures,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            print(json.dumps({"mode": mode, **report["results"][mode]}, ensure_ascii=False), flush=True)

    missing = set(args.modes) - set(report["results"])
    if missing:
        raise SystemExit(f"A complete report requires all modes; missing: {sorted(missing)}")
    json_path = output_dir / f"{report_stem}.json"
    md_path = output_dir / f"{report_stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
