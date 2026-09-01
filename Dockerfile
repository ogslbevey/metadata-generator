FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev


CMD ["sh", "-c", "uv run hypercorn app.main:app --bind 0.0.0.0:${PORT:-8000}"]