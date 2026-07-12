from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import success_response
from app.core.security import get_current_admin
from app.db.session import get_db
from app.models.admin import AdminUser
from app.schemas.report import ReportCreate, ReportFilters, ReportOut, ReportListResponse, StatusUpdateRequest
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])
service = ReportService()


def serialize_report(report) -> dict[str, object]:
    return ReportOut(
        id=report.id,
        name=report.name,
        contact=report.contact,
        location=report.location,
        description=report.description,
        language=report.language,
        category=report.category,
        urgency=report.urgency,
        summary=report.summary,
        suggestedAction=report.suggested_action,
        confidence=report.confidence,
        possibleDuplicate=report.possible_duplicate,
        matchedReportId=report.matched_report_id,
        status=report.status,
        createdAt=report.created_at,
        updatedAt=report.updated_at,
    ).model_dump()


@router.post("", response_model=None)
async def submit_report(payload: ReportCreate, db: Session = Depends(get_db)):
    report = await service.create_report(db, payload)
    return success_response("Report submitted successfully.", serialize_report(report))


@router.get("", response_model=None)
def list_reports(
    category: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = ReportFilters.model_validate(
        {
            "category": category,
            "urgency": urgency,
            "status": status,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
            "page": page,
            "page_size": page_size,
        }
    )
    items, total = service.list_reports(db, filters)
    payload = ReportListResponse(items=[ReportOut.model_validate(serialize_report(item)) for item in items], total=total, page=page, page_size=page_size)
    return success_response("Reports fetched successfully.", payload.model_dump())


@router.get("/{report_id}", response_model=None)
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = service.get_report(db, report_id)
    return success_response("Report fetched successfully.", {"report": serialize_report(report)})


@router.patch("/{report_id}/status", response_model=None)
def update_status(report_id: str, payload: StatusUpdateRequest, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    report = service.update_status(db, report_id, payload)
    return success_response("Report status updated successfully.", serialize_report(report))


@router.delete("/{report_id}", response_model=None)
def delete_report(report_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    service.delete_report(db, report_id)
    return success_response("Report deleted successfully.", {"id": report_id})


@router.get("/stats/summary", response_model=None)
def stats_summary(db: Session = Depends(get_db)):
    return success_response("Analytics summary fetched successfully.", service.stats(db))
