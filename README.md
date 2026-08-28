# RAGForge

生产级 Agent 知识引擎：文档增量构建、Parent-Child 检索、Hybrid Retrieval、反馈记忆、RAG 评测和 OpenTelemetry 全链路观测。

## 架构

- `app/`：React/Vinext 管理工作台
- `backend/app/main.py`：FastAPI API
- PostgreSQL + pgvector：业务数据、父子块和向量索引
- Redis + Celery：防抖批处理、可靠任务、失败重试
- OpenTelemetry Collector + Jaeger：Agent/检索/LLM 嵌套 Span
- OpenAI-compatible models：Query Rewrite、Embedding 和回答生成
- ONNX 中英 CrossEncoder：MIT 许可的 `BAAI/bge-reranker-base` 本地精排，无需 API Key

## 本地启动

```bash
cp .env.example .env
# 在 .env 中设置 OPENAI_API_KEY
docker compose up --build
npm install
npm run dev
```

- 工作台：http://localhost:3000
- API 文档：http://localhost:8000/docs
- Jaeger Trace Viewer：http://localhost:16686

创建知识库后，将返回的 ID 写入前端环境变量：

```env
NEXT_PUBLIC_RAGFORGE_API_URL=http://localhost:8000
NEXT_PUBLIC_RAGFORGE_KB_ID=<knowledge-base-uuid>
```

## 真实处理链路

1. `POST /api/v1/knowledge-bases/{id}/documents` 将变化写入不可变事件账本。
2. `POST /api/v1/knowledge-bases/{id}/compile` 创建镜像版本并延迟触发批处理。
3. Celery Worker 使用条件 `UPDATE ... RETURNING` 获取 CAS 租约；相同版本只能由一个 Worker 处理。
4. Worker 聚合同一 URI 的最新变化、按内容哈希跳过未变化文档、生成 Parent/Child 块与标题 Breadcrumb。
5. Child 块生成向量；查询时执行 BM25、pgvector cosine search、RRF 和真实 CrossEncoder 精排。
6. 命中 Child 后返回 Parent 正文，保持精确召回和上下文完整。
7. Agent 回答包含来源、Token usage 与 traceId；所有阶段均生成嵌套 Span。

## 反馈记忆

反馈默认进入 `pending`，只有人工 `accepted` 后才生成向量并参与后续会话注入；注入时按用户、知识库作用域和语义相似度过滤。记录包含纠正、原因、作用域、置信度与审核时间。

## 评测

仓库包含确定性生成的 `backend/eval_data/documents.jsonl`（100 篇）和 `qa.jsonl`（300 组），每题都带来源与原文证据。`POST /api/v1/evaluations` 接受 chunk ID 或 source URI 标注并真实计算 Recall@K、Precision@K、MRR、NDCG@K。

```bash
python backend/scripts/run_benchmark.py --api http://localhost:8000
```

`GET /api/v1/traces` 查询 Jaeger，`GET /metrics` 暴露 Prometheus 指标；Agent 会话包含 Tool Call、检索阶段和 LLM 嵌套 Span，并记录 token、可配置价格估算、时延和异常。

## 测试与构建

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
npm run build
docker compose config
```

## 生产注意事项

- 将数据库和 Redis 密码改为 Secret，并启用 TLS、备份和网络隔离。
- API 部署为至少两个实例；Worker 独立扩缩容。
- 为外部模型配置限流、超时、预算与熔断。
- 在线工作台只部署前端；FastAPI/PostgreSQL/Redis/Collector 需部署在容器平台，再通过私有网络或 HTTPS API 连接。
