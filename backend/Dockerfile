FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY app ./app
COPY eval_data ./eval_data
COPY scripts ./scripts
COPY migrations ./migrations
RUN useradd --uid 10001 --create-home ragforge && mkdir -p /models && chown -R ragforge:ragforge /models
USER 10001
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
