from __future__ import annotations

from dataclasses import dataclass

from app.models.report import Report
from app.services.duplicates import DuplicateService


@dataclass
class FakeReport:
    id: str
    location: str
    description: str


class FakeQuery:
    def __init__(self, reports: list[FakeReport]):
        self._reports = reports

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return self._reports


class FakeDB:
    def __init__(self, reports: list[FakeReport]):
        self._reports = reports

    def query(self, model):
        assert model is Report
        return FakeQuery(self._reports)


def test_detects_similar_duplicate(monkeypatch):
    service = DuplicateService()
    db = FakeDB([FakeReport(id="report_1", location="Sylhet Bondor Bazar", description="Fire near shop")])

    monkeypatch.setattr("app.services.duplicates.text_similarity", lambda left, right: 0.9)
    monkeypatch.setattr("app.services.duplicates.token_overlap", lambda left, right: 0.9)

    possible_duplicate, matched_id = service.detect(
        db,
        location="Sylhet Bondor Bazar",
        category="fire",
        description="There is a fire near a shop and people are trapped.",
    )

    assert possible_duplicate is True
    assert matched_id == "report_1"


def test_non_duplicate_when_similarity_is_low(monkeypatch):
    service = DuplicateService()
    db = FakeDB([FakeReport(id="report_1", location="Dhaka", description="Power outage")])

    monkeypatch.setattr("app.services.duplicates.text_similarity", lambda left, right: 0.1)
    monkeypatch.setattr("app.services.duplicates.token_overlap", lambda left, right: 0.1)

    possible_duplicate, matched_id = service.detect(
        db,
        location="Sylhet",
        category="fire",
        description="There is a fire near a shop and people are trapped.",
    )

    assert possible_duplicate is False
    assert matched_id is None
