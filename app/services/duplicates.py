from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.report import Report
from app.utils.similarity import text_similarity, token_overlap


class DuplicateService:
    def detect(self, db: Session, *, location: str, category: str, description: str) -> tuple[bool, str | None]:
        candidates = db.query(Report).filter(Report.category == category).order_by(Report.created_at.desc()).limit(50).all()
        best_score = 0.0
        best_id: str | None = None
        for report in candidates:
            location_score = text_similarity(location, report.location)
            description_score = max(text_similarity(description, report.description), token_overlap(description, report.description))
            combined = (location_score * 0.4) + (description_score * 0.6)
            if combined > best_score:
                best_score = combined
                best_id = report.id
        if best_score >= 0.78:
            return True, best_id
        return False, None
