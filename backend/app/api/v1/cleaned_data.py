"""API endpoints for browsing cleaned data files."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/data", tags=["data"])

# Root directory for cleaned data
CLEANED_DIR = Path(__file__).resolve().parents[3] / "data" / "cleaned"

PLATFORM_NAMES: dict[str, str] = {
    "dy": "Douyin",
    "xhs": "Xiaohongshu",
    "bili": "Bilibili",
    "wb": "Weibo",
}


# ── Response Models ───────────────────────────────────────────────

class CleanedFileInfo(BaseModel):
    filename: str
    platform: str
    platform_label: str
    keyword: str
    task_id: Optional[int] = None
    cleaned_count: Optional[int] = None
    generated_at: Optional[str] = None
    file_size: int  # bytes


class CleanedFileListResponse(BaseModel):
    platforms: list[dict]  # [{value, label, count}]
    files: list[CleanedFileInfo]
    total: int


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/cleaned/files", response_model=CleanedFileListResponse)
async def list_cleaned_files(
    platform: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """List all cleaned JSON files, optionally filtered by platform/keyword."""
    if not CLEANED_DIR.exists():
        return CleanedFileListResponse(platforms=[], files=[], total=0)

    # Discover available platforms
    platform_dirs = sorted(
        d.name for d in CLEANED_DIR.iterdir() if d.is_dir()
    )
    platforms_info: list[dict] = []
    for p in platform_dirs:
        count = len(list((CLEANED_DIR / p).glob("*.json")))
        platforms_info.append({
            "value": p,
            "label": PLATFORM_NAMES.get(p, p),
            "count": count,
        })

    # Collect files
    files: list[CleanedFileInfo] = []
    search_dirs = [platform] if platform else platform_dirs

    for p in search_dirs:
        p_dir = CLEANED_DIR / p
        if not p_dir.is_dir():
            continue
        for fp in sorted(p_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            # Try to parse metadata for richer info
            keyword_val = ""
            task_id_val = None
            cleaned_count_val = None
            generated_at_val = None

            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                keyword_val = meta.get("keyword", "")
                task_id_val = meta.get("task_id")
                cleaned_count_val = meta.get("cleaned_count")
                generated_at_val = meta.get("generated_at")
            except Exception:
                # Fallback: extract keyword from filename
                keyword_val = fp.stem.split("_task")[0] if "_task" in fp.stem else fp.stem

            # Apply keyword filter
            if keyword and keyword.lower() not in keyword_val.lower():
                continue

            files.append(CleanedFileInfo(
                filename=fp.name,
                platform=p,
                platform_label=PLATFORM_NAMES.get(p, p),
                keyword=keyword_val,
                task_id=task_id_val,
                cleaned_count=cleaned_count_val,
                generated_at=generated_at_val,
                file_size=fp.stat().st_size,
            ))

    return CleanedFileListResponse(
        platforms=platforms_info,
        files=files,
        total=len(files),
    )


@router.get("/cleaned/content")
async def get_cleaned_file_content(
    platform: str,
    filename: str,
):
    """Read and return the content of a specific cleaned JSON file."""
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    if ".." in platform or "/" in platform or "\\" in platform:
        raise HTTPException(400, "Invalid platform")

    filepath = CLEANED_DIR / platform / filename
    if not filepath.exists():
        raise HTTPException(404, f"File not found: {platform}/{filename}")

    # Verify the resolved path is still under CLEANED_DIR
    try:
        filepath.resolve().relative_to(CLEANED_DIR.resolve())
    except ValueError:
        raise HTTPException(403, "Access denied")

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(500, "Failed to parse JSON file")
    except Exception as e:
        raise HTTPException(500, f"Failed to read file: {e}")

    return data
