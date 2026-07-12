from __future__ import annotations

import httpx

from app.core.config import get_settings


class GeocodingService:
    async def geocode(self, location: str) -> dict[str, object]:
        settings = get_settings()
        params = {"q": location, "format": "jsonv2", "limit": 1}
        headers = {"User-Agent": "Citizen-Report-Triage-API/1.0"}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                response = await client.get(settings.nominatim_url, params=params)
                response.raise_for_status()
                items = response.json()
                if items:
                    item = items[0]
                    return {
                        "matched": True,
                        "display_name": item.get("display_name"),
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                    }
        except Exception:
            pass
        return {"matched": False, "display_name": None, "lat": None, "lon": None}
