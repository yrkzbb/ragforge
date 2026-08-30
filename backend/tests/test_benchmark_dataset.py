import json
from pathlib import Path


DATA = Path(__file__).parents[1] / "eval_data"


def read_jsonl(name: str):
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines()]


def test_benchmark_is_complete_and_grounded():
    documents = read_jsonl("documents.jsonl")
    questions = read_jsonl("qa.jsonl")
    by_id = {item["document_id"]: item for item in documents}
    assert len(documents) == len(by_id) == 100
    assert len(questions) == len({item["qa_id"] for item in questions}) == 300
    assert all(item["document_id"] in by_id for item in questions)
    assert all(item["evidence"] in by_id[item["document_id"]]["text"] for item in questions)
    assert all(sum(item["document_id"] == doc_id for item in questions) == 3 for doc_id in by_id)


def test_hard_benchmark_is_grounded_without_title_copying():
    documents = read_jsonl("documents.jsonl")
    questions = read_jsonl("qa_hard.jsonl")
    by_id = {item["document_id"]: item for item in documents}
    assert len(questions) == len({item["qa_id"] for item in questions}) == 300
    assert all(item["difficulty"] == "lexical-hard" for item in questions)
    assert all(item["evidence"] in by_id[item["document_id"]]["text"] for item in questions)
    assert all(by_id[item["document_id"]]["title"] not in item["question"] for item in questions)
