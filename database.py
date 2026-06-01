"""Database configuration for bugs service."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/app/data/bugs.db")

# Ensure directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _conn_record):
    """WAL : lecteurs et écrivains ne se bloquent plus (le tracker subit des
    accès concurrents — page = 3 requêtes // + créations de bugs en fond).
    Évite les pics de latence vus en mode `delete` (write = verrou global).
    busy_timeout : attend jusqu'à 15s un verrou au lieu d'échouer tôt.
    Posé à chaque connexion -> survit aussi à une base recréée."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=15000")
    cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def migrate_db():
    """Migrations additives idempotentes (create_all n'ALTER pas les tables
    existantes). Ajoute les colonnes de deduplication a `issues` si absentes.

    SQLite : ADD COLUMN est sans danger et instantane (pas de reecriture de
    table). On verifie d'abord via PRAGMA table_info pour rester idempotent.
    """
    from sqlalchemy import text
    additive = {
        "fingerprint": "VARCHAR(64)",
        "occurrence_count": "INTEGER NOT NULL DEFAULT 1",
        "last_seen_at": "DATETIME",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(issues)"))}
        had_last_seen = "last_seen_at" in existing
        for name, ddl in additive.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE issues ADD COLUMN {name} {ddl}"))
        if not had_last_seen:
            # Backfill : les issues existantes prennent created_at comme last_seen.
            conn.execute(text(
                "UPDATE issues SET last_seen_at = created_at WHERE last_seen_at IS NULL"
            ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_issues_fingerprint ON issues (fingerprint)"
        ))
