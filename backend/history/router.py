"""
History service + router — store, retrieve, and delete file history per user.
All endpoints require authentication via Bearer token.
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.router import get_current_user
from db.database import get_db
from db.models import FileHistory, User

MAX_HISTORY_PER_USER = 50  # hard cap; UI shows last 10


# ─── Schemas ─────────────────────────────────────────────────────────────────

class HistoryEntryOut(BaseModel):
    id: str
    filename: str
    original_format: str
    row_count: int | None
    column_count: int | None
    quality_score_before: int | None
    quality_score_after: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryEntryDetail(HistoryEntryOut):
    file_content: str | None
    report_json: str | None


class SaveHistoryRequest(BaseModel):
    filename: str
    original_format: str
    row_count: int | None = None
    column_count: int | None = None
    quality_score_before: int | None = None
    quality_score_after: int | None = None
    file_content: str | None = None      # raw CSV/TSV/JSON text or base64 XLSX
    report_json: str | None = None       # serialized QualityReport dict


# ─── Service ─────────────────────────────────────────────────────────────────

async def save_history_entry(db: AsyncSession, user_id: str, data: SaveHistoryRequest) -> FileHistory:
    entry = FileHistory(
        user_id=user_id,
        filename=data.filename,
        original_format=data.original_format,
        row_count=data.row_count,
        column_count=data.column_count,
        quality_score_before=data.quality_score_before,
        quality_score_after=data.quality_score_after,
        file_content=data.file_content,
        report_json=data.report_json,
    )
    db.add(entry)
    await db.flush()

    # Enforce per-user cap — remove oldest entries beyond limit
    result = await db.execute(
        select(FileHistory.id)
        .where(FileHistory.user_id == user_id)
        .order_by(FileHistory.created_at.desc())
        .offset(MAX_HISTORY_PER_USER)
    )
    old_ids = result.scalars().all()
    if old_ids:
        await db.execute(delete(FileHistory).where(FileHistory.id.in_(old_ids)))

    return entry


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryEntryOut])
async def list_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's most recent history entries (metadata only, no file content)."""
    limit = min(limit, 50)
    result = await db.execute(
        select(FileHistory)
        .where(FileHistory.user_id == current_user.id)
        .order_by(FileHistory.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{entry_id}", response_model=HistoryEntryDetail)
async def get_history_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a single history entry including file content and report."""
    result = await db.execute(
        select(FileHistory).where(
            FileHistory.id == entry_id,
            FileHistory.user_id == current_user.id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


@router.post("", response_model=HistoryEntryOut, status_code=status.HTTP_201_CREATED)
async def create_history_entry(
    body: SaveHistoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await save_history_entry(db, current_user.id, body)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FileHistory).where(
            FileHistory.id == entry_id,
            FileHistory.user_id == current_user.id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    await db.delete(entry)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all history for the current user."""
    await db.execute(delete(FileHistory).where(FileHistory.user_id == current_user.id))
