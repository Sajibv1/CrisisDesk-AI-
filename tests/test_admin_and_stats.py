from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.db.init_db import seed_if_needed
from app.main import create_app


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


def get_token(client: TestClient) -> str:
    response = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_admin_login_and_stats(tmp_path):
    app = build_test_app(tmp_path)
    client = TestClient(app)
    token = get_token(client)

    created = client.post(
        "/api/reports",
        json={
            "location": "Dhaka",
            "description": "Power outage in the area.",
            "language": "en",
        },
    )
    report_id = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/reports/{report_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "assigned"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "assigned"

    stats = client.get("/api/reports/stats/summary")
    assert stats.status_code == 200
    assert stats.json()["success"] is True
    assert "data" in stats.json()
