"""Tests for Bugs Service API."""

import os

# Set test environment variables before importing app
os.environ["DATABASE_PATH"] = "/tmp/test_bugs.db"
os.environ["ADMIN_MASTER_KEY"] = "test_master_key_12345"

# Remove stale test DB
if os.path.exists("/tmp/test_bugs.db"):
    os.remove("/tmp/test_bugs.db")

from fastapi.testclient import TestClient

from database import init_db
from main import app

# Initialize DB tables before tests
init_db()

client = TestClient(app)

ADMIN_AUTH = {"Authorization": "Bearer test_master_key_12345"}


def test_health():
    """GET /health returns 200 with ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_unauthorized_stats():
    """GET /api/v1/stats without auth returns 401."""
    response = client.get("/api/v1/stats")
    assert response.status_code == 401


def test_unauthorized_issues():
    """GET /api/v1/issues without auth returns 401."""
    response = client.get("/api/v1/issues")
    assert response.status_code == 401


def test_create_project_admin():
    """POST /api/v1/admin/projects with admin key succeeds."""
    response = client.post(
        "/api/v1/admin/projects",
        json={"name": "Test Project", "slug": "test-ci"},
        headers=ADMIN_AUTH,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["slug"] == "test-ci"
    assert "api_key" in data


def test_list_projects_admin():
    """GET /api/v1/admin/projects with admin key returns projects."""
    response = client.get("/api/v1/admin/projects", headers=ADMIN_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_stats_with_admin_key():
    """GET /api/v1/stats with admin key succeeds."""
    response = client.get("/api/v1/stats", headers=ADMIN_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_status" in data


def test_create_project_no_auth():
    """POST /api/v1/admin/projects without auth returns 401."""
    response = client.post(
        "/api/v1/admin/projects",
        json={"name": "Nope", "slug": "nope"},
    )
    assert response.status_code == 401


def test_create_project_duplicate_slug():
    """POST /api/v1/admin/projects with duplicate slug returns 400."""
    response = client.post(
        "/api/v1/admin/projects",
        json={"name": "Duplicate", "slug": "test-ci"},
        headers=ADMIN_AUTH,
    )
    assert response.status_code == 400
