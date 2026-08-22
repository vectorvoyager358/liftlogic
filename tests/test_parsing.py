"""Tests for field parsers."""

from datetime import date

from liftlogic.parsing import parse_date, parse_weight


def test_parse_date_iso():
    assert parse_date("2026-08-20") == date(2026, 8, 20)


def test_parse_date_us_format():
    assert parse_date("8/20/2026") == date(2026, 8, 20)


def test_parse_date_object():
    assert parse_date(date(2026, 8, 20)) == date(2026, 8, 20)


def test_parse_date_invalid():
    assert parse_date("not-a-date") is None
    assert parse_date("") is None


def test_parse_weight():
    assert parse_weight("185") == 185.0
    assert parse_weight("1,000") == 1000.0
    assert parse_weight(200) == 200.0


def test_parse_weight_invalid():
    assert parse_weight("abc") is None
    assert parse_weight("") is None
