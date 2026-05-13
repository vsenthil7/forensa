# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 POETRY_VERSION=1.8.4 POETRY_VIRTUALENVS_IN_PROJECT=true
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==${POETRY_VERSION}
WORKDIR /build
COPY pyproject.toml poetry.lock ./
COPY packages ./packages
COPY apps ./apps
COPY tools ./tools
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN poetry install --only main --no-interaction --no-ansi

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/* && useradd -m -u 1001 forensa
WORKDIR /app
COPY --from=builder /build /app
USER forensa
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=3).status == 200 else 1)"
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
