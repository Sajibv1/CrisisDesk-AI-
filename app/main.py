from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.response import generic_exception_handler, http_exception_handler, request_validation_exception_handler
from app.db.base import Base
from app.db.init_db import seed_if_needed
from app.db.session import build_engine, build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", description="AI-powered triage API for public-service reports.")
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    app.state.engine = engine
    app.state.SessionLocal = session_factory

    try:
        Base.metadata.create_all(bind=engine)
        with session_factory() as session:
            seed_if_needed(session, settings)
    except OperationalError:
        app.state.database_ready = False
    else:
        app.state.database_ready = True

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RateLimitMiddleware, max_requests_per_minute=settings.rate_limit_per_minute)

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(reports_router)
    return app


app = create_app()
