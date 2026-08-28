"""Generate the deterministic Chinese RAGForge benchmark (100 docs / 300 QA)."""
from __future__ import annotations

import json
from pathlib import Path


DOMAINS = [
    ("人力资源", "员工制度"), ("信息安全", "安全规范"), ("财务管理", "财务制度"),
    ("客户服务", "服务手册"), ("研发工程", "工程规范"), ("采购管理", "采购制度"),
    ("市场运营", "运营手册"), ("法务合规", "合规指引"), ("行政管理", "行政制度"),
    ("业务连续性", "应急预案"),
]


def build_document(domain: str, series: str, index: int) -> tuple[str, str, list[dict]]:
    title = f"{domain}{series}第{index:02d}号"
    days = 2 + index % 8
    owner = f"{domain}第{index % 4 + 1}小组"
    channel = f"{domain}服务台-{index:02d}"
    facts = [
        (f"{title}规定，标准申请应至少提前{days}个工作日提交。", f"{title}的标准申请应提前多久提交？", f"至少提前{days}个工作日。"),
        (f"该制度的责任部门为{owner}，负责受理、复核和结果归档。", f"{title}由哪个部门负责？", f"由{owner}负责。"),
        (f"遇到异常时，应通过“{channel}”上报，并在24小时内补齐记录。", f"执行{title}时遇到异常，应通过什么渠道上报？", f"通过“{channel}”上报。"),
    ]
    text = (
        f"# {title}\n\n## 一、适用范围\n本文件适用于公司内部所有涉及{domain}的员工与合作方。"
        f"\n\n## 二、申请时限\n{facts[0][0]}逾期申请须由直属负责人说明原因。"
        f"\n\n## 三、职责分工\n{facts[1][0]}未经复核的结果不得进入正式流程。"
        f"\n\n## 四、异常处理\n{facts[2][0]}重大异常须同步值班负责人。"
        "\n\n## 五、审计要求\n所有申请、审批与异常记录保存三年，每季度抽样复核。"
    )
    qa = [{"question": q, "answer": a, "evidence": evidence} for evidence, q, a in facts]
    return title, text, qa


def generate(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    documents, questions = [], []
    for domain_index, (domain, series) in enumerate(DOMAINS, start=1):
        for index in range(1, 11):
            title, text, qa = build_document(domain, series, index)
            source_uri = f"benchmark://zh/{domain_index:02d}/{index:02d}"
            document_id = f"doc-{domain_index:02d}-{index:02d}"
            documents.append({
                "document_id": document_id, "source_uri": source_uri, "title": title,
                "text": text, "metadata": {"domain": domain, "benchmark": "ragforge-zh-v1"},
            })
            for question_index, item in enumerate(qa, start=1):
                questions.append({
                    "qa_id": f"qa-{domain_index:02d}-{index:02d}-{question_index}",
                    "document_id": document_id, "source_uri": source_uri, **item,
                })
    document_path, qa_path = output_dir / "documents.jsonl", output_dir / "qa.jsonl"
    for path, rows in ((document_path, documents), (qa_path, questions)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return document_path, qa_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    docs, qa = generate(root / "eval_data")
    print(f"generated {docs} and {qa}")
