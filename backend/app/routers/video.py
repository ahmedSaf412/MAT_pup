import os
import re
import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/video", tags=["video"])

# ── Paths ─────────────────────────────────────────────────────────────────────
_THIS_FILE    = Path(__file__).resolve()
ANIMATION_DIR = str(_THIS_FILE.parent.parent / "data" / "Animation")

# ── Move → folder mapping ─────────────────────────────────────────────────────
_MOVE_FOLDERS = {
    "gedanbarai": "GedanBarai",
    "maegeri":    "Maegeri",
    "gyakudzuki": "Gyakudzuki",
    "gyakuzuki":  "Gyakudzuki",   # alias: gyaku_zuki → strip _ → "gyakuzuki"
}


def _resolve_folder(move_name: str) -> str | None:
    key = move_name.lower().replace("_", "").replace("-", "").replace(" ", "")
    return _MOVE_FOLDERS.get(key)


def _find_file(folder: str, keyword: str, exts: list[str] | None = None) -> str | None:
    """Return first file in folder whose name contains keyword (case-insensitive)."""
    folder_path = os.path.join(ANIMATION_DIR, folder)
    if not os.path.isdir(folder_path):
        return None
    for fname in sorted(os.listdir(folder_path)):
        flo = fname.lower()
        if keyword.lower() in flo:
            if exts is None or any(flo.endswith(e) for e in exts):
                full = os.path.join(folder_path, fname)
                if os.path.isfile(full):
                    return full
    return None


# ── Info ─────────────────────────────────────────────────────────────────────
@router.get("/info")
async def info():
    result: dict = {}
    seen: set = set()
    for _k, folder in _MOVE_FOLDERS.items():
        if folder in seen:
            continue
        seen.add(folder)
        fp = os.path.join(ANIMATION_DIR, folder)
        if os.path.isdir(fp):
            result[folder] = sorted(
                f for f in os.listdir(fp) if os.path.isfile(os.path.join(fp, f))
            )
    return {"animation_dir": ANIMATION_DIR, "moves": result}


# ── Landmarks (MUST be before the two-segment wildcard) ──────────────────────
@router.get("/{move_name}/landmarks")
async def get_landmarks(move_name: str, view: str = "front"):
    """Return pre-extracted MediaPipe landmark JSON for the given move + view."""
    folder = _resolve_folder(move_name)
    if not folder:
        raise HTTPException(404, f"Unknown move '{move_name}'")

    # Find JSON for requested view, fall back to the other view
    file_path = _find_file(folder, view, exts=[".json"])
    if not file_path:
        other = "side" if view == "front" else "front"
        file_path = _find_file(folder, other, exts=[".json"])

    if not file_path:
        raise HTTPException(404, f"No landmark JSON found for '{move_name}' ({view} view)")

    with open(file_path, "r") as f:
        return json.load(f)


# ── Video streaming with Range request support ────────────────────────────────
@router.get("/{move_name}/{view}")
async def stream_video(move_name: str, view: str, request: Request):
    """
    Stream reference video with proper HTTP Range support so browsers can
    buffer and seek the <video> element.
    """
    folder = _resolve_folder(move_name)
    if not folder:
        raise HTTPException(404, f"Unknown move '{move_name}'")

    file_path = _find_file(folder, view, exts=[".mov", ".mp4", ".webm"])
    if not file_path:
        raise HTTPException(404, f"No '{view}' video for '{move_name}' in {folder}/")

    file_size = os.path.getsize(file_path)
    mime, _   = mimetypes.guess_type(file_path)
    mime      = mime or "video/quicktime"

    def iter_bytes(start: int, end: int):
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = (end - start) + 1
            while remaining > 0:
                chunk = f.read(min(65_536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    range_header = request.headers.get("range", "")
    match = re.search(r"bytes=(\d+)-(\d*)", range_header)

    if match:
        start = int(match.group(1))
        end   = int(match.group(2)) if match.group(2) else file_size - 1
        end   = min(end, file_size - 1)
        headers = {
            "Content-Range":  f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges":  "bytes",
            "Content-Length": str((end - start) + 1),
            "Content-Type":   mime,
        }
        return StreamingResponse(iter_bytes(start, end), status_code=206, headers=headers)

    # First request (no Range header) — send full file but advertise range support
    headers = {
        "Accept-Ranges":  "bytes",
        "Content-Length": str(file_size),
        "Content-Type":   mime,
    }
    return StreamingResponse(iter_bytes(0, file_size - 1), status_code=200, headers=headers)