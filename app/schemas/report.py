from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["medical", "fire", "accident", "crime", "flood", "utility", "public_service", "infrastructure", "other"]
Urgency = Literal["low", "medium", "high", "critical"]
Language = Literal["bn", "en", "unknown"]
Status = Literal["pending", "in_review", "assigned", "resolved", "rejected"]


class ReportCreate(BaseModel):
    name: str | None = None
    contact: str | None = None
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)
    language: Language = "unknown"

    @field_validator("location", "description")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value


class StatusUpdateRequest(BaseModel):
    status: Status


class ReportFilters(BaseModel):
    category: Category | None = None
    urgency: Urgency | None = None
    status: Status | None = None
    search: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ReportOut(BaseModel):
    id: str
    name: str | None
    contact: str | None
    location: str
    description: str
    language: str
    category: str
    urgency: str
    summary: str
    suggestedAction: str
    confidence: float
    possibleDuplicate: bool
    matchedReportId: str | None
    status: str
    createdAt: datetime
    updatedAt: datetime


class ReportListResponse(BaseModel):
    items: list[ReportOut]
    total: int
    page: int
    page_size: int


class StatsSummaryResponse(BaseModel):
    totalReports: int
    criticalReports: int
    pendingReports: int
    resolvedReports: int
    categoryBreakdown: dict[str, int]
    urgencyBreakdown: dict[str, int]


class ClassifiedReport(BaseModel):
    category: Category
    urgency: Urgency
    summary: str
    suggestedAction: str
    confidence: float = Field(ge=0.0, le=1.0)
