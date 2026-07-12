from __future__ import annotations

import re

import httpx

from app.core.config import get_settings
from app.schemas.report import ClassifiedReport


KEYWORDS: dict[str, set[str]] = {
    "fire": {"fire", "smoke", "burn", "burning", "flame", "trapped"},
    "medical": {"injured", "hospital", "ambulance", "bleeding", "heart", "unconscious"},
    "crime": {"theft", "robbery", "attack", "assault", "gun", "murder", "kidnap"},
    "accident": {"accident", "collision", "crash", "hit", "overturned"},
    "flood": {"flood", "water", "overflow", "submerged", "heavy rain", "rain"},
    "utility": {"power", "electricity", "outage", "gas", "water supply", "internet"},
    "public_service": {"garbage", "trash", "cleaning", "streetlight", "service"},
    "infrastructure": {"road", "bridge", "pothole", "broken", "collapse", "construction"},
}


class ClassificationService:
    async def classify(self, text: str, translated_text: str | None = None, weather_context: dict[str, object] | None = None) -> ClassifiedReport:
        normalized = (translated_text or text).lower()
        gemini_result = await self._try_gemini(normalized)
        if gemini_result is not None:
            return gemini_result
        return self._heuristic(normalized, weather_context)

    async def _try_gemini(self, text: str) -> ClassifiedReport | None:
        settings = get_settings()
        if not settings.gemini_api_key:
            return None

        prompt = (
            "Classify this citizen report. Return JSON with keys category, urgency, summary, suggestedAction, confidence. "
            f"Allowed categories: medical, fire, accident, crime, flood, utility, public_service, infrastructure, other. "
            f"Report: {text}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
                text_output = data["candidates"][0]["content"]["parts"][0]["text"]
                json_block = self._extract_json(text_output)
                if json_block:
                    return ClassifiedReport(**json_block)
        except Exception:
            return None
        return None

    def _heuristic(self, text: str, weather_context: dict[str, object] | None) -> ClassifiedReport:
        scores: dict[str, int] = {category: 0 for category in KEYWORDS}
        for category, keywords in KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[category] += 2 if " " in keyword else 1

        category = max(scores, key=scores.get)
        if scores[category] == 0:
            category = "other"

        urgency = "medium"
        if any(term in text for term in {"trapped", "injured", "smoke", "fire", "gun", "flood", "collapse"}):
            urgency = "high"
        if any(term in text for term in {"dead", "explosion", "burning", "hospital", "critical", "blocked"}):
            urgency = "critical"
        if weather_context and weather_context.get("risk") == "elevated" and category == "flood":
            urgency = "critical"

        summary = self._summarize(text, category)
        suggested_action = self._action_for(category)
        confidence = 0.56 if category == "other" else min(0.95, 0.65 + scores.get(category, 0) * 0.08)
        return ClassifiedReport(
            category=category,  # type: ignore[arg-type]
            urgency=urgency,  # type: ignore[arg-type]
            summary=summary,
            suggestedAction=suggested_action,
            confidence=round(confidence, 2),
        )

    def _summarize(self, text: str, category: str) -> str:
        match = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)
        base = match[0] if match else text.strip()
        base = base[:180]
        if category == "other":
            return f"A public report requires review: {base}"
        return f"A {category} incident has been reported: {base}"

    def _action_for(self, category: str) -> str:
        if category == "fire":
            return "Dispatch fire service and emergency responders immediately."
        if category == "medical":
            return "Send ambulance and medical responders without delay."
        if category == "crime":
            return "Alert police and secure the location."
        if category == "flood":
            return "Notify disaster response teams and inspect evacuation needs."
        if category == "accident":
            return "Send traffic control and emergency medical support."
        if category == "utility":
            return "Notify the utility operator and log a service restoration case."
        if category == "infrastructure":
            return "Send engineering inspection and field assessment."
        return "Assign to the appropriate municipal response team for review."

    def _extract_json(self, text: str) -> dict[str, object] | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        import json

        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
