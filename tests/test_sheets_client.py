"""Tests for Sheets client retry / batch helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from liftlogic.sheets.client import _BATCH_UPDATE_SIZE, execute_with_retries


def test_execute_with_retries_succeeds_first_try():
    assert execute_with_retries(lambda: 42) == 42


def test_execute_with_retries_recovers_from_timeout(monkeypatch):
    monkeypatch.setattr("liftlogic.sheets.client.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("read timed out")
        return "ok"

    assert execute_with_retries(flaky) == "ok"
    assert calls["n"] == 3


def test_execute_with_retries_gives_up(monkeypatch):
    monkeypatch.setattr("liftlogic.sheets.client.time.sleep", lambda _s: None)

    def always_timeout():
        raise TimeoutError("still down")

    with pytest.raises(TimeoutError, match="still down"):
        execute_with_retries(always_timeout, max_retries=3)


def test_execute_with_retries_retries_http_503(monkeypatch):
    monkeypatch.setattr("liftlogic.sheets.client.time.sleep", lambda _s: None)
    calls = {"n": 0}
    resp = SimpleNamespace(status=503, reason="Service Unavailable")

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise HttpError(resp, b"unavailable")
        return "ok"

    assert execute_with_retries(flaky) == "ok"
    assert calls["n"] == 2


def test_batch_chunk_size_is_bounded():
    assert 20 <= _BATCH_UPDATE_SIZE <= 200
