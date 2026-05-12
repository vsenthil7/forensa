# Forensa - Software Bill of Materials (SBOM)

**Status:** v0.1.0 placeholder. Production SBOM generated per release in CycloneDX format and signed.

## Generation

SBOM is auto-generated on every release tag:
- Python deps: cyclonedx-py from pyproject.toml + poetry.lock
- TypeScript deps: cyclonedx-bom from package.json + pnpm-lock.yaml
- Container deps: syft on Docker images
- Merged into single CycloneDX 1.5 JSON
- Signed by tenant release key
- Published to docs/sbom/v{version}/forensa-sbom.cdx.json.sig

## Key dependencies (v0.1.0)

### Python (Poetry-managed)
| Package | Version | License | Use |
|---|---|---|---|
| fastapi | ^0.115 | MIT | Web framework |
| pydantic | ^2.9 | MIT | Schemas |
| sqlalchemy | ^2.0 | MIT | ORM |
| asyncpg | ^0.30 | Apache-2.0 | PostgreSQL async driver |
| alembic | ^1.13 | MIT | Migrations |
| cryptography | ^43 | Apache-2.0/BSD | Ed25519, SHA-256, RFC 3161 |
| opentelemetry-api | ^1.27 | Apache-2.0 | OTel ingest |
| opentelemetry-semantic-conventions-ai | latest | Apache-2.0 | GenAI semconv |
| google-generativeai | ^0.8 | Apache-2.0 | Gemini SDK |
| langgraph | ^0.2 | MIT | Multi-agent provenance |
| celery | ^5.4 | BSD | Async workers |
| redis | ^5.0 | MIT | Cache + Celery broker |
| pytest | ^8.3 | MIT | Test runner |
| pytest-cov | ^5.0 | MIT | Coverage |
| hypothesis | ^6.115 | MPL-2.0 | Property-based testing |
| ruff | ^0.7 | MIT | Linter |
| mypy | ^1.13 | MIT | Type checker |
| locust | ^2.32 | MIT | Load testing |
| schemathesis | ^3.36 | MIT | Contract testing |

### TypeScript (pnpm-managed)
| Package | Version | License | Use |
|---|---|---|---|
| next | ^15 | MIT | React framework |
| react | ^19 | MIT | UI |
| typescript | ^5.6 | Apache-2.0 | Type checker |
| tailwindcss | ^3.4 | MIT | Styling |
| @google/generative-ai | ^0.21 | Apache-2.0 | Gemini SDK |
| vitest | ^2.1 | MIT | Test runner |
| @playwright/test | ^1.48 | Apache-2.0 | E2E |

### Container base images
| Image | Tag | License |
|---|---|---|
| python | 3.12-slim-bookworm | PSF |
| node | 22-alpine | MIT |
| postgres | 16-bookworm | PostgreSQL |
| opensearchproject/opensearch | 2.18 | Apache-2.0 |
| redis | 7.4-alpine | BSD |

## License inventory

All direct dependencies use OSI-approved permissive licenses:
- MIT (majority)
- Apache-2.0
- BSD-3-Clause
- BSD-2-Clause
- MPL-2.0 (hypothesis)
- PSF (Python stdlib)
- PostgreSQL License (PostgreSQL)

No copyleft (GPL/AGPL/LGPL) in production dependencies. Acceptable for MIT-licensed Forensa core.

## Security scanning

Per-release CI scans:
- pip-audit on Python deps -> zero high/critical or build fails
- npm audit (level=high) on TypeScript deps
- Trivy on container images -> zero high/critical CVEs
- Snyk SCA (Year 2+)
- CodeQL SAST on all code

## SLSA provenance

Forensa CI emits SLSA Level 3 provenance per release:
- Build environment attested
- Source repo + commit SHA recorded
- Dependencies resolved deterministically (lock files)
- Signed with build-time ephemeral key
- Published alongside SBOM

## Vulnerability disclosure

Security issues: security@forensa.dev with 90-day responsible disclosure.
Year 2+: HackerOne bug bounty.

## Update cadence

- Critical CVE patches: within 24h
- High CVE patches: within 7 days
- Medium: monthly batch
- Low + dependency hygiene: quarterly
- Major framework upgrades (Next.js, FastAPI): annually with full regression

