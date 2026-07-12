from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str):
    return create_engine(database_url, future=True, echo=False)


def build_session_factory(engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db(request: Request) -> Generator[Session, None, None]:
    session: Session = request.app.state.SessionLocal()
    try:
        yield session
    finally:
        session.close()
