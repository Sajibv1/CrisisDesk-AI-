from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.models.report import Report
from app.schemas.report import ReportCreate, ReportFilters, StatusUpdateRequest
from app.services.report_service import ReportService


@dataclass
class FakeQueryResult:
    items: list[Report] | None = None
    total: int = 0
    scalar_value: int | None = None


class FakeCountQuery:
    def __init__(self, result: FakeQueryResult):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return []

    def scalar(self):
        return self.result.scalar_value


class FakeReportQuery:
    def __init__(self, result: FakeQueryResult):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def count(self):
        return self.result.total

    def all(self):
        return self.result.items or []


class FakeDB:
    def __init__(self, report: Report | None = None, list_result: FakeQueryResult | None = None, stats_map: dict[str, int] | None = None):
        self.report = report
        self.list_result = list_result or FakeQueryResult()
        self.stats_map = stats_map or {}
        self.added: list[Report] = []
        self.deleted: list[Report] = []
        self.committed = 0
        self.refreshed: list[Report] = []

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed += 1

    def refresh(self, item):
        self.refreshed.append(item)

    def delete(self, item):
        self.deleted.append(item)

    def get(self, model, report_id):
        return self.report if self.report and self.report.id == report_id else None

    def query(self, *models):
        if len(models) == 1 and models[0] is Report:
            return FakeReportQuery(self.list_result)
        return FakeCountQuery(FakeQueryResult(scalar_value=self.stats_map.get("scalar", 0)))


def test_create_report_uses_dependency_outputs(monkeypatch):
    service = ReportService()
    db = FakeDB()

    async def fake_translate(text, language):
        return "translated text"

    async def fake_geocode(location):
        return {"lat": 23.1, "lon": 90.4}

    async def fake_weather(lat, lon):
        return {"risk": "normal"}

    async def fake_classify(text, translated_text=None, weather_context=None):
        from app.schemas.report import ClassifiedReport

        return ClassifiedReport(
            category="fire",
            urgency="critical",
            summary="A fire has been reported.",
            suggestedAction="Dispatch fire service and emergency responders immediately.",
            confidence=0.93,
        )

    monkeypatch.setattr("app.services.report_service.new_report_id", lambda: "report_unit_1")
    service.translation_service.translate_to_english = fake_translate
    service.geocoding_service.geocode = fake_geocode
    service.weather_service.get_context = fake_weather
    service.classification_service.classify = fake_classify
    service.duplicate_service.detect = lambda db, location, category, description: (False, None)

    payload = ReportCreate(
        name="Rahim",
        contact="017xxxxxxxx",
        location="Sylhet Bondor Bazar",
        description="There is a fire near a shop and people are trapped.",
        language="bn",
    )

    report = asyncio.run(service.create_report(db, payload))

    assert report.id == "report_unit_1"
    assert report.category == "fire"
    assert report.urgency == "critical"
    assert report.location_lat == 23.1
    assert report.location_lon == 90.4
    assert db.added[0] is report
    assert db.committed >= 1
    assert db.refreshed[0] is report


def test_get_update_delete_and_stats(monkeypatch):
    now = datetime.now(timezone.utc)
    report = Report(
        id="report_1",
        name="Rahim",
        contact="017xxxxxxxx",
        location="Sylhet",
        normalized_location="sylhet",
        location_lat=23.1,
        location_lon=90.4,
        description="Fire near shop",
        translated_description=None,
        language="en",
        category="fire",
        urgency="critical",
        summary="A fire has been reported.",
        suggested_action="Dispatch fire service and emergency responders immediately.",
        confidence=0.93,
        possible_duplicate=False,
        matched_report_id=None,
        status="pending",
        source_metadata=None,
        created_at=now,
        updated_at=now,
    )

    list_result = FakeQueryResult(items=[report], total=1)
    db = FakeDB(report=report, list_result=list_result, stats_map={"scalar": 7})
    service = ReportService()

    fetched = service.get_report(db, "report_1")
    assert fetched is report

    updated = service.update_status(db, "report_1", StatusUpdateRequest(status="assigned"))
    assert updated.status == "assigned"
    assert updated.updated_at >= now

    items, total = service.list_reports(db, ReportFilters(page=1, page_size=10))
    assert total == 1
    assert items[0] is report

    stats = service.stats(db)
    assert stats["totalReports"] == 7

    service.delete_report(db, "report_1")
    assert db.deleted[0] is report


def test_get_report_raises_not_found():
    service = ReportService()
    db = FakeDB(report=None)

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        service.get_report(db, "missing")
