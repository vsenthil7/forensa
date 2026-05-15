"""Forensa job-runner modules.

Pure execution layers that take a persisted job_id and drive it through
its state machine. Workers are independent of HTTP routes -- the route
schedules a worker via asyncio.create_task / Celery / EventBridge and
returns 202 immediately; the worker owns its own session lifecycle
because the route's session is closed by the time the worker runs.

Today: packages.jobs.ma_export_runner (CP9.44 / IP #8 runner half).
"""

from __future__ import annotations
