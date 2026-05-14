# syntax=docker/dockerfile:1.7
#
# CP9.10 / NEW-P9.8.29: COPY ordering rewritten for proper Docker-layer
# caching. Previously every code change invalidated the `poetry install`
# layer because pyproject.toml + poetry.lock were copied alongside source.
# Now deps install in its own layer that only invalidates when pyproject /
# lock change.
#
# CP9.10 / NEW-P9.8.29 also adds --chown=forensa:forensa on the runtime COPY
# so /app is owned by the non-root user instead of root.
#
# NEW-P9.8.30: a sibling .dockerignore excludes _backup, .git, .venv,
# __pycache__, node_modules etc. to keep the build context small.
#
# Still TRACKED / not closed in CP9.10:
# - pip-audit step in builder (NEW-P9.8.28, Phase 13)
# - SBOM generation (top-20 #19, Phase 13)
# - image signing via cosign (top-20 #19, Phase 13)
# - healthcheck uvicorn-direct vs TLS sidecar (NEW-P9.8.31, Phase 12)

# ------------------------------------------------------------------ builder
FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==${POETRY_VERSION}

WORKDIR /build

# Layer 1: dependency manifests only. Changes ONLY when deps change.
COPY pyproject.toml poetry.lock ./

# Layer 2: install deps. Cached unless layer 1 invalidates.
RUN poetry install --only main --no-interaction --no-ansi --no-root

# Layer 3: copy source. Cached unless source changes - and crucially does
# NOT invalidate layer 2 when only source changes.
COPY packages ./packages
COPY apps ./apps
COPY tools ./tools
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Layer 4: install the root package (forensa itself) now that source is present.
# --only main again to skip dev deps.
RUN poetry install --only main --no-interaction --no-ansi

# ------------------------------------------------------------------ runtime
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1001 forensa

WORKDIR /app

# --chown sets ownership at copy time so /app is forensa-owned, not root.
COPY --from=builder --chown=forensa:forensa /build /app

USER forensa
EXPOSE 8000

# CP9.10 leaves the urllib healthcheck targeting http://localhost as-is for
# now; NEW-P9.8.31 will move it to uvicorn-direct to skip TLS sidecars.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
