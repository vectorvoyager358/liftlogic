"""Tests for exercise dropdown sync helpers."""

from liftlogic.constants import MUSCLE_TABS
from liftlogic.setup import _exercise_names_by_muscle_from_sheet


class _FakeClient:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[str]]:
        return self._rows


def test_exercise_names_from_sheet_group_by_muscle():
    client = _FakeClient(
        [
            ["CH001", "Barbell Bench Press", "Chest"],
            ["CH004", "Push-Up", "Chest"],
            ["CD004", "Steps", "Cardio"],
        ]
    )
    grouped = _exercise_names_by_muscle_from_sheet(client, "sheet123")
    assert grouped["Chest"] == ["Barbell Bench Press", "Push-Up"]
    assert grouped["Cardio"] == ["Steps"]
    assert "Lat Pulldown" in grouped["Back"]  # seed fallback when sheet has none for Back


def test_exercise_names_fallback_when_sheet_empty():
    client = _FakeClient([])
    grouped = _exercise_names_by_muscle_from_sheet(client, "sheet123")
    for muscle in MUSCLE_TABS:
        assert grouped[muscle], f"{muscle} should fall back to seed catalog"
