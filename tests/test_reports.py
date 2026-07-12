from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from app.db.init_db import seed_if_needed


def build_test_app(tmp_path):
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://citizen_reports:citizen_reports@localhost:5432/citizen_reports",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="admin123",
        JWT_SECRET_KEY="test-secret",
        RATE_LIMIT_PER_MINUTE=100,
    )
    app = create_app(settings)
    with app.state.engine.begin() as connection:
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
    with app.state.SessionLocal() as session:
        seed_if_needed(session, settings)
    return app


def test_submit_and_fetch_report(tmp_path):
    app = build_test_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/reports",
        json={
            "name": "Rahim",
            "contact": "017xxxxxxxx",
            "location": "Sylhet Bondor Bazar",
            "description": "There is a fire near a shop and people are trapped.",
            "language": "bn",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["category"] == "fire"
    report_id = payload["data"]["id"]

    detail = client.get(f"/api/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["report"]["id"] == report_id


def test_validation_error_is_structured(tmp_path):
    app = build_test_app(tmp_path)
    client = TestClient(app)

    response = client.post("/api/reports", json={"location": "", "description": ""})
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert "details" in payload
