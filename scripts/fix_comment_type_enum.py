#!/usr/bin/env python3
"""
Migration : normalise comments.type en valeurs UPPERCASE (NAMES de l'enum
CommentType : COMMENT / STATUS_CHANGE / SYSTEM).

Audit /app-team-test ERP 2026-05-08 (tracker-tester) — la table comments
contenait un melange de valeurs UPPERCASE (1007 rows OK) et lowercase
(6 rows 'comment') + NULL (2 rows). SQLAlchemy str+Enum mappe par NAME
par defaut, donc les rows lowercase causaient :

  LookupError: 'comment' is not among the defined enum values.

Symptome : 500 Internal Server Error sur GET /api/v1/issues?limit=20
des que `comments_count=len(issue.comments)` (lazy-load) tombait sur
une row lowercase. Reproduit en prod (ERP .100) ; la liste de bugs
ne se chargeait pas pour les bugs concernes.

Origine probable : insertions Claude via un chemin qui passait .value
au lieu du membre Enum (ou copy-paste d'un payload API).

Idempotent — safe a relancer.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'db' / 'bugs.db'

VALID_NAMES = {'COMMENT', 'STATUS_CHANGE', 'SYSTEM'}


def main():
    if not DB_PATH.exists():
        print(f"ERREUR : {DB_PATH} introuvable", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    # Avant : decompte par valeur
    rows = cur.execute(
        "SELECT type, COUNT(*) FROM comments GROUP BY type"
    ).fetchall()
    print("Avant migration :", rows)

    # NULL et lowercase 'comment' -> 'COMMENT'
    cur.execute(
        "UPDATE comments SET type = 'COMMENT' "
        "WHERE type IS NULL OR type = 'comment'"
    )
    print(f"  Lignes corrigees (NULL/'comment' -> 'COMMENT') : {cur.rowcount}")

    # lowercase 'status_change' -> 'STATUS_CHANGE'
    cur.execute(
        "UPDATE comments SET type = 'STATUS_CHANGE' "
        "WHERE type = 'status_change'"
    )
    print(f"  Lignes corrigees ('status_change' -> 'STATUS_CHANGE') : {cur.rowcount}")

    # lowercase 'system' -> 'SYSTEM'
    cur.execute(
        "UPDATE comments SET type = 'SYSTEM' "
        "WHERE type = 'system'"
    )
    print(f"  Lignes corrigees ('system' -> 'SYSTEM') : {cur.rowcount}")

    con.commit()

    rows_after = cur.execute(
        "SELECT type, COUNT(*) FROM comments GROUP BY type"
    ).fetchall()
    print("Apres migration :", rows_after)

    invalid = [r for r in rows_after if r[0] not in VALID_NAMES]
    if invalid:
        print(f"ERREUR : valeurs invalides restantes : {invalid}", file=sys.stderr)
        sys.exit(2)

    print("OK : tous les comments.type sont des NAMES valides de CommentType.")


if __name__ == '__main__':
    main()
