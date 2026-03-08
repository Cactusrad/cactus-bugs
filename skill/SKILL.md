---
name: bugs
description: Bug and suggestion tracker via the Cactus Bugs Service. Use this skill to (1) add a floating Bug Report button to any app (React, Vue, HTML), (2) list/filter bugs for a project, (3) create bugs with screenshots, (4) update bug status. Trigger when the user mentions bugs, bug report, report a bug, or /bugs.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Bugs Service - Local Bug Tracker

Self-hosted bug/suggestion tracking service for all your projects.

**API Base URL:** Configured via `BUGS_SERVICE_URL` environment variable
**Default port:** `9010` (Docker container)

## Authentication

All requests require `Authorization: Bearer {API_KEY}` header.
Admin endpoints require the `ADMIN_MASTER_KEY` or a user with `is_admin=true`.

## Reference System

References are based on the issue **type**, not the project:
- `BUG-001` for bugs
- `SUG-002` for suggestions
- `FEAT-003` for features
- `IMP-004` for improvements

Counter is per-project (numbers are not sequential by type).

## Main Actions

### 1. List bugs for a project

```bash
# List open bugs
curl -s "${BUGS_SERVICE_URL}/api/v1/issues?status=nouveau,en_cours" \
  -H "Authorization: Bearer ${API_KEY}" | jq

# Filter by type/priority
curl -s "${BUGS_SERVICE_URL}/api/v1/issues?type=bug&priority=haute" \
  -H "Authorization: Bearer ${API_KEY}" | jq

# All bugs (admin - cross-project)
curl -s "${BUGS_SERVICE_URL}/api/v1/issues" \
  -H "Authorization: Bearer ${ADMIN_MASTER_KEY}" | jq
```

Available filters: `status`, `type`, `priority`, `assignee`, `page`, `limit`

### 2. View bug details

```bash
curl -s "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001" \
  -H "Authorization: Bearer ${API_KEY}" | jq
```

Returns: issue + comments + attachments + history.

### 3. Create a bug

```bash
curl -X POST "${BUGS_SERVICE_URL}/api/v1/issues" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "bug",
    "title": "Problem description",
    "description": "Details...",
    "priority": "normale",
    "reporter": "name",
    "reporter_email": "email@example.com",
    "context_data": {
      "url": "https://...",
      "user_agent": "..."
    }
  }'
```

Types: `bug`, `suggestion`, `feature`, `improvement`
Priorities: `basse`, `normale`, `haute`, `critique`

### 4. Update status

```bash
curl -X PATCH "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001/status" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"status": "en_cours", "assignee": "name", "comment": "Taking over"}'
```

**Status workflow:**
```
nouveau -> en_cours -> a_approuver -> termine
                    \-> rejete
```

### 5. Update an issue

```bash
curl -X PUT "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"title": "New title", "priority": "haute", "assignee": "dev1"}'
```

### 6. Add a comment

```bash
curl -X POST "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001/comments" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"author": "name", "content": "Comment text"}'
```

### 7. Upload a screenshot / attachment

```bash
curl -X POST "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001/attachments" \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "file=@screenshot.png"
```

Accepted types: PNG, JPEG, GIF, WebP, MP4, WebM, PDF. Max 10 MB.

### 8. Delete an issue

```bash
curl -X DELETE "${BUGS_SERVICE_URL}/api/v1/issues/BUG-001" \
  -H "Authorization: Bearer ${API_KEY}"
```

### 9. Statistics

```bash
curl -s "${BUGS_SERVICE_URL}/api/v1/stats" \
  -H "Authorization: Bearer ${API_KEY}" | jq
```

### 10. Admin: manage projects

```bash
# List projects
curl -s "${BUGS_SERVICE_URL}/api/v1/admin/projects" \
  -H "Authorization: Bearer ${ADMIN_MASTER_KEY}" | jq

# Create a project
curl -X POST "${BUGS_SERVICE_URL}/api/v1/admin/projects" \
  -H "Authorization: Bearer ${ADMIN_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "slug": "my-project"}'

# Rename a project
curl -X PATCH "${BUGS_SERVICE_URL}/api/v1/admin/projects/{ID}" \
  -H "Authorization: Bearer ${ADMIN_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name": "Real Name", "slug": "real-slug"}'
```

## Adding a Bug Report Button

See `references/bug-button.md` for ready-to-use React, Vue, and vanilla HTML components.

## Standard Workflow

When `/bugs` is invoked:

1. **Identify the project** - Look for an API key in .env, config, or CLAUDE.md
2. **If no key exists:**
   - Create a new project via admin POST endpoint
   - Configure the API key in the project (.env or equivalent)
3. **List bugs** - Show bugs with `nouveau` and `en_cours` status
4. **Available actions:**
   - Create a new bug/suggestion
   - Update a status
   - Add a comment/screenshot
   - View details of a specific bug
   - View statistics

## References

- `references/bug-button.md` - UI components for bug report button (React, Vue, HTML)
- `references/api-reference.md` - Complete API reference
