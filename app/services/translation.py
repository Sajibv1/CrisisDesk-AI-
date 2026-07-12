from __future__ import annotations

import httpx

from app.core.config import get_settings


class TranslationService:
    async def translate_to_english(self, text: str, language: str) -> str:
        if language in {"en", "unknown"}:
            return text

        settings = get_settings()
        payload = {"q": text, "source": "bn", "target": "en", "format": "text"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(settings.libretranslate_url, json=payload)
                response.raise_for_status()
                data = response.json()
                translated = data.get("translatedText")
                if translated:
                    return str(translated)
        except Exception:
            pass
        return text
