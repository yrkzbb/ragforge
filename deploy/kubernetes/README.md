# Kubernetes deployment

These manifests deploy the stateless API and Celery workers. PostgreSQL with
pgvector, Redis, an OpenTelemetry Collector and Jaeger should be provided as
managed or separately operated services.

## Prerequisites

- A Kubernetes cluster with Metrics Server and an Ingress controller.
- A PostgreSQL 15+ database with the `vector` extension.
- Redis with TLS in production.
- A storage class supporting `ReadWriteMany` for the shared model cache. If the
  cluster only supports `ReadWriteOnce`, replace the PVC with one cache per pod
  or use an object-backed RWX storage driver.
- A container image built from `backend/Dockerfile` and pushed to a registry.

## Deploy

1. Replace `REPLACE_OWNER` and `REPLACE_TAG` in `api.yaml`, `worker.yaml`, and
   `migrate.yaml` with an immutable image tag.
2. Copy `secret.example.yaml` to a file outside version control. Fill in a
   rotated model API key and production database/Redis URLs.
3. Adjust `config.yaml` and `ingress.example.yaml` for the production domains.
4. Apply the namespace, configuration and secret, then run migrations before
   rolling out application workloads:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f config.yaml
kubectl apply -f /secure/path/ragforge-secret.yaml
kubectl apply -f migrate.yaml
kubectl wait --for=condition=complete job/ragforge-migrate -n ragforge --timeout=180s
kubectl apply -f api.yaml -f worker.yaml -f scaling.yaml
kubectl apply -f ingress.example.yaml
```

For a new migration image, delete the completed `ragforge-migrate` Job before
applying it again, or give the Job a release-specific name. Database migrations
are transactional and recorded in `schema_migrations`.

## Operations

- Terminate TLS at the Ingress and restrict database/Redis access to cluster
  workloads through firewall or NetworkPolicy rules.
- Export `/metrics` to Prometheus and forward OTLP to the configured collector.
- Back up PostgreSQL and test restores. Redis is a queue/cache, not the source
  of truth.
- Keep at least two API replicas. Scale workers by queue depth when a KEDA or
  Prometheus adapter is available; the checked-in HPA covers API CPU load.
- Never commit the real Secret manifest or an API key.
