from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.report import Report
from app.schemas.report import ReportCreate, ReportFilters, StatusUpdateRequest
from app.services.classification import ClassificationService
from app.services.duplicates import DuplicateService
from app.services.geocoding import GeocodingService
from app.services.translation import TranslationService
from app.services.weather import WeatherService
from app.utils.ids import new_report_id


class ReportService:
    def __init__(self) -> None:
        self.translation_service = TranslationService()
        self.geocoding_service = GeocodingService()
        self.weather_service = WeatherService()
        self.classification_service = ClassificationService()
        self.duplicate_service = DuplicateService()

    async def create_report(self, db: Session, payload: ReportCreate) -> Report:
        translated_description = await self.translation_service.translate_to_english(payload.description, payload.language)
        geocoded = await self.geocoding_service.geocode(payload.location)
        weather_context = await self.weather_service.get_context(geocoded.get("lat"), geocoded.get("lon"))
        classified = await self.classification_service.classify(translated_description, translated_description, weather_context)

        possible_duplicate, matched_report_id = self.duplicate_service.detect(
            db,
            location=payload.location,
            category=classified.category,
            description=translated_description,
        )

        report = Report(
            id=new_report_id(),
            name=payload.name.strip() if payload.name else None,
            contact=payload.contact.strip() if payload.contact else None,
            location=payload.location,
            normalized_location=payload.location.lower().strip(),
            location_lat=geocoded.get("lat"),
            location_lon=geocoded.get("lon"),
            description=payload.description,
            translated_description=translated_description if translated_description != payload.description else None,
            language=payload.language,
            category=classified.category,
            urgency=classified.urgency,
            summary=classified.summary,
            suggested_action=classified.suggestedAction,
            confidence=classified.confidence,
            possible_duplicate=possible_duplicate,
            matched_report_id=matched_report_id,
            status="pending",
            source_metadata={"geocoding": geocoded, "weather": weather_context},
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    def get_report(self, db: Session, report_id: str) -> Report:
        report = db.get(Report, report_id)
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
        return report

    def list_reports(self, db: Session, filters: ReportFilters) -> tuple[list[Report], int]:
        query = db.query(Report)
        if filters.category:
            query = query.filter(Report.category == filters.category)
        if filters.urgency:
            query = query.filter(Report.urgency == filters.urgency)
        if filters.status:
            query = query.filter(Report.status == filters.status)
        if filters.search:
            search = f"%{filters.search.strip()}%"
            query = query.filter(
                or_(
                    Report.description.ilike(search),
                    Report.location.ilike(search),
                    Report.summary.ilike(search),
                )
            )
        if filters.date_from:
            query = query.filter(Report.created_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(Report.created_at <= filters.date_to)

        total = query.count()
        offset = (filters.page - 1) * filters.page_size
        items = query.order_by(Report.created_at.desc()).offset(offset).limit(filters.page_size).all()
        return items, total

    def update_status(self, db: Session, report_id: str, payload: StatusUpdateRequest) -> Report:
        report = self.get_report(db, report_id)
        report.status = payload.status
        report.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(report)
        return report

    def delete_report(self, db: Session, report_id: str) -> None:
        report = self.get_report(db, report_id)
        db.delete(report)
        db.commit()

    def stats(self, db: Session) -> dict[str, object]:
        total = db.query(func.count(Report.id)).scalar() or 0
        category_breakdown = dict(db.query(Report.category, func.count(Report.id)).group_by(Report.category).all())
        urgency_breakdown = dict(db.query(Report.urgency, func.count(Report.id)).group_by(Report.urgency).all())
        return {
            "totalReports": total,
            "criticalReports": db.query(func.count(Report.id)).filter(Report.urgency == "critical").scalar() or 0,
            "pendingReports": db.query(func.count(Report.id)).filter(Report.status == "pending").scalar() or 0,
            "resolvedReports": db.query(func.count(Report.id)).filter(Report.status == "resolved").scalar() or 0,
            "categoryBreakdown": category_breakdown,
            "urgencyBreakdown": urgency_breakdown,
        }
