"""Database models for bugs service."""

import secrets
import hashlib
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum

from database import Base


class IssueType(str, enum.Enum):
    BUG = "bug"
    SUGGESTION = "suggestion"
    FEATURE = "feature"
    IMPROVEMENT = "improvement"


class IssueStatus(str, enum.Enum):
    NOUVEAU = "nouveau"
    EN_COURS = "en_cours"
    A_APPROUVER = "a_approuver"
    TERMINE = "termine"
    REJETE = "rejete"


class Priority(str, enum.Enum):
    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"
    CRITIQUE = "critique"


class CommentType(str, enum.Enum):
    COMMENT = "comment"
    STATUS_CHANGE = "status_change"
    SYSTEM = "system"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)  # salt:sha256hash
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with SHA256 + random salt."""
        salt = secrets.token_hex(16)
        h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{h}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored salt:hash."""
        if ":" not in stored_hash:
            return False
        salt, h = stored_hash.split(":", 1)
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(check, h)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(64), unique=True, nullable=False)
    api_key_prefix = Column(String(10), nullable=False)  # For identification
    webhook_url = Column(String(500), nullable=True)
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")

    # Counter for reference generation
    issue_counter = Column(Integer, default=0)

    @staticmethod
    def generate_api_key(slug: str) -> tuple:
        """Generate API key and return (plain_key, hash)."""
        random_part = secrets.token_hex(24)
        prefix = slug[:3].upper()
        api_key = f"{prefix}_{random_part}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key, key_hash, prefix

    @staticmethod
    def verify_api_key(api_key: str, stored_hash: str) -> bool:
        """Verify API key against stored hash."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return secrets.compare_digest(key_hash, stored_hash)


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # Reference like RAD-001
    reference = Column(String(20), unique=True, nullable=False, index=True)

    # Content
    type = Column(Enum(IssueType), nullable=False, default=IssueType.BUG)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Workflow
    status = Column(Enum(IssueStatus), default=IssueStatus.NOUVEAU, index=True)
    priority = Column(Enum(Priority), default=Priority.NORMALE)

    # Context data (URL, user agent, console logs, etc.)
    context_data = Column(JSON, default=dict)

    # People
    assignee = Column(String(100), nullable=True)
    reporter = Column(String(100), nullable=True)
    reporter_email = Column(String(200), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="issues")
    comments = relationship("Comment", back_populates="issue", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="issue", cascade="all, delete-orphan")
    history = relationship("IssueHistory", back_populates="issue", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)

    author = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(Enum(CommentType), default=CommentType.COMMENT)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    issue = relationship("Issue", back_populates="comments")
    attachments = relationship("Attachment", back_populates="comment", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)

    storage_path = Column(String(500), nullable=False)
    thumbnail_path = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    issue = relationship("Issue", back_populates="attachments")
    comment = relationship("Comment", back_populates="attachments")


class IssueHistory(Base):
    __tablename__ = "issue_history"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)

    field_name = Column(String(50), nullable=False)
    old_value = Column(String(500), nullable=True)
    new_value = Column(String(500), nullable=True)

    changed_by = Column(String(100), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    issue = relationship("Issue", back_populates="history")
