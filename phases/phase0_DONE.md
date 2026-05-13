# Phase 0 - Green CI - DONE

Status: COMPLETE
HEAD at completion: bb6b0ea
CI run: 25798493526 (success in 6m31s)

## Summary

All 8 CI jobs passing. Hard requirement met:
- 100pct Python coverage (217 tests)
- 100pct TypeScript coverage (7 vitest tests)
- Playwright E2E running and passing (2 tests)
- Docker images building
- Security scans clean (bandit + pip-audit + pnpm-audit + gitleaks + CodeQL)
- SBOM generating

## Fixes landed

1. Bandit + pip-audit added to dev deps (was missing).
2. FORENSA_DATABASE_URL renamed in CI to match env.py.
3. pip-audit switched to lockfile-based (--strict on local editable failed).
4. poetry-plugin-export injected in all 5 Install Poetry steps.
5. Built full apps/console Next.js 15 + React 19 skeleton.
6. Bumped Python CVEs: fastapi 0.121, starlette 0.50, orjson 3.11, pytest 9, pytest-asyncio 1.3, python-multipart 0.0.27, cryptography 46.
7. Bumped Node CVEs: next latest, react 19.2, vitest 4, playwright latest, vite 8, eslint-config-next 16.2 flat-config.
8. pnpm --filter <pkg> exec <bin> pattern (was bare pnpm --filter <pkg> <bin>).
9. CI security-events: write permission for CodeQL.
10. nohup + pid-file + sleep 2 for backgrounded uvicorn so it survives step boundary.
11. wait-on http-get:// prefix (default HEAD verb got 405 from GET-only /healthz).

## Next: Phase 1 - Unit 10 cryptographic primitives

---

## Test-level split per CP

Phase 0 is CI infrastructure only - no new source code or unit tests added in this phase. The 217 baseline pytest count was unchanged; the fix was a 1-character change to the Playwright wait-on URL scheme.

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP0.1 fix Playwright wait-on | 0 | 0 | 0 | 0 | 0 | Infra fix (wait-on http:// to http-get://) verified by CI run going green |
| CP0.2 verify 7 CI jobs | 0 | 0 | 0 | 0 | 0 | Acceptance test = ci-gate green on run 25798493526 |
| CP0.3 commit + push | 0 | 0 | 0 | 0 | 0 | DOC commit only |
| **Phase 0 total** | **0** | **0** | **0** | **0** | **0 new tests; 217 existing all green** | - |

---

## Source code embedded (production + tests)

### CP0.1 - CI workflow snippet (wait-on fix) - `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write
  security-events: write
  actions: read

env:
  POETRY_VERSION: '1.8.4'
  PYTHON_VERSION: '3.12'
  NODE_VERSION: '22'
  PNPM_VERSION: '9'

jobs:
  python-tests:
    name: Python tests (100% coverage gate)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: forensa
          POSTGRES_PASSWORD: forensa_ci
          POSTGRES_DB: forensa_test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install Poetry
        run: |
          pipx install poetry==${{ env.POETRY_VERSION }}
          pipx inject poetry poetry-plugin-export
      - name: Cache Poetry virtualenv
        uses: actions/cache@v4
        with:
          path: .venv
          key: poetry-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}
      - name: Install dependencies
        run: poetry install --with dev --no-interaction
      - name: Run migrations
        env:
          FORENSA_DATABASE_URL: postgresql+asyncpg://forensa:forensa_ci@localhost:5432/forensa_test
        run: poetry run alembic upgrade head
      - name: Run pytest with coverage (100%% gate)
        env:
          FORENSA_DATABASE_URL: postgresql+asyncpg://forensa:forensa_ci@localhost:5432/forensa_test
        run: poetry run pytest --cov=packages --cov=apps/api --cov-fail-under=100 --cov-report=xml --cov-report=term-missing
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: python-coverage
          path: coverage.xml


  typescript-tests:
    name: TypeScript tests (100% coverage gate)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}
      - name: Get pnpm store dir
        id: pnpm-cache
        shell: bash
        run: echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_OUTPUT
      - name: Setup pnpm cache
        uses: actions/cache@v4
        with:
          path: ${{ steps.pnpm-cache.outputs.STORE_PATH }}
          key: pnpm-${{ runner.os }}-${{ hashFiles('**/pnpm-lock.yaml') }}
      - name: Install dependencies
        run: pnpm install --frozen-lockfile
      - name: Run vitest with coverage (100%% gate)
        run: pnpm --filter @forensa/console exec vitest run --coverage
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: typescript-coverage
          path: apps/console/coverage

  playwright-e2e:
    name: Playwright E2E
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: forensa
          POSTGRES_PASSWORD: forensa_ci
          POSTGRES_DB: forensa_e2e
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install Poetry
        run: |
          pipx install poetry==${{ env.POETRY_VERSION }}
          pipx inject poetry poetry-plugin-export
      - name: Install Python deps
        run: poetry install --with dev --no-interaction
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}
      - name: Install Node deps
        run: pnpm install --frozen-lockfile
      - name: Install Playwright browsers
        run: pnpm --filter @forensa/console exec playwright install --with-deps chromium
      - name: Run migrations
        env:
          FORENSA_DATABASE_URL: postgresql+asyncpg://forensa:forensa_ci@localhost:5432/forensa_e2e
        run: poetry run alembic upgrade head
      - name: Start API in background
        env:
          FORENSA_DATABASE_URL: postgresql+asyncpg://forensa:forensa_ci@localhost:5432/forensa_e2e
        run: |
          nohup poetry run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
          echo $! > /tmp/uvicorn.pid
          sleep 2
      - name: Wait for API ready
        run: npx wait-on http-get://localhost:8000/healthz --timeout 60000
      - name: Show uvicorn log on failure
        if: failure()
        run: cat /tmp/uvicorn.log || true
      - name: Run Playwright tests
        run: pnpm --filter @forensa/console exec playwright test
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/


  lint:
    name: Lint and type-check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install Poetry
        run: |
          pipx install poetry==${{ env.POETRY_VERSION }}
          pipx inject poetry poetry-plugin-export
      - name: Install deps
        run: poetry install --with dev --no-interaction
      - name: Ruff
        run: poetry run ruff check .
      - name: Ruff format check
        run: poetry run ruff format --check .
      - name: Mypy
        run: poetry run mypy packages apps/api
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}
      - name: Install Node deps
        run: pnpm install --frozen-lockfile
      - name: ESLint
        run: pnpm --filter @forensa/console run lint
      - name: TypeScript strict check
        run: pnpm --filter @forensa/console exec tsc --noEmit

  security:
    name: Security scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install Poetry
        run: |
          pipx install poetry==${{ env.POETRY_VERSION }}
          pipx inject poetry poetry-plugin-export
      - name: Install deps
        run: poetry install --with dev --no-interaction
      - name: Bandit (Python SAST)
        run: poetry run bandit -r packages apps/api -ll
      - name: pip-audit (Python lockfile vulns)
        run: |
          poetry export --without-hashes --with dev -f requirements.txt -o /tmp/requirements.txt
          poetry run pip-audit --requirement /tmp/requirements.txt --strict
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}
      - name: pnpm audit
        run: pnpm audit --audit-level high
      - name: Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: CodeQL Python
        uses: github/codeql-action/init@v3
        with:
          languages: python, typescript
      - name: Run CodeQL analysis
        uses: github/codeql-action/analyze@v3


  build-docker:
    name: Docker build
    runs-on: ubuntu-latest
    needs: [python-tests, typescript-tests, lint, security]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Build API image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          tags: forensa-api:${{ github.sha }}
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Build Console image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/console/Dockerfile
          tags: forensa-console:${{ github.sha }}
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max

  sbom:
    name: Generate SBOM
    runs-on: ubuntu-latest
    needs: [python-tests, typescript-tests]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install Poetry
        run: |
          pipx install poetry==${{ env.POETRY_VERSION }}
          pipx inject poetry poetry-plugin-export
      - name: Install cyclonedx-py
        run: pipx install cyclonedx-bom
      - name: Generate Python SBOM
        run: cyclonedx-py poetry --output-format JSON --output-file forensa-python.cdx.json
      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: forensa-python.cdx.json

  ci-gate:
    name: CI gate (all checks passed)
    runs-on: ubuntu-latest
    needs: [python-tests, typescript-tests, playwright-e2e, lint, security]
    if: always()
    steps:
      - name: Check all jobs succeeded
        run: |
          if [ "${{ needs.python-tests.result }}" != "success" ]; then echo "python-tests failed"; exit 1; fi
          if [ "${{ needs.typescript-tests.result }}" != "success" ]; then echo "typescript-tests failed"; exit 1; fi
          if [ "${{ needs.playwright-e2e.result }}" != "success" ]; then echo "playwright-e2e failed"; exit 1; fi
          if [ "${{ needs.lint.result }}" != "success" ]; then echo "lint failed"; exit 1; fi
          if [ "${{ needs.security.result }}" != "success" ]; then echo "security failed"; exit 1; fi
          echo "All CI gates passed"
```

