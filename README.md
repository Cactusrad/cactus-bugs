# Cactus Bugs - Self-Hosted Bug Tracker

A lightweight, self-hosted bug tracking service with a REST API, a web dashboard, and a **Claude Code skill** for AI-assisted bug management.

Built with FastAPI + SQLite + nginx. Ships as Docker containers. Zero external dependencies.

```
Your App                        Bugs Service (Docker)
+------------------+            +-------------------+
| Floating Bug     |  REST API  |  FastAPI backend   |
| Report Button  --------->     |  SQLite database   |
| (React/Vue/HTML) |            |  File attachments  |
+------------------+            +-------------------+
                                        |
Claude Code                             |
+------------------+    /bugs skill     |
| "Show me open  ---------------------->|
|  bugs for       |    curl API calls   |
|  my-project"    |<-----------------------
+------------------+
```

## Features

- Multi-project support with per-project API keys
- Issue types: Bug, Suggestion, Feature, Improvement
- Auto-generated references: `BUG-001`, `SUG-002`, `FEAT-003`, `IMP-004`
- Status workflow: `nouveau` -> `en_cours` -> `a_approuver` -> `termine` / `rejete`
- File attachments with auto-thumbnail generation (images)
- Full audit history on every change
- Webhook notifications on issue creation
- Built-in web dashboard (SPA)
- Claude Code skill for AI-assisted bug management
- Drop-in floating bug report button (React, Vue, vanilla HTML)
- CI/CD pipeline (GitHub Actions)

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Cactusrad/cactus-bugs.git
cd cactus-bugs

# Generate your admin master key
cp .env.example .env
echo "ADMIN_MASTER_KEY=$(openssl rand -hex 32)" > .env
```

### 2. Start with Docker

```bash
docker compose up -d
```

The service starts on **port 9010**:
- Web dashboard: `http://localhost:9010`
- API: `http://localhost:9010/api/v1/`
- Health check: `http://localhost:9010/health`

### 3. Create your first project

```bash
# Read your admin key
export ADMIN_KEY=$(grep ADMIN_MASTER_KEY .env | cut -d= -f2)

# Create a project (the API key is shown only once!)
curl -X POST "http://localhost:9010/api/v1/admin/projects" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "slug": "my-app"}'
```

Save the returned `api_key` — it's your project's authentication token.

### 4. Create your first bug

```bash
export API_KEY="the_key_from_step_3"

curl -X POST "http://localhost:9010/api/v1/issues" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "bug",
    "title": "Login button does not respond",
    "description": "Clicking the login button on /auth does nothing. Console shows CORS error.",
    "priority": "haute",
    "reporter": "Pierre"
  }'
```

---

## Floating Bug Report Button

The killer feature: a **floating button** that your users click to report bugs directly from your app. It captures the page URL, browser info, and optional screenshots — all sent to your Bugs Service automatically.

### How It Works

```
User clicks bug button -> Modal opens -> User fills title + description
                                      -> Optional: capture screenshot
                                      -> Submit
                                            |
                                            v
                                     POST /api/v1/issues
                                     (with context_data: URL, user_agent)
                                            |
                                            v
                                     If screenshot captured:
                                     POST /api/v1/issues/{ref}/attachments
                                            |
                                            v
                                     Issue created! (BUG-042)
                                     Webhook sent (if configured)
```

### React

```bash
npm install html2canvas  # For screenshot capture
```

```tsx
// BugReportButton.tsx
import { useState } from 'react';

interface BugReportProps {
  apiUrl: string;       // Your bugs service URL (e.g. "http://localhost:9010")
  apiKey: string;       // Project API key
  projectSlug: string;  // Project identifier
  reporter?: string;    // Pre-fill reporter name
}

export function BugReportButton({ apiUrl, apiKey, projectSlug, reporter = 'anonymous' }: BugReportProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<'bug' | 'suggestion'>('bug');
  const [priority, setPriority] = useState<'basse' | 'normale' | 'haute' | 'critique'>('normale');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const captureScreenshot = async () => {
    try {
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(document.body);
      canvas.toBlob((blob) => {
        if (blob) {
          setScreenshot(new File([blob], 'screenshot.png', { type: 'image/png' }));
        }
      });
    } catch (e) {
      console.error('Screenshot capture failed:', e);
    }
  };

  const submit = async () => {
    if (!title.trim()) return;
    setLoading(true);

    try {
      // 1. Create the issue
      const res = await fetch(`${apiUrl}/api/v1/issues`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type,
          title,
          description,
          priority,
          reporter,
          context_data: {
            url: window.location.href,
            user_agent: navigator.userAgent,
          },
        }),
      });

      const issue = await res.json();

      // 2. Upload screenshot if captured
      if (screenshot && issue.reference) {
        const formData = new FormData();
        formData.append('file', screenshot);
        await fetch(`${apiUrl}/api/v1/issues/${issue.reference}/attachments`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${apiKey}` },
          body: formData,
        });
      }

      // 3. Show success feedback
      setSuccess(true);
      setTimeout(() => {
        setIsOpen(false);
        setSuccess(false);
        setTitle('');
        setDescription('');
        setScreenshot(null);
      }, 2000);
    } catch (e) {
      console.error('Bug report failed:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed', bottom: '20px', right: '20px',
          background: '#dc2626', color: 'white', border: 'none',
          borderRadius: '50%', width: '56px', height: '56px',
          cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          fontSize: '24px', zIndex: 9999,
        }}
        title="Report a bug"
      >
        Bug
      </button>
    );
  }

  return (
    <div style={{
      position: 'fixed', bottom: '20px', right: '20px',
      background: 'white', borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      padding: '20px', width: '360px', maxHeight: '80vh',
      overflow: 'auto', zIndex: 9999,
    }}>
      {success ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <p style={{ fontSize: '18px', fontWeight: 'bold' }}>Bug reported!</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>Report a problem</h3>
            <button onClick={() => setIsOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px' }}>X</button>
          </div>

          <select value={type} onChange={(e) => setType(e.target.value as any)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px' }}>
            <option value="bug">Bug</option>
            <option value="suggestion">Suggestion</option>
            <option value="feature">Feature request</option>
          </select>

          <input type="text" placeholder="Problem title" value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px', boxSizing: 'border-box' }}
          />

          <textarea placeholder="Description (optional)" value={description}
            onChange={(e) => setDescription(e.target.value)} rows={4}
            style={{ width: '100%', padding: '8px', marginBottom: '12px', boxSizing: 'border-box', resize: 'vertical' }}
          />

          <select value={priority} onChange={(e) => setPriority(e.target.value as any)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px' }}>
            <option value="basse">Low priority</option>
            <option value="normale">Normal priority</option>
            <option value="haute">High priority</option>
            <option value="critique">Critical</option>
          </select>

          <div style={{ marginBottom: '16px' }}>
            <button onClick={captureScreenshot} style={{ marginRight: '8px', padding: '8px 12px' }}>
              Capture screenshot
            </button>
            {screenshot && <span style={{ color: 'green' }}>Ready</span>}
          </div>

          <button onClick={submit} disabled={loading || !title.trim()}
            style={{
              width: '100%', padding: '12px',
              background: loading ? '#ccc' : '#dc2626',
              color: 'white', border: 'none', borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}>
            {loading ? 'Sending...' : 'Send report'}
          </button>
        </>
      )}
    </div>
  );
}
```

**Usage in your app:**

```tsx
import { BugReportButton } from './BugReportButton';

function App() {
  return (
    <>
      {/* Your app content */}
      <BugReportButton
        apiUrl="http://localhost:9010"
        apiKey="YOUR_PROJECT_API_KEY"
        projectSlug="my-app"
        reporter="user@email.com"
      />
    </>
  );
}
```

### Vue

```vue
<template>
  <div>
    <button v-if="!isOpen" @click="isOpen = true" class="bug-btn">Bug</button>

    <div v-if="isOpen" class="bug-modal">
      <div v-if="success" class="success">
        <p>Bug reported!</p>
      </div>
      <template v-else>
        <div class="header">
          <h3>Report a problem</h3>
          <button @click="isOpen = false" class="close">X</button>
        </div>
        <select v-model="type">
          <option value="bug">Bug</option>
          <option value="suggestion">Suggestion</option>
          <option value="feature">Feature request</option>
        </select>
        <input v-model="title" placeholder="Problem title" />
        <textarea v-model="description" placeholder="Description (optional)" rows="4" />
        <select v-model="priority">
          <option value="basse">Low</option>
          <option value="normale">Normal</option>
          <option value="haute">High</option>
          <option value="critique">Critical</option>
        </select>
        <div class="screenshot-row">
          <button @click="captureScreenshot">Capture screenshot</button>
          <span v-if="screenshot" class="ready">Ready</span>
        </div>
        <button @click="submit" :disabled="loading || !title.trim()" class="submit">
          {{ loading ? 'Sending...' : 'Send report' }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{
  apiUrl: string;
  apiKey: string;
  reporter?: string;
}>();

const isOpen = ref(false);
const title = ref('');
const description = ref('');
const type = ref<'bug' | 'suggestion' | 'feature'>('bug');
const priority = ref<'basse' | 'normale' | 'haute' | 'critique'>('normale');
const screenshot = ref<File | null>(null);
const loading = ref(false);
const success = ref(false);

const captureScreenshot = async () => {
  const html2canvas = (await import('html2canvas')).default;
  const canvas = await html2canvas(document.body);
  canvas.toBlob((blob) => {
    if (blob) screenshot.value = new File([blob], 'screenshot.png', { type: 'image/png' });
  });
};

const submit = async () => {
  if (!title.value.trim()) return;
  loading.value = true;

  const res = await fetch(`${props.apiUrl}/api/v1/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${props.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: type.value, title: title.value, description: description.value,
      priority: priority.value, reporter: props.reporter || 'anonymous',
      context_data: { url: window.location.href, user_agent: navigator.userAgent },
    }),
  });
  const issue = await res.json();

  if (screenshot.value && issue.reference) {
    const fd = new FormData();
    fd.append('file', screenshot.value);
    await fetch(`${props.apiUrl}/api/v1/issues/${issue.reference}/attachments`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${props.apiKey}` },
      body: fd,
    });
  }

  success.value = true;
  setTimeout(() => {
    isOpen.value = false; success.value = false;
    title.value = ''; description.value = ''; screenshot.value = null;
  }, 2000);
  loading.value = false;
};
</script>
```

**Usage:**

```vue
<BugReportButton api-url="http://localhost:9010" api-key="YOUR_KEY" reporter="user@email.com" />
```

### Vanilla HTML

Drop this snippet before `</body>` in any HTML page:

```html
<div id="bug-report-widget"></div>
<script>
(function() {
  // CONFIGURE THESE
  const BUGS_API_URL = 'http://localhost:9010';
  const API_KEY = 'YOUR_PROJECT_API_KEY';
  const REPORTER = 'anonymous';

  const style = document.createElement('style');
  style.textContent = `
    #bug-btn { position:fixed; bottom:20px; right:20px; background:#dc2626; color:white;
      border:none; border-radius:50%; width:56px; height:56px; cursor:pointer;
      box-shadow:0 4px 12px rgba(0,0,0,.3); font-size:14px; font-weight:bold; z-index:9999; }
    #bug-modal { position:fixed; bottom:20px; right:20px; background:white; border-radius:12px;
      box-shadow:0 8px 32px rgba(0,0,0,.2); padding:20px; width:360px; z-index:10000; display:none; }
    #bug-modal.open { display:block; }
    #bug-modal input, #bug-modal select, #bug-modal textarea {
      width:100%; padding:8px; margin-bottom:12px; box-sizing:border-box; }
    #bug-modal .submit { width:100%; padding:12px; background:#dc2626; color:white;
      border:none; border-radius:6px; cursor:pointer; }
    #bug-modal .header { display:flex; justify-content:space-between; margin-bottom:16px; }
    #bug-modal .close { background:none; border:none; cursor:pointer; font-size:18px; }
  `;
  document.head.appendChild(style);

  document.getElementById('bug-report-widget').innerHTML = `
    <button id="bug-btn">Bug</button>
    <div id="bug-modal">
      <div class="header">
        <h3 style="margin:0">Report a problem</h3>
        <button class="close" onclick="closeBugModal()">X</button>
      </div>
      <select id="bug-type">
        <option value="bug">Bug</option>
        <option value="suggestion">Suggestion</option>
        <option value="feature">Feature request</option>
      </select>
      <input id="bug-title" placeholder="Problem title" />
      <textarea id="bug-desc" placeholder="Description (optional)" rows="4"></textarea>
      <select id="bug-priority">
        <option value="basse">Low</option>
        <option value="normale" selected>Normal</option>
        <option value="haute">High</option>
        <option value="critique">Critical</option>
      </select>
      <button class="submit" onclick="submitBugReport()">Send report</button>
    </div>
  `;

  document.getElementById('bug-btn').onclick = () => {
    document.getElementById('bug-modal').classList.add('open');
    document.getElementById('bug-btn').style.display = 'none';
  };

  window.closeBugModal = () => {
    document.getElementById('bug-modal').classList.remove('open');
    document.getElementById('bug-btn').style.display = 'block';
  };

  window.submitBugReport = async () => {
    const title = document.getElementById('bug-title').value;
    if (!title.trim()) return alert('Title required');

    const res = await fetch(BUGS_API_URL + '/api/v1/issues', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: document.getElementById('bug-type').value,
        title: title,
        description: document.getElementById('bug-desc').value,
        priority: document.getElementById('bug-priority').value,
        reporter: REPORTER,
        context_data: { url: window.location.href, user_agent: navigator.userAgent }
      }),
    });

    if (res.ok) {
      alert('Bug reported!');
      closeBugModal();
      document.getElementById('bug-title').value = '';
      document.getElementById('bug-desc').value = '';
    }
  };
})();
</script>
```

### Button Configuration

| Prop / Variable | Required | Description |
|-----------------|----------|-------------|
| `apiUrl` | Yes | URL of your bugs service (e.g. `http://localhost:9010`) |
| `apiKey` | Yes | Project API key (from project creation) |
| `projectSlug` | No | Project slug (for display/routing) |
| `reporter` | No | Pre-filled reporter name/email (default: `anonymous`) |

### What Gets Captured Automatically

The button automatically sends `context_data` with every report:

```json
{
  "url": "http://myapp.com/dashboard?tab=settings",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
}
```

This helps developers reproduce bugs by knowing exactly where the user was.

### Screenshot Capture

The React and Vue components include screenshot capture via `html2canvas`. When the user clicks "Capture screenshot":

1. `html2canvas` renders the current DOM to a canvas
2. The canvas is converted to a PNG blob
3. After issue creation, the PNG is uploaded as an attachment via `POST /api/v1/issues/{ref}/attachments`
4. The screenshot appears in the issue detail view with auto-generated thumbnail

**Note:** `html2canvas` does not capture cross-origin images, WebGL canvases, or iframes. For those cases, consider using the browser's native `navigator.mediaDevices.getDisplayMedia()` API.

---

## Claude Code Skill Integration

This repo includes a **Claude Code skill** (`/bugs`) that lets Claude manage bugs via natural language.

### What Claude Can Do With This Skill

When you type `/bugs` or mention "bugs" in Claude Code, Claude can:

- **List open bugs:** "Show me all open bugs for my-project"
- **Create a bug:** "Create a high-priority bug: the login page crashes on Safari"
- **Update status:** "Mark BUG-042 as en_cours and assign to Pierre"
- **Add comments:** "Add a comment to BUG-042: Fixed in commit abc123"
- **View details:** "Show me the full history of BUG-042"
- **Check stats:** "How many open bugs do we have?"
- **Add the floating button:** "Add a bug report button to my React app"

### How It Works

```
You: "show me open bugs"
                |
                v
Claude Code loads /bugs skill
                |
                v
Reads SKILL.md -> understands API endpoints + auth
                |
                v
Finds API_KEY in your project's .env or CLAUDE.md
                |
                v
Runs: curl -s "http://localhost:9010/api/v1/issues?status=nouveau,en_cours" \
        -H "Authorization: Bearer $API_KEY" | jq
                |
                v
Formats and displays the results to you
```

### Installing the Skill

```bash
# Copy the skill directory to your Claude Code skills folder
cp -r skill/  ~/.claude/skills/bugs/
```

That's it. Claude Code auto-discovers skills in `~/.claude/skills/`. Next time you type `/bugs`, the skill activates.

### Skill File Structure

```
~/.claude/skills/bugs/
  SKILL.md                      # Main skill definition (loaded by Claude)
  references/
    api-reference.md            # Full API docs (loaded on demand)
    bug-button.md               # Button component code (loaded on demand)
```

### Configuring the Skill for Your Instance

Edit `~/.claude/skills/bugs/SKILL.md` and update the API Base URL to point to your instance:

```markdown
**API Base URL:** `http://your-server:9010`
```

Or better: set `BUGS_SERVICE_URL` and `BUGS_SERVICE_API_KEY` in your project's `.env` file. Claude will read them from there.

### Skill Metadata

The skill is defined by YAML frontmatter in `SKILL.md`:

```yaml
---
name: bugs                    # Skill identifier (used for /bugs command)
description: Bug and ...      # Trigger description (Claude reads this to decide when to activate)
allowed-tools: Read, Grep, Glob, Bash, Write, Edit   # Tools the skill can use
---
```

**How triggering works:** Claude reads only the `description` field to decide if the skill is relevant to your request. Keywords like "bugs", "bug report", "signaler un bug" in the description tell Claude when to activate the skill.

---

## Python Client

A Python HTTP client is included for server-side integration (Flask, Django, FastAPI, etc.):

```python
from clients.python.bugs_client import BugsClient

client = BugsClient(
    base_url="http://localhost:9010",
    api_key="YOUR_PROJECT_API_KEY"
)

# List open bugs
issues, error = client.list_issues(status="nouveau,en_cours")

# Create a bug
issue, error = client.create_issue({
    "type": "bug",
    "title": "Payment fails on checkout",
    "priority": "critique",
    "reporter": "backend-service"
})

# Update status
result, error = client.update_status(
    "BUG-001",
    status="en_cours",
    assignee="Pierre",
    comment="Investigating"
)

# Upload a screenshot
with open("screenshot.png", "rb") as f:
    attachment, error = client.upload_attachment("BUG-001", f)

# Get stats
stats, error = client.get_stats()
```

All methods return `(data, None)` on success or `(None, error_string)` on failure.

### Flask Integration Example

```python
# config.py
BUGS_SERVICE_URL = "http://localhost:9010"
BUGS_SERVICE_API_KEY = "YOUR_PROJECT_API_KEY"

# routes.py
from bugs_client import BugsClient

@app.route("/api/report-bug", methods=["POST"])
def report_bug():
    client = BugsClient(
        app.config["BUGS_SERVICE_URL"],
        app.config["BUGS_SERVICE_API_KEY"]
    )
    data = request.json
    issue, error = client.create_issue({
        "type": "bug",
        "title": data["title"],
        "description": data.get("description", ""),
        "priority": data.get("priority", "normale"),
        "reporter": current_user.email,
        "context_data": {
            "url": data.get("url"),
            "user_agent": request.headers.get("User-Agent"),
        }
    })
    if error:
        return jsonify({"error": error}), 500
    return jsonify(issue), 201
```

---

## API Reference

### Authentication

All endpoints (except `/health`) require authentication:

| Method | Header | Access Level |
|--------|--------|--------------|
| Bearer token (API key) | `Authorization: Bearer {API_KEY}` | Project-scoped |
| Bearer token (master key) | `Authorization: Bearer {ADMIN_MASTER_KEY}` | Admin (all projects) |
| Basic auth | `Authorization: Basic {base64(user:pass)}` | User-scoped |

### Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | None | Health check |
| **Admin** | | | |
| `POST` | `/api/v1/admin/projects` | Admin | Create project (returns API key) |
| `GET` | `/api/v1/admin/projects` | Admin | List all projects |
| `PATCH` | `/api/v1/admin/projects/{id}` | Admin | Update project (rename, enable/disable) |
| `POST` | `/api/v1/admin/projects/{id}/regenerate-key` | Admin | Regenerate API key |
| `POST` | `/api/v1/admin/users` | Admin | Create user |
| `GET` | `/api/v1/admin/users` | Admin | List users |
| `DELETE` | `/api/v1/admin/users/{id}` | Admin | Delete user |
| **Issues** | | | |
| `POST` | `/api/v1/issues` | Project key | Create issue |
| `GET` | `/api/v1/issues` | Any | List issues (filters: status, type, priority, assignee) |
| `GET` | `/api/v1/issues/{reference}` | Any | Get issue + comments + attachments + history |
| `PUT` | `/api/v1/issues/{reference}` | Any | Update issue fields |
| `PATCH` | `/api/v1/issues/{reference}/status` | Any | Change status (+ optional assignee/comment) |
| `DELETE` | `/api/v1/issues/{reference}` | Any | Delete issue |
| **Comments** | | | |
| `POST` | `/api/v1/issues/{reference}/comments` | Any | Add comment |
| `GET` | `/api/v1/issues/{reference}/comments` | Any | List comments |
| **Attachments** | | | |
| `POST` | `/api/v1/issues/{reference}/attachments` | Any | Upload file (PNG, JPEG, GIF, WebP, MP4, WebM, PDF — max 10MB) |
| `GET` | `/api/v1/attachments/{id}` | None | Download file |
| `GET` | `/api/v1/attachments/{id}/thumbnail` | None | Get image thumbnail (300x300) |
| **Stats** | | | |
| `GET` | `/api/v1/stats` | Any | Counts by status/type/priority |

### Issue Types & Statuses

**Types:** `bug`, `suggestion`, `feature`, `improvement`

**Priorities:** `basse`, `normale`, `haute`, `critique`

**Status workflow:**
```
nouveau ──> en_cours ──> a_approuver ──> termine
                    └──> rejete
```

### Response Format

**List issues:**
```json
{
  "data": [
    {
      "id": 1,
      "reference": "BUG-001",
      "type": "bug",
      "title": "Login button broken",
      "status": "nouveau",
      "priority": "haute",
      "reporter": "Pierre",
      "created_at": "2026-01-15T10:30:00",
      "comments_count": 2,
      "attachments_count": 1
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 42, "pages": 3 }
}
```

**Issue detail:**
```json
{
  "issue": { ... },
  "comments": [
    { "id": 1, "author": "Pierre", "content": "Investigating...", "type": "comment", "created_at": "..." }
  ],
  "attachments": [
    { "id": 1, "filename": "screenshot.png", "mime_type": "image/png", "size_bytes": 45231 }
  ],
  "history": [
    { "field": "status", "old": "nouveau", "new": "en_cours", "by": "Pierre", "at": "..." }
  ]
}
```

### Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid data or duplicate slug |
| 401 | Invalid or missing API key |
| 403 | Admin access required |
| 404 | Issue/project/attachment not found |
| 422 | Validation error |

---

## Architecture

```
docker compose
├── bugs-backend (FastAPI, port 8000 internal)
│   ├── main.py              # API endpoints + auth + schemas
│   ├── models.py            # SQLAlchemy ORM models
│   ├── database.py          # SQLite connection
│   └── services/
│       └── attachment_service.py  # File upload + thumbnails
│
├── bugs-frontend (nginx, port 9010 external)
│   ├── nginx.conf           # Reverse proxy + security headers
│   └── static/              # SPA dashboard (pre-built)
│
└── Volumes
    ├── data/db/             # SQLite database (bugs.db)
    ├── data/uploads/        # File attachments
    └── data/backups/        # Manual backups
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Admin/operator accounts |
| `projects` | Projects with API keys (hashed) and webhook URLs |
| `issues` | Bugs/suggestions with full metadata |
| `comments` | Issue comments (including status change logs) |
| `attachments` | File metadata + storage paths |
| `issue_history` | Audit trail of every field change |

### Security

- API keys are hashed with SHA256 (plaintext never stored)
- Passwords hashed with SHA256 + random salt
- nginx security headers: X-Frame-Options, X-Content-Type-Options, CSP, etc.
- CORS enabled (configurable)
- Max upload size: 10MB (backend) / 15MB (nginx)

### Default Admin User

On first startup (empty database), a default admin is created:
- Username: `admin`
- Password: `admin123`

**Change this immediately** via the admin API or by setting environment variables.

---

## Development

### Run without Docker

```bash
pip install -r requirements.txt
export ADMIN_MASTER_KEY=$(openssl rand -hex 32)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run tests

```bash
pip install -r requirements-dev.txt
pytest test_bugs.py -v
```

### Lint

```bash
pip install ruff
ruff check . --select=E,F,W --ignore=E501
```

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on push/PR to main:

1. **Lint** — ruff check
2. **Tests** — pytest
3. **Notify** — Discord webhook (optional, configure `DISCORD_WEBHOOK_URL` secret)

### Auto-deploy (optional)

A cron-based deploy script is included in `scripts/auto-deploy-tag.sh`. It watches for new git tags and rebuilds containers automatically.

---

## License

MIT
