# Phase 0 - Green CI - Progress

HEAD at phase start: 06f369b

## Pre-phase CI state (from run 25797703029)

Failing: Playwright E2E (Wait for API ready timeout - uvicorn doesnt bind in CI).
Passing: python-tests, typescript-tests, lint, security, sbom, docker-build.


## CP0.1 - Diagnose & fix Playwright Wait for API ready timeout

Root cause: wait-on default verb is HEAD. FastAPI route /healthz only accepts GET. 
Every probe got 405 Method Not Allowed; wait-on never saw a 2xx until 60s timeout.

Fix: change wait-on URL prefix from http:// to http-get:// (forces GET verb).
Confirmed by uvicorn.log dump in CI run 25797703029: 30+ HEAD /healthz returning 405.

Status: FIXED (commit pending)
Commits: pending
Tests added: 0 (CI infra fix)


