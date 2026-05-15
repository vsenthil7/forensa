# Forensa Demo Video Pipeline

Captioned, narration-free regulator-flow walkthrough recorded via Playwright.
Ported from the auditex sibling project's pipeline at
`0001_Hack0014_Vertex_Swarm_Tashi/auditex/demovideo/`.

## Folder layout

```
demovideo/
  README.md                                 # this file
  creation/                                 # Option 1 - record demo video
    run-creation.ps1                        # 5-step orchestrator
    README.md                               # creation-specific docs
  results/
    creation/
      latest.txt                            # pointer to most recent recording
  verification-a/                           # (future) structural assertion review
  verification-b/                           # (future) frame OCR review
```

## Source files the recording drives

```
apps/console/playwright.config.ts                                  # webServer + DEMO=1 toggles
apps/console/tests-e2e/demo/end-to-end-demo.spec.ts                # 4-step captioned spec
apps/console/tests-e2e/demo/caption-overlay.ts                     # BDD scene cards + title cards
```

## Usage

```powershell
pwsh ./demovideo/creation/run-creation.ps1
```

The script:
1. Brings up `forensa-pg` if it isn't already + runs alembic migrations
2. Seeds demo data (TRUNCATE + reseed for a clean recording every time)
3. Captures the printed `FORENSA_TENANT_ID` + `FORENSA_TOKEN` from the seed output and exports them along with `FORENSA_HMAC_SECRET` + `FORENSA_HMAC_TENANT_ID` so the FastAPI auth layer recognises the token
4. Runs `npx playwright test ... --headed` with `DEMO=1` so the spec uses captions + slowMo + records video
5. Copies the resulting `.webm` to `demo/end-to-end-{timestamp}.webm` + `demo/_backup/`

## Outputs

- Recorded videos -> `demo/end-to-end-{timestamp}.webm` (gitignored)
- Backup of every recording -> `demo/_backup/` (gitignored)
- Pointer to latest active recording -> `demovideo/results/creation/latest.txt`

## Prerequisites

- Docker Desktop running (for `forensa-pg`)
- Python 3.12+ with `poetry install` already done
- Node 18+ with `npm install` already done inside `apps/console/`
- `pwsh` or PowerShell 5.1+
