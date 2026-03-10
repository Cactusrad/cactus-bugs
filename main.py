"""
Bugs Service - Centralized bug/suggestion tracking API.
"""

import os
import secrets
import threading
import ipaddress
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr

from database import get_db, init_db, SessionLocal
from models import (
    Project, Issue, Comment, Attachment, IssueHistory, User,
    IssueType, IssueStatus, Priority, CommentType
)
from services.attachment_service import save_attachment, get_attachment_path, UPLOAD_DIR


# ============ Pydantic Schemas ============

class ProjectCreate(BaseModel):
    name: str
    slug: str
    webhook_url: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    slug: str
    api_key_prefix: str
    webhook_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectWithKey(ProjectResponse):
    api_key: str  # Only returned on creation


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: Optional[bool] = None


class IssueCreate(BaseModel):
    type: IssueType = IssueType.BUG
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.NORMALE
    reporter: Optional[str] = None
    reporter_email: Optional[str] = None
    context_data: Optional[dict] = None


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    assignee: Optional[str] = None


class StatusUpdate(BaseModel):
    status: IssueStatus
    assignee: Optional[str] = None
    comment: Optional[str] = None


class IssueResponse(BaseModel):
    id: int
    reference: str
    type: IssueType
    title: str
    description: Optional[str]
    status: IssueStatus
    priority: Priority
    assignee: Optional[str]
    reporter: Optional[str]
    reporter_email: Optional[str]
    context_data: Optional[dict]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    comments_count: int = 0
    attachments_count: int = 0

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    author: str
    content: str


class CommentResponse(BaseModel):
    id: int
    author: str
    content: str
    type: CommentType
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total: int
    by_status: dict
    by_type: dict
    by_priority: dict


class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Auth Dependencies ============

ADMIN_MASTER_KEY = os.environ.get("ADMIN_MASTER_KEY", "dev_master_key_change_me")
LOCAL_SUBNET = ipaddress.ip_network('192.168.1.0/24')


import base64


def _is_local_network(request: Request) -> bool:
    """Check if request comes from the local subnet."""
    ip_str = request.headers.get('X-Real-IP') or request.headers.get('X-Forwarded-For', request.client.host)
    ip_str = ip_str.split(',')[0].strip()
    try:
        return ipaddress.ip_address(ip_str) in LOCAL_SUBNET
    except ValueError:
        return False


def _parse_basic_auth(auth_header: str, db: Session) -> Optional[User]:
    """Parse Basic auth header and return User if valid."""
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return None

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user and User.verify_password(password, user.password_hash):
        return user
    return None


def get_current_project(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[Project]:
    """Verify auth and return project (or None for admin/user auth)."""
    auth = request.headers.get("Authorization", "")

    # Local network = admin-level access (no auth needed)
    if not auth and _is_local_network(request):
        return None

    # Basic auth — user/password
    if auth.startswith("Basic "):
        user = _parse_basic_auth(auth, db)
        if user:
            return None  # Authenticated user = admin-level access
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Bearer auth — API key
    if auth.startswith("Bearer "):
        api_key = auth[7:]

        # Check admin master key
        if api_key == ADMIN_MASTER_KEY:
            return None  # Admin access

        # Find project by API key
        projects = db.query(Project).filter(Project.is_active == True).all()
        for project in projects:
            if Project.verify_api_key(api_key, project.api_key_hash):
                return project

        raise HTTPException(status_code=401, detail="Invalid API key")

    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


def _get_authenticated_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Return the authenticated User if Basic auth, else None."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        return _parse_basic_auth(auth, db)
    return None


def require_admin(request: Request, db: Session = Depends(get_db)):
    """Require admin access (master key or admin user)."""
    # Local network = admin access
    if _is_local_network(request):
        return

    auth = request.headers.get("Authorization", "")

    if auth.startswith("Basic "):
        user = _parse_basic_auth(auth, db)
        if user and user.is_admin:
            return
        raise HTTPException(status_code=403, detail="Admin access required")

    if auth.startswith("Bearer "):
        api_key = auth[7:]
        if api_key == ADMIN_MASTER_KEY:
            return
        raise HTTPException(status_code=403, detail="Admin access required")

    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


def require_project(project: Optional[Project] = Depends(get_current_project)) -> Project:
    """Require a valid project (not admin)."""
    if project is None:
        raise HTTPException(status_code=400, detail="Project API key required")
    return project


# ============ Lifespan ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Create default admin user if no users exist
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                password_hash=User.hash_password("admin123"),
                is_admin=True,
                is_active=True
            )
            db.add(admin)
            db.commit()
            print("Created default admin user (admin/admin123)")
    finally:
        db.close()
    yield


# ============ App Setup ============

app = FastAPI(
    title="Bugs Service API",
    description="Centralized bug and suggestion tracking",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Webhook Helper ============

def send_webhook(webhook_url: str, payload: dict):
    """Send webhook notification in background thread."""
    def _send():
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(webhook_url, json=payload)
        except Exception as e:
            print(f"Webhook failed: {e}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


# ============ Health Check ============

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "bugs-api"}


# ============ Admin: Projects ============

@app.post("/api/v1/admin/projects", response_model=ProjectWithKey)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """Create a new project (admin only)."""
    # Check slug uniqueness
    existing = db.query(Project).filter(Project.slug == data.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    # Generate API key
    api_key, key_hash, prefix = Project.generate_api_key(data.slug)

    project = Project(
        name=data.name,
        slug=data.slug,
        api_key_hash=key_hash,
        api_key_prefix=prefix,
        webhook_url=data.webhook_url
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Return with plain API key (only time it's shown)
    return ProjectWithKey(
        id=project.id,
        name=project.name,
        slug=project.slug,
        api_key_prefix=project.api_key_prefix,
        api_key=api_key,
        webhook_url=project.webhook_url,
        is_active=project.is_active,
        created_at=project.created_at
    )


@app.get("/api/v1/admin/projects", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """List all projects (admin only)."""
    return db.query(Project).all()


@app.post("/api/v1/admin/projects/{project_id}/regenerate-key")
def regenerate_api_key(
    project_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """Regenerate API key for a project (admin only)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    api_key, key_hash, prefix = Project.generate_api_key(project.slug)
    project.api_key_hash = key_hash
    project.api_key_prefix = prefix
    db.commit()

    return {"api_key": api_key, "message": "API key regenerated"}


@app.patch("/api/v1/admin/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """Update a project (admin only). Allows renaming projects."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check slug uniqueness if changing
    if data.slug and data.slug != project.slug:
        existing = db.query(Project).filter(Project.slug == data.slug).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug already exists")
        project.slug = data.slug

    if data.name is not None:
        project.name = data.name
    if data.webhook_url is not None:
        project.webhook_url = data.webhook_url
    if data.is_active is not None:
        project.is_active = data.is_active

    db.commit()
    db.refresh(project)
    return project


# ============ Admin: Users ============

@app.post("/api/v1/admin/users", response_model=UserResponse)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """Create a new user (admin only)."""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=User.hash_password(data.password),
        is_admin=data.is_admin,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/v1/admin/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """List all users (admin only)."""
    return db.query(User).all()


@app.delete("/api/v1/admin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": f"User '{user.username}' deleted"}


# ============ Issues ============

TYPE_PREFIXES = {
    "bug": "BUG",
    "suggestion": "SUG",
    "feature": "FEAT",
    "improvement": "IMP",
}

def generate_reference(project: Project, issue_type: str, db: Session) -> str:
    """Generate next reference based on issue type (e.g., BUG-001, SUG-002)."""
    project.issue_counter = (project.issue_counter or 0) + 1
    db.flush()
    prefix = TYPE_PREFIXES.get(issue_type, "BUG")
    return f"{prefix}-{project.issue_counter:03d}"


@app.post("/api/v1/issues", response_model=IssueResponse)
def create_issue(
    data: IssueCreate,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project)
):
    """Create a new issue."""
    reference = generate_reference(project, data.type, db)

    issue = Issue(
        project_id=project.id,
        reference=reference,
        type=data.type,
        title=data.title,
        description=data.description,
        priority=data.priority,
        reporter=data.reporter,
        reporter_email=data.reporter_email,
        context_data=data.context_data or {}
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    # Send webhook if configured
    if project.webhook_url:
        send_webhook(project.webhook_url, {
            "event": "issue_created",
            "project": {
                "id": project.id,
                "name": project.name,
                "slug": project.slug
            },
            "issue": {
                "reference": issue.reference,
                "type": issue.type.value,
                "title": issue.title,
                "description": issue.description,
                "priority": issue.priority.value,
                "status": issue.status.value,
                "reporter": issue.reporter,
                "context_data": issue.context_data,
                "created_at": issue.created_at.isoformat()
            }
        })

    return IssueResponse(
        **issue.__dict__,
        comments_count=0,
        attachments_count=0
    )


@app.get("/api/v1/issues", response_model=dict)
def list_issues(
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    type: Optional[IssueType] = None,
    priority: Optional[Priority] = None,
    assignee: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """List issues with filters."""
    query = db.query(Issue)

    # Filter by project if not admin
    if project:
        query = query.filter(Issue.project_id == project.id)

    # Apply filters
    if status:
        statuses = [IssueStatus(s.strip()) for s in status.split(",")]
        query = query.filter(Issue.status.in_(statuses))
    if type:
        query = query.filter(Issue.type == type)
    if priority:
        query = query.filter(Issue.priority == priority)
    if assignee:
        query = query.filter(Issue.assignee == assignee)

    # Count total
    total = query.count()

    # Paginate
    issues = query.order_by(Issue.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    # Add counts
    results = []
    for issue in issues:
        results.append(IssueResponse(
            **issue.__dict__,
            comments_count=len(issue.comments),
            attachments_count=len(issue.attachments)
        ))

    return {
        "data": results,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@app.get("/api/v1/issues/{reference}", response_model=dict)
def get_issue(
    reference: str,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Get issue details with comments and attachments."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    return {
        "issue": IssueResponse(
            **issue.__dict__,
            comments_count=len(issue.comments),
            attachments_count=len(issue.attachments)
        ),
        "comments": [CommentResponse.model_validate(c) for c in issue.comments],
        "attachments": [AttachmentResponse.model_validate(a) for a in issue.attachments],
        "history": [
            {
                "field": h.field_name,
                "old": h.old_value,
                "new": h.new_value,
                "by": h.changed_by,
                "at": h.changed_at
            }
            for h in issue.history
        ]
    }


@app.put("/api/v1/issues/{reference}", response_model=IssueResponse)
def update_issue(
    reference: str,
    data: IssueUpdate,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Update issue details."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            old_value = getattr(issue, field)
            setattr(issue, field, value)

            # Record history
            if old_value != value:
                history = IssueHistory(
                    issue_id=issue.id,
                    field_name=field,
                    old_value=str(old_value) if old_value else None,
                    new_value=str(value)
                )
                db.add(history)

    db.commit()
    db.refresh(issue)

    return IssueResponse(
        **issue.__dict__,
        comments_count=len(issue.comments),
        attachments_count=len(issue.attachments)
    )


@app.patch("/api/v1/issues/{reference}/status", response_model=IssueResponse)
def update_issue_status(
    reference: str,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Update issue status."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    old_status = issue.status

    # Update status
    issue.status = data.status

    if data.assignee:
        issue.assignee = data.assignee

    if data.status == IssueStatus.TERMINE:
        issue.resolved_at = datetime.utcnow()

    # Record history
    history = IssueHistory(
        issue_id=issue.id,
        field_name="status",
        old_value=old_status.value,
        new_value=data.status.value,
        changed_by=data.assignee
    )
    db.add(history)

    # Add system comment if provided
    if data.comment:
        comment = Comment(
            issue_id=issue.id,
            author=data.assignee or "System",
            content=data.comment,
            type=CommentType.STATUS_CHANGE
        )
        db.add(comment)

    db.commit()
    db.refresh(issue)

    return IssueResponse(
        **issue.__dict__,
        comments_count=len(issue.comments),
        attachments_count=len(issue.attachments)
    )


@app.delete("/api/v1/issues/{reference}")
def delete_issue(
    reference: str,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Delete an issue."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    db.delete(issue)
    db.commit()

    return {"message": "Issue deleted"}


# ============ Comments ============

@app.post("/api/v1/issues/{reference}/comments", response_model=CommentResponse)
def add_comment(
    reference: str,
    data: CommentCreate,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Add a comment to an issue."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    comment = Comment(
        issue_id=issue.id,
        author=data.author,
        content=data.content,
        type=CommentType.COMMENT
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment


@app.get("/api/v1/issues/{reference}/comments", response_model=List[CommentResponse])
def list_comments(
    reference: str,
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """List comments for an issue."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    return issue.comments


# ============ Attachments ============

@app.post("/api/v1/issues/{reference}/attachments", response_model=AttachmentResponse)
async def upload_attachment(
    reference: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Upload an attachment to an issue."""
    query = db.query(Issue).filter(Issue.reference == reference.upper())

    if project:
        query = query.filter(Issue.project_id == project.id)

    issue = query.first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    attachment = await save_attachment(file, issue, db)
    return attachment


@app.get("/api/v1/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db)
):
    """Download an attachment."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = get_attachment_path(attachment.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=attachment.original_name,
        media_type=attachment.mime_type
    )


@app.get("/api/v1/attachments/{attachment_id}/thumbnail")
def get_thumbnail(
    attachment_id: int,
    db: Session = Depends(get_db)
):
    """Get thumbnail for an image attachment."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not attachment.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail available")

    file_path = get_attachment_path(attachment.thumbnail_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk")

    return FileResponse(path=str(file_path), media_type="image/jpeg")


# ============ Statistics ============

@app.get("/api/v1/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    project: Optional[Project] = Depends(get_current_project)
):
    """Get statistics for issues."""
    query = db.query(Issue)

    if project:
        query = query.filter(Issue.project_id == project.id)

    total = query.count()

    # By status
    status_counts = db.query(
        Issue.status, func.count(Issue.id)
    ).group_by(Issue.status)
    if project:
        status_counts = status_counts.filter(Issue.project_id == project.id)
    by_status = {s.value: c for s, c in status_counts.all()}

    # By type
    type_counts = db.query(
        Issue.type, func.count(Issue.id)
    ).group_by(Issue.type)
    if project:
        type_counts = type_counts.filter(Issue.project_id == project.id)
    by_type = {t.value: c for t, c in type_counts.all()}

    # By priority
    priority_counts = db.query(
        Issue.priority, func.count(Issue.id)
    ).group_by(Issue.priority)
    if project:
        priority_counts = priority_counts.filter(Issue.project_id == project.id)
    by_priority = {p.value: c for p, c in priority_counts.all()}

    return StatsResponse(
        total=total,
        by_status=by_status,
        by_type=by_type,
        by_priority=by_priority
    )


# ============ Static Files (Frontend) ============

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str = ""):
        """Serve the SPA for all non-API routes."""
        # Don't serve index.html for API or health routes
        if path.startswith("api/") or path == "health" or path == "docs" or path == "openapi.json" or path == "redoc":
            raise HTTPException(status_code=404, detail="Not found")

        # Check if it's a static file request
        static_path = STATIC_DIR / path
        if static_path.exists() and static_path.is_file():
            return FileResponse(static_path)

        # Otherwise serve index.html for SPA routing
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        raise HTTPException(status_code=404, detail="Not found")
