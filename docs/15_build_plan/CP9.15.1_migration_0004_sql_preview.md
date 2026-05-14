# CP9.15.1 — Migration 0004 SQL preview (alembic --sql)

**Generated:** 2026-05-14 18:30 UTC
**Command:** `poetry run alembic upgrade 0003_event_output:0004_bundle_approval_workflow --sql`
**Purpose:** verify the migration's generated SQL is syntactically correct without a live Postgres connection.

End-to-end migration execution against a real Postgres is tracked as `NEW-P9.15.1.run-migration-on-pg` — neither Docker Desktop nor a local Postgres was reachable during this session.

## Generated SQL

```sql
BEGIN;

-- Running upgrade 0003_event_output -> 0004_bundle_approval_workflow

ALTER TABLE policy_bundles ADD COLUMN status VARCHAR(16) DEFAULT 'proposed' NOT NULL;

ALTER TABLE policy_bundles ADD CONSTRAINT ck_policy_bundles_status CHECK (status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded'));

CREATE UNIQUE INDEX uq_policy_bundles_one_active_per_tenant ON policy_bundles (tenant_id) WHERE status = 'active';

CREATE TABLE policy_bundle_approvals (
    id UUID NOT NULL,
    bundle_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    from_status VARCHAR(16) NOT NULL,
    to_status VARCHAR(16) NOT NULL,
    actor_id UUID,
    actor_role VARCHAR(16) NOT NULL,
    reason VARCHAR(512) NOT NULL,
    decided_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(bundle_id) REFERENCES policy_bundles (id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT,
    CONSTRAINT ck_policy_bundle_approvals_from_status CHECK (from_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')),
    CONSTRAINT ck_policy_bundle_approvals_to_status CHECK (to_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')),
    CONSTRAINT ck_policy_bundle_approvals_actor_role CHECK (actor_role IN ('author', 'reviewer', 'approver', 'activator', 'system'))
);

CREATE INDEX ix_policy_bundle_approvals_bundle_decided ON policy_bundle_approvals (bundle_id, decided_at);

CREATE INDEX ix_policy_bundle_approvals_tenant_decided ON policy_bundle_approvals (tenant_id, decided_at);

CREATE OR REPLACE FUNCTION forensa_block_approval_mutation()
        RETURNS TRIGGER LANGUAGE plpgsql AS $func$
        BEGIN
            RAISE EXCEPTION 'policy_bundle_approvals is append-only; % is forbidden', TG_OP;
        END;
        $func$;;

CREATE TRIGGER trg_policy_bundle_approvals_block_update
        BEFORE UPDATE ON policy_bundle_approvals
        FOR EACH ROW EXECUTE FUNCTION forensa_block_approval_mutation();;

CREATE TRIGGER trg_policy_bundle_approvals_block_delete
        BEFORE DELETE ON policy_bundle_approvals
        FOR EACH ROW EXECUTE FUNCTION forensa_block_approval_mutation();;

ALTER TABLE policy_bundles ALTER COLUMN status DROP DEFAULT;

UPDATE alembic_version SET version_num='0004_bundle_approval_workflow' WHERE alembic_version.version_num = '0003_event_output';

COMMIT;
```

## Verified

- `ALTER TABLE policy_bundles ADD COLUMN status` with default `'proposed'` for backfill
- `ALTER ... DROP DEFAULT` after to require explicit value going forward
- `CHECK` on the 5 allowed status values
- Partial `UNIQUE INDEX` on `(tenant_id) WHERE status = 'active'` — enforces one-active-per-tenant
- `policy_bundle_approvals` table with FKs, CHECKs, indexes
- PL/pgSQL trigger function `forensa_block_approval_mutation()` with `$func$` delimiters intact
- Two triggers (`BEFORE UPDATE`, `BEFORE DELETE`) wired to the function

## Outstanding (NEW-P9.15.1.run-migration-on-pg)

To complete this work, run on a real Postgres:

```bash
# Set FORENSA_DB_URL to a real instance
export FORENSA_DB_URL='postgresql+asyncpg://user:pw@host:5432/forensa'
poetry run alembic upgrade head
# Confirm the workflow tables exist
psql -c '\dt policy_bundle*'
# Confirm the triggers exist
psql -c "\df forensa_block_approval_mutation"
# Verify the append-only enforcement (this MUST fail)
psql -c "UPDATE policy_bundle_approvals SET reason='tampered' WHERE id IS NOT NULL;"
# Verify downgrade reverses cleanly
poetry run alembic downgrade 0003_event_output
poetry run alembic upgrade head
```
