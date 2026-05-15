# creation/ - Option 1: Record demo video

Coordinates the Playwright spec at
`apps/console/tests-e2e/demo/end-to-end-demo.spec.ts` to record a
captioned, narration-free walkthrough of the Forensa regulator
verification flow.

Ported from `auditex/demovideo/creation/` (sibling hackathon project).

## What it does (5 steps)

1. Pre-flight: `forensa-pg` container up + alembic at head
2. Seed demo data (idempotent - re-running re-mints the bearer token)
3. Capture seed-output env vars + wire FastAPI auth env vars
4. Run the playwright spec with `DEMO=1` (slow-motion + captions + video on)
5. Archive the video to `demo/end-to-end-{timestamp}.webm` and `demo/_backup/`

## Run

```powershell
pwsh ./demovideo/creation/run-creation.ps1
```

## Modular touch-points

- **Spec source:** `apps/console/tests-e2e/demo/end-to-end-demo.spec.ts`
- **Caption helper:** `apps/console/tests-e2e/demo/caption-overlay.ts` (BDD scene cards)
- **Video archive:** `demo/` (active) + `demo/_backup/` (history)
- **Pointer file:** `demovideo/results/creation/latest.txt`

## What you'll see in the recording

Four scenarios, each with a full-screen BDD caption card (Given /
When / Then / Test Data / Expected Outcome) followed by a "Regulator
Console" surface that renders the actual API response:

1. **STEP 1 of 4** - GET evidence-pack (JSON-LD): tenant_id, root_hash, anchor_id, receipt_count
2. **STEP 2 of 4** - GET evidence-pack (PDF wire form): PDF magic bytes + size
3. **STEP 3 of 4** - GET anchor (raw RFC 3161 TSR): DER bytes + filename + X-Forensa-Anchor-Root-Hash header
4. **STEP 4 of 4** - Chain integrity: re-fetch the pack; root_hash is byte-for-byte identical

Bookended by Forensa title cards on `about:blank` (no app flash).
