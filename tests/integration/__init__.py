"""Integration tests against a real Postgres.

All tests in this folder MUST be marked with ``@pytest.mark.pg``.
They are auto-skipped when ``FORENSA_TEST_DB_URL`` is unset, so the default
``poetry run pytest`` invocation remains a pure-SQLite, no-network unit suite.

To run these tests locally with the CP9.16-PG-up container:

    docker run -d --name forensa-pg \\
        -e POSTGRES_PASSWORD=forensa -e POSTGRES_USER=forensa -e POSTGRES_DB=forensa \\
        -p 5433:5432 postgres:16
    $env:FORENSA_TEST_DB_URL = "postgresql+asyncpg://forensa:forensa@localhost:5433/forensa"
    poetry run pytest tests/integration -m pg
"""
