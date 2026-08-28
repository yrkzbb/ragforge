"""Load the bundled corpus into a running API and execute all 300 retrieval queries."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--knowledge-base-id", help="Reuse an already compiled benchmark knowledge base")
    args = parser.parse_args()
    data = Path(__file__).resolve().parents[1] / "eval_data"
    documents, questions = rows(data / "documents.jsonl"), rows(data / "qa.jsonl")
    with httpx.Client(base_url=args.api, timeout=60) as client:
        kb = {"id": args.knowledge_base_id} if args.knowledge_base_id else client.post("/api/v1/knowledge-bases", json={"name": f"ragforge-zh-v1-{int(time.time())}"}).raise_for_status().json()
        if not args.knowledge_base_id:
            for document in documents:
                payload = {key: document[key] for key in ("source_uri", "title", "text", "metadata")}
                client.post(f"/api/v1/knowledge-bases/{kb['id']}/documents", json=payload).raise_for_status()
            job = client.post(f"/api/v1/knowledge-bases/{kb['id']}/compile").raise_for_status().json()
            deadline = time.time() + args.timeout
            while time.time() < deadline:
                status = client.get(f"/api/v1/build-jobs/{job['job_id']}").raise_for_status().json()
                if status["state"] == "succeeded":
                    break
                if status["state"] == "failed":
                    raise RuntimeError(status["error"])
                time.sleep(2)
            else:
                raise TimeoutError("knowledge image compilation timed out")
        examples = [{"query": item["question"], "relevant_source_uris": [item["source_uri"]]} for item in questions]
        result = client.post("/api/v1/evaluations", json={
            "knowledge_base_id": kb["id"], "dataset_name": "ragforge-zh-v1",
            "examples": examples, "k": 10,
        }, timeout=args.timeout).raise_for_status().json()
        result["evaluated_examples"] = len(result.pop("details", []))
        print(json.dumps({"knowledge_base_id": kb["id"], **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
