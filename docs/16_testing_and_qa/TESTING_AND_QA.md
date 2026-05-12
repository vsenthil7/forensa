# Forensa - Testing and QA

**Doc:** 16 of 22 | **Source:** master doc + Verixa pattern carryover

## Coverage target: 100% line + branch on all production code

Non-negotiable. CI enforces.

## Test stack

| Layer | Tool | Coverage gate |
|---|---|---:|
| Python unit + integration + property-based | pytest + pytest-cov + hypothesis | 100% |
| TypeScript unit + component | vitest + @vitest/coverage-v8 | 100% |
| Browser e2e | Playwright | 100% of user paths |
| Load | Locust | 10K sustained, 100K peak |
| Contract | pytest with OpenAPI schemathesis | All endpoints |
| Security | bandit + pip-audit + npm-audit + CodeQL | Zero high/critical |

## Test taxonomy

### Unit tests
- Pure-function tests in packages/crypto, packages/schema, packages/policy
- No I/O, no DB, no network
- pytest fixtures isolated per test

### Integration tests
- FastAPI TestClient + ephemeral PostgreSQL (testcontainers-python)
- Full request-response cycle including signature verification
- Database state asserted

### Property-based tests (hypothesis)
- Chain integrity: any insertion/modification fails verification
- Merkle tree: random insertion orders produce correct root
- Signatures: round-trip sign-verify always succeeds for valid keys

### End-to-end tests (Playwright)
- Full user journey: investigator opens console -> queries -> exports pack -> verifies pack
- Live FastAPI dev server + Next.js dev server
- Real Gemini API (or recorded responses for CI determinism)

### Load tests (Locust)
- Scenarios: steady-state ingest, burst spike, investigator query, export generation
- Run on workflow_dispatch and weekly schedule
- Targets: 10K events/sec sustained, 100K peak; p99 capture < 5ms

### Contract tests
- Generated from OpenAPI spec via schemathesis
- Catch backward-incompatible API changes
- Run on every PR

## CI pipeline (.github/workflows/ci.yml)

3 parallel jobs:
1. **python-tests**: pytest --cov=packages,apps/api --cov-fail-under=100 --cov-report=xml
2. **typescript-tests**: pnpm vitest run --coverage --coverage.thresholds.lines=100
3. **playwright-e2e**: spin up API + console, run Playwright suite

Plus serial jobs:
4. **lint**: ruff + mypy + eslint + tsc strict
5. **security**: bandit, pip-audit, npm-audit, gitleaks (secrets)
6. **build**: docker build + push (on tag)
7. **deploy**: helm upgrade (on tag, prod environment)

## Test fixtures

- tests/fixtures/receipts/ - canonical Receipt examples per event type
- tests/fixtures/policies/ - example OPA bundles
- tests/fixtures/agents/ - test agent identities with deterministic keys
- tests/fixtures/evidence-packs/ - reference signed packs for verification tests

## Hypothesis strategies

Custom strategies:
- forensa_receipt() - generates valid Receipts with all required fields
- forensa_merkle_chain(min_len=2, max_len=10000) - generates valid chains
- forensa_policy_bundle() - generates valid OPA bundles

## Performance regression tests

- pytest-benchmark for hot-path functions
- Baseline stored in tests/baseline.json
- CI fails if regression > 10%

## Tamper detection test (canonical scenario)

```python
def test_tamper_detection():
    # 1. Create chain of 100 receipts
    chain = create_chain(receipt_count=100)
    # 2. Verify chain - should pass
    assert chain.verify().chain_valid
    # 3. Modify Receipt #50 content (in DB)
    db.execute("UPDATE receipts SET prompt_hash='deadbeef' WHERE leaf_index=50")
    # 4. Re-verify chain - should fail at #50
    result = chain.verify()
    assert not result.chain_valid
    assert result.failure_leaf == 50
    assert result.failure_reason == "previous_receipt_hash_mismatch"
```

## Coverage exemptions

Allowed exemptions (must be commented):
- `# pragma: no cover` for unreachable defensive branches
- Cloud SDK call sites (mocked in unit tests, exercised in integration only)

CI rejects PRs that add `pragma: no cover` without a comment explaining why.

## Test environments

| Env | Purpose | Data |
|---|---|---|
| local-dev | Developer machine | Synthetic |
| ci | GitHub Actions | Synthetic |
| staging | Pre-production | Synthetic + scrubbed real |
| pre-prod | Customer-facing acceptance | Customer-provided test data |
| prod | Live | Real customer data |

## Bug bounty + responsible disclosure

Year 2+: HackerOne bounty programme. Year 1: security@forensa.dev with 90-day disclosure.

