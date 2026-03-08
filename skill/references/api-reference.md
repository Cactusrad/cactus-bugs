# API Reference - Bugs Service

**Base URL:** `http://localhost:9010`

## Authentification

Toutes les requetes necessitent un header `Authorization`.

- `Authorization: Bearer {API_KEY}` — Acces aux issues du projet uniquement
- `Authorization: Bearer {ADMIN_MASTER_KEY}` — Acces admin cross-projets
- `Authorization: Basic {base64(username:password)}` — Acces utilisateur

---

## Health Check

```
GET /health
```

Reponse: `{"status": "ok", "service": "bugs-api"}`

---

## Admin (Master Key ou admin user requis)

### Lister les projets

```
GET /api/v1/admin/projects
```

### Creer un projet

```
POST /api/v1/admin/projects
```

Body:
```json
{
  "name": "Mon Projet",
  "slug": "mon-projet",
  "webhook_url": "https://..."
}
```

Retourne le projet avec l'API key en clair (visible une seule fois).

### Modifier un projet

```
PATCH /api/v1/admin/projects/{project_id}
```

Body (tous les champs optionnels):
```json
{
  "name": "Nouveau Nom",
  "slug": "nouveau-slug",
  "webhook_url": "https://...",
  "is_active": true
}
```

### Regenerer une API key

```
POST /api/v1/admin/projects/{project_id}/regenerate-key
```

### Gestion des utilisateurs

```
POST /api/v1/admin/users          — Creer un utilisateur
GET /api/v1/admin/users           — Lister les utilisateurs
DELETE /api/v1/admin/users/{id}   — Supprimer un utilisateur
```

Body creation:
```json
{
  "username": "nom",
  "password": "motdepasse",
  "is_admin": false
}
```

---

## Issues

### Lister les issues

```
GET /api/v1/issues
```

Query params:

| Param | Type | Description |
|-------|------|-------------|
| status | string | Filtrer par statut (comma-separated): `nouveau`, `en_cours`, `a_approuver`, `termine`, `rejete` |
| type | string | Filtrer par type: `bug`, `suggestion`, `feature`, `improvement` |
| priority | string | Filtrer par priorite: `basse`, `normale`, `haute`, `critique` |
| assignee | string | Filtrer par assignee |
| page | int | Page (default: 1) |
| limit | int | Items par page (default: 20) |

Reponse:
```json
{
  "data": [
    {
      "id": 1,
      "reference": "BUG-001",
      "type": "bug",
      "title": "Bouton ne fonctionne pas",
      "description": "...",
      "status": "nouveau",
      "priority": "haute",
      "assignee": null,
      "reporter": "Pierre",
      "reporter_email": null,
      "context_data": {},
      "created_at": "2026-01-15T10:30:00",
      "updated_at": "2026-01-15T10:30:00",
      "resolved_at": null,
      "comments_count": 0,
      "attachments_count": 0
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 42,
    "pages": 3
  }
}
```

### Creer une issue

```
POST /api/v1/issues
```

Body:
```json
{
  "type": "bug",
  "title": "Description courte",
  "description": "Details du probleme...",
  "priority": "normale",
  "reporter": "nom ou email",
  "reporter_email": "email@example.com",
  "context_data": {
    "url": "https://...",
    "user_agent": "...",
    "custom_field": "value"
  }
}
```

Reponse: Issue creee avec `reference` unique basee sur le type (ex: `BUG-001`, `SUG-002`).

**Important:** Requiert une API key **projet** (pas admin). L'issue est rattachee au projet de la key.

### Obtenir une issue

```
GET /api/v1/issues/{reference}
```

Retourne l'issue complete avec commentaires, attachments et historique:
```json
{
  "issue": { ... },
  "comments": [ ... ],
  "attachments": [ ... ],
  "history": [
    {
      "field": "status",
      "old": "nouveau",
      "new": "en_cours",
      "by": "Pierre",
      "at": "2026-01-16T09:00:00"
    }
  ]
}
```

### Modifier une issue

```
PUT /api/v1/issues/{reference}
```

Body (tous les champs optionnels):
```json
{
  "title": "Nouveau titre",
  "description": "Nouvelle description",
  "priority": "haute",
  "assignee": "simon"
}
```

### Changer le statut

```
PATCH /api/v1/issues/{reference}/status
```

Body:
```json
{
  "status": "en_cours",
  "assignee": "simon",
  "comment": "Je prends en charge"
}
```

Workflow des statuts:
```
nouveau -> en_cours -> a_approuver -> termine
                    \-> rejete
```

Quand le statut passe a `termine`, `resolved_at` est automatiquement rempli.

### Supprimer une issue

```
DELETE /api/v1/issues/{reference}
```

---

## Commentaires

### Ajouter un commentaire

```
POST /api/v1/issues/{reference}/comments
```

Body:
```json
{
  "author": "nom",
  "content": "Texte du commentaire"
}
```

### Lister les commentaires

```
GET /api/v1/issues/{reference}/comments
```

---

## Attachments

### Uploader un fichier

```
POST /api/v1/issues/{reference}/attachments
```

Form data: `file` (multipart/form-data)

Types acceptes: PNG, JPEG, GIF, WebP, MP4, WebM, PDF
Taille max: 10 MB

### Telecharger un fichier

```
GET /api/v1/attachments/{attachment_id}
```

### Obtenir le thumbnail

```
GET /api/v1/attachments/{attachment_id}/thumbnail
```

---

## Statistiques

```
GET /api/v1/stats
```

Reponse:
```json
{
  "total": 20,
  "by_status": {
    "nouveau": 5,
    "en_cours": 3,
    "termine": 12
  },
  "by_type": {
    "bug": 15,
    "suggestion": 5
  },
  "by_priority": {
    "haute": 4,
    "normale": 12,
    "basse": 4
  }
}
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| 400 | Donnees invalides ou slug deja existant |
| 401 | API key invalide ou manquante |
| 403 | Acces refuse (admin requis) |
| 404 | Issue/projet/attachment non trouve |
| 422 | Donnees de validation invalides |
