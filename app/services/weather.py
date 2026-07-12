from __future__ import annotations

import httpx

from app.core.config import get_settings


class WeatherService:
    async def get_context(self, lat: float | None, lon: float | None) -> dict[str, object]:
        if lat is None or lon is None:
            return {"available": False, "risk": "unknown", "context": None}
        settings = get_settings()
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "precipitation", "weather_code"],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(settings.open_meteo_url, params=params)
                response.raise_for_status()
                data = response.json().get("current", {})
                precipitation = float(data.get("precipitation", 0.0) or 0.0)
                risk = "elevated" if precipitation >= 10 else "normal"
                return {"available": True, "risk": risk, "context": data}
        except Exception:
            return {"available": False, "risk": "unknown", "context": None}
