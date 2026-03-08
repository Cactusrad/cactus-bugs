"""Attachment service for file uploads."""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from PIL import Image

from models import Issue, Attachment

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
THUMBNAIL_SIZE = (300, 300)

ALLOWED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'video/mp4',
    'video/webm',
    'application/pdf'
}


def get_attachment_path(storage_path: str) -> Path:
    """Get full path for an attachment."""
    return UPLOAD_DIR / storage_path


async def save_attachment(
    file: UploadFile,
    issue: Issue,
    db: Session,
    comment_id: Optional[int] = None
) -> Attachment:
    """Save an uploaded file and create attachment record."""

    # Validate mime type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # Read content
    content = await file.read()

    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(file.filename).suffix.lower() if file.filename else '.bin'
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{issue.reference}_{timestamp}_{unique_id}{ext}"

    # Build storage path: PROJECT_SLUG/YYYY/MM/filename
    project_slug = issue.reference.split('-')[0]
    year_month = datetime.now().strftime("%Y/%m")
    storage_path = f"{project_slug}/{year_month}/{filename}"

    # Create directory if needed
    full_path = UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    full_path.write_bytes(content)

    # Generate thumbnail for images
    thumbnail_path = None
    if file.content_type and file.content_type.startswith('image/'):
        thumbnail_path = generate_thumbnail(full_path, storage_path)

    # Create attachment record
    attachment = Attachment(
        issue_id=issue.id,
        comment_id=comment_id,
        filename=filename,
        original_name=file.filename or filename,
        mime_type=file.content_type or 'application/octet-stream',
        size_bytes=len(content),
        storage_path=storage_path,
        thumbnail_path=thumbnail_path
    )

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


def generate_thumbnail(image_path: Path, storage_path: str) -> Optional[str]:
    """Generate thumbnail for an image."""
    try:
        img = Image.open(image_path)

        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        img.thumbnail(THUMBNAIL_SIZE)

        # Build thumbnail path
        thumb_storage = storage_path.rsplit('.', 1)[0] + '_thumb.jpg'
        thumb_full_path = UPLOAD_DIR / thumb_storage

        img.save(thumb_full_path, 'JPEG', quality=85, optimize=True)

        return thumb_storage
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None
