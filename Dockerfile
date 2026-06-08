FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fra\
        libgl1 \
        libglib2.0-0 \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev

ENV CELERY_APP=app.celery_app \
    CELERY_QUEUES=ocr \
    CELERY_CONCURRENCY=32 \
    CELERY_LOGLEVEL=info \
    CELERY_MAX_TASKS_PER_CHILD=50 \
    CELERY_MAX_MEMORY_PER_CHILD=500000

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["sh", "-c", "uv run celery -A ${CELERY_APP} worker \
    -Q ${CELERY_QUEUES} \
    --pool=prefork \
    --concurrency=${CELERY_CONCURRENCY} \
    --loglevel=${CELERY_LOGLEVEL} \
    --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD} \
    --max-memory-per-child=${CELERY_MAX_MEMORY_PER_CHILD} \
    -n worker@%h"]