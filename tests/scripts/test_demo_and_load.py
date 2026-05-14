"""Tests for scripts.demo_tabletop and scripts.load_test (CP8.1 + CP8.2)."""

from __future__ import annotations

import pytest

from scripts.demo_tabletop import run_demo
from scripts.load_test import main as load_main
from scripts.load_test import run_load


@pytest.mark.asyncio
async def test_demo_runs_end_to_end_with_default_n_events(capsys):
    await run_demo()
    captured = capsys.readouterr()
    assert "Forensa tabletop demo" in captured.out
    assert "ALL CHECKS PASSED" in captured.out
    assert "pack.root_hash" in captured.out
    assert "prompt_hash" in captured.out
    assert "content_hash" in captured.out


@pytest.mark.asyncio
async def test_demo_with_smaller_n(capsys):
    await run_demo(n_events=2)
    captured = capsys.readouterr()
    # Two receipts means seq=0 and seq=1 must appear in output
    assert "seq=0" in captured.out
    assert "seq=1" in captured.out


@pytest.mark.asyncio
async def test_load_test_run_returns_integrity_for_small_n():
    elapsed, ok, size, root_hash = await run_load(20)
    assert ok is True
    assert size == 20
    assert len(root_hash) == 64
    assert elapsed >= 0.0


@pytest.mark.asyncio
async def test_load_main_prints_budget_honoured_for_small_n(capsys):
    await load_main(10)
    captured = capsys.readouterr()
    assert "events             = 10" in captured.out
    assert "chain + pack ok    = True" in captured.out
    assert "BR-09 budget honoured" in captured.out
