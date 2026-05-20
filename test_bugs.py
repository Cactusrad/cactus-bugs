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


# ---------------------------------------------------------------------------
# Deduplication / occurrence counting (feat/error-dedup-occurrence)
# ---------------------------------------------------------------------------

_DEDUP_PROJECT = {}


def _project_key():
    """En-tete Bearer d'un projet partage (cree une seule fois).

    Un seul projet pour tous les tests dedup : sur master `reference` est unique
    GLOBALEMENT (le fix per-projet est sur une autre branche), donc creer
    plusieurs projets ferait collisionner les references (BUG-001/ERR-001). Les
    fingerprints sont distincts par test -> aucune interference de dedup.
    """
    if not _DEDUP_PROJECT:
        resp = client.post(
            "/api/v1/admin/projects",
            json={"name": "Dedup Suite", "slug": "dedup-suite"},
            headers=ADMIN_AUTH,
        )
        assert resp.status_code == 200, resp.text
        _DEDUP_PROJECT["h"] = {"Authorization": f"Bearer {resp.json()['api_key']}"}
    return _DEDUP_PROJECT["h"]


def test_dedup_same_fingerprint_increments():
    """2 POST meme fingerprint -> 1 seule issue (meme reference), count -> 2."""
    h = _project_key()
    payload = {"type": "frontend_error", "title": "TypeError: x is undefined",
               "fingerprint": "fp-aaa"}
    r1 = client.post("/api/v1/issues", json=payload, headers=h)
    assert r1.status_code == 200, r1.text
    assert r1.json()["occurrence_count"] == 1
    ref1 = r1.json()["reference"]

    r2 = client.post("/api/v1/issues", json=payload, headers=h)
    assert r2.status_code == 200
    assert r2.json()["reference"] == ref1, "doit reutiliser la meme issue"
    assert r2.json()["occurrence_count"] == 2


def test_no_fingerprint_always_creates():
    """Sans fingerprint -> chaque POST cree une nouvelle issue (legacy)."""
    h = _project_key()
    p = {"type": "bug", "title": "Bug manuel"}
    r1 = client.post("/api/v1/issues", json=p, headers=h)
    r2 = client.post("/api/v1/issues", json=p, headers=h)
    assert r1.json()["reference"] != r2.json()["reference"]


def test_dedup_different_fingerprints_separate():
    """Fingerprints differents -> issues distinctes."""
    h = _project_key()
    r1 = client.post("/api/v1/issues",
                     json={"type": "frontend_error", "title": "A", "fingerprint": "f1"},
                     headers=h)
    r2 = client.post("/api/v1/issues",
                     json={"type": "frontend_error", "title": "B", "fingerprint": "f2"},
                     headers=h)
    assert r1.json()["reference"] != r2.json()["reference"]


def test_frontend_error_reference_prefix():
    """Le type frontend_error genere une reference ERR-NNN."""
    h = _project_key()
    r = client.post("/api/v1/issues",
                    json={"type": "frontend_error", "title": "E", "fingerprint": "fp-err"},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["reference"].startswith("ERR-"), r.json()


def test_dedup_recreates_after_resolved():
    """Une recurrence APRES resolution cree une nouvelle issue (regression)."""
    h = _project_key()
    fp = {"type": "frontend_error", "title": "Recurrent", "fingerprint": "fp-recur"}
    r1 = client.post("/api/v1/issues", json=fp, headers=h)
    ref1 = r1.json()["reference"]
    # Resoudre l'issue
    rs = client.patch(f"/api/v1/issues/{ref1}/status",
                      json={"status": "termine"}, headers=h)
    assert rs.status_code == 200, rs.text
    # Nouvelle occurrence -> nouvelle issue (l'ancienne est fermee)
    r2 = client.post("/api/v1/issues", json=fp, headers=h)
    assert r2.json()["reference"] != ref1
    assert r2.json()["occurrence_count"] == 1


# ============================================================================
# Tests : aguillage par projet (BUG-152 leak — voir _resolve_project_or_400)
#
# Avant ce fix, le bypass LAN OU l'admin master key sans ?project= laissait
# les endpoints scopés répondre cross-projet :
#   - /issues listait tous les projets mélangés
#   - /issues/{ref} renvoyait la première ligne match (peu importe le projet)
#   - PATCH /issues/{ref}/status patchait n'importe quelle ligne match
# C'est exactement ce qui faisait apparaître BUG-152 de "Terminal Launcher"
# dans la liste d'un user qui pensait travailler sur "Rad Quote v3".
#
# Le fix : tout endpoint scopé exige un projet identifiable (Bearer projet
# OU ?project=<slug>). Sinon 400. Plus jamais de leak silencieux.
# ============================================================================


def _admin_create_project(slug, name=None):
    """Helper : crée un projet via l'admin endpoint, renvoie (id, api_key)."""
    resp = client.post(
        "/api/v1/admin/projects",
        json={"name": name or f"Project {slug}", "slug": slug},
        headers=ADMIN_AUTH,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["id"], body["api_key"]


def _create_issue(project_key, title):
    """Helper : crée un issue dans le projet identifié par sa clé."""
    resp = client.post(
        "/api/v1/issues",
        json={"type": "bug", "title": title, "priority": "normale"},
        headers={"Authorization": f"Bearer {project_key}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["reference"]


def test_list_admin_without_project_returns_400():
    """Admin master key SANS ?project= → 400 avec la liste des slugs valides."""
    resp = client.get("/api/v1/issues", headers=ADMIN_AUTH)
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["error"] == "project_required"
    assert "valid_slugs" in body["detail"]
    assert isinstance(body["detail"]["valid_slugs"], list)


def test_list_admin_with_project_slug_scopes():
    """Admin master key + ?project=<slug> → scoped à ce projet uniquement."""
    _, key_a = _admin_create_project("scope-a")
    _, key_b = _admin_create_project("scope-b")
    _create_issue(key_a, "Issue A unique titre")
    _create_issue(key_b, "Issue B unique titre")

    # Les références peuvent coïncider (BUG-001 dans chaque projet) — on
    # compare par titre, qui est lui unique par construction.
    resp = client.get("/api/v1/issues?project=scope-a", headers=ADMIN_AUTH)
    assert resp.status_code == 200
    titles = [it["title"] for it in resp.json()["data"]]
    assert "Issue A unique titre" in titles
    assert "Issue B unique titre" not in titles, \
        "leak : issue de scope-b visible via ?project=scope-a"


def test_list_admin_unknown_slug_400():
    """Slug inexistant → 400 explicite."""
    resp = client.get("/api/v1/issues?project=does-not-exist", headers=ADMIN_AUTH)
    assert resp.status_code == 400


def test_get_issue_by_ref_no_cross_project_leak():
    """Même ref dans 2 projets → ?project=<slug> renvoie la BONNE.

    Avant le fix, GET /issues/{ref} sans project renvoyait la première
    ligne matchée (souvent du mauvais projet). Avec scope-c et scope-d
    partageant la ref BUG-001, on doit obtenir l'issue du projet demandé."""
    _, key_c = _admin_create_project("scope-c")
    _, key_d = _admin_create_project("scope-d")
    ref_c = _create_issue(key_c, "Issue dans scope-c")
    ref_d = _create_issue(key_d, "Issue dans scope-d")
    assert ref_c == ref_d, "les 2 projets devraient avoir attribué la même 1re ref"

    # GET avec project=scope-c
    resp = client.get(f"/api/v1/issues/{ref_c}?project=scope-c", headers=ADMIN_AUTH)
    assert resp.status_code == 200
    assert resp.json()["issue"]["title"] == "Issue dans scope-c"

    # GET avec project=scope-d → l'autre
    resp = client.get(f"/api/v1/issues/{ref_d}?project=scope-d", headers=ADMIN_AUTH)
    assert resp.status_code == 200
    assert resp.json()["issue"]["title"] == "Issue dans scope-d"


def test_get_issue_by_ref_no_project_400():
    """GET /issues/{ref} sans project (admin) → 400, jamais de pick aléatoire."""
    _, key_e = _admin_create_project("scope-e")
    ref = _create_issue(key_e, "Solo")
    resp = client.get(f"/api/v1/issues/{ref}", headers=ADMIN_AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "project_required"


def test_patch_status_no_cross_project_leak():
    """PATCH /status sur une ref partagée par 2 projets : ?project= cible
    correctement, jamais l'autre projet."""
    _, key_f = _admin_create_project("scope-f")
    _, key_g = _admin_create_project("scope-g")
    ref_f = _create_issue(key_f, "f")
    ref_g = _create_issue(key_g, "g")
    assert ref_f == ref_g

    # PATCH du projet scope-f → termine
    resp = client.patch(
        f"/api/v1/issues/{ref_f}/status?project=scope-f",
        json={"status": "termine"},
        headers=ADMIN_AUTH,
    )
    assert resp.status_code == 200

    # L'issue de scope-g doit rester intacte (statut initial, pas termine)
    resp = client.get(f"/api/v1/issues/{ref_g}?project=scope-g", headers=ADMIN_AUTH)
    assert resp.status_code == 200
    assert resp.json()["issue"]["status"] != "termine", \
        "PATCH a fuité vers scope-g — la régression BUG-152 est revenue"


def test_list_with_project_key_still_scoped_auto():
    """La clé projet (Bearer key d'un projet) reste auto-scopée, pas besoin
    de ?project= (rétro-compatibilité totale pour les clients existants)."""
    _, key_h = _admin_create_project("scope-h")
    _, key_i = _admin_create_project("scope-i")
    ref_h = _create_issue(key_h, "h-only")
    _create_issue(key_i, "i-only")

    resp = client.get(
        "/api/v1/issues",
        headers={"Authorization": f"Bearer {key_h}"},
    )
    assert resp.status_code == 200
    titles = [it["title"] for it in resp.json()["data"]]
    assert "h-only" in titles
    assert "i-only" not in titles, "leak via clé projet — ne devrait pas arriver"
