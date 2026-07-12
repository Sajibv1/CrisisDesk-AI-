from __future__ import annotations

import asyncio

import pytest

from app.schemas.report import ClassifiedReport
from app.services.classification import ClassificationService


def test_classify_uses_heuristics_for_fire_and_high_urgency():
    service = ClassificationService()

    result = asyncio.run(service.classify("There is smoke and trapped people near a shop."))

    assert isinstance(result, ClassifiedReport)
    assert result.category == "fire"
    assert result.urgency == "high"
    assert "fire incident" in result.summary
    assert "fire service" in result.suggestedAction.lower()


def test_classify_marks_flood_critical_with_weather_context():
    service = ClassificationService()

    result = asyncio.run(
        service.classify(
            "water is rising in the area",
            translated_text="water is rising in the area",
            weather_context={"risk": "elevated"},
        )
    )

    assert result.category == "flood"
    assert result.urgency == "critical"
