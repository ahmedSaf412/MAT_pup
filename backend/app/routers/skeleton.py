# backend/app/routers/skeleton.py
"""
GET /api/moves/{move_id}/skeleton
──────────────────────────────────
Returns the 3D landmark frames for a specific move's reference sequence.
The frontend uses this to render the animated reference skeleton side-by-side
with the trainee's captured skeleton after classification.

Data priority:
  1. MADS P3 reference (mads_reference_sequences.json) — expert quality
  2. Exampler sequences (exampler_sequences.json) — YouTube fallback

Response shape:
{
  "move_id":     "mae_geri",
  "fps":         15.0,
  "n_frames":    30,
  "angle_names": ["right_elbow", "left_elbow", ...],
  "angles":      [[...], ...],   // (30, 9) — for skeleton reconstruction
  "source":      "mads_p3"    // "mads_p3" | "exampler"
}

GET /api/moves/{move_id}/reference_stats
──────────────────────────────────────────
Returns MADS per-joint mean/std/tight/loose bands from the DB
(or directly from P3_mp_reference.json as fallback).
Used by the frontend to draw the per-joint error bars.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/moves", tags=["skeleton"])

DATA_DIR       = Path(__file__).resolve().parent.parent / "rag" / "data"
ANDREW_PATH    = DATA_DIR / "mads_reference_sequences.json"
EXAMPLER_PATH  = DATA_DIR / "exampler_sequences.json"

ANDREW_REF_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "MADS_correction" / "kata_reference" / "P3_mp_reference.json"
)

ANDREW_ANGLE_NAMES = [
    "right_elbow", "left_elbow",
    "right_shoulder", "left_shoulder",
    "right_knee", "left_knee",
    "right_hip", "left_hip",
    "spine_lean",
]

_mads_cache   = None
_exampler_cache = None
_p3_stats_cache = None


def _load_mads():
    global _mads_cache
    if _mads_cache is None and ANDREW_PATH.exists():
        with open(ANDREW_PATH, encoding="utf-8") as f:
            _mads_cache = json.load(f)
    return _mads_cache


def _load_exampler():
    global _exampler_cache
    if _exampler_cache is None and EXAMPLER_PATH.exists():
        with open(EXAMPLER_PATH, encoding="utf-8") as f:
            _exampler_cache = json.load(f)
    return _exampler_cache or {}


def _load_p3_stats():
    global _p3_stats_cache
    if _p3_stats_cache is None and ANDREW_REF_JSON.exists():
        with open(ANDREW_REF_JSON, encoding="utf-8") as f:
            raw = json.load(f)
        _p3_stats_cache = raw.get("move_stats", {})
    return _p3_stats_cache or {}


@router.get("/{move_id}/skeleton")
def get_skeleton(move_id: str):
    """Return the reference angle sequence for a given move."""
    move_id = move_id.lower().strip()

    # 1. Try MADS P3 reference first
    mads = _load_mads()
    if mads and move_id in mads:
        data = mads[move_id]
        return JSONResponse({
            "move_id":     move_id,
            "fps":         data.get("fps", 15.0),
            "n_frames":    len(data["angles"]),
            "angle_names": data.get("angle_names", ANDREW_ANGLE_NAMES),
            "angles":      data["angles"],
            "source":      "mads_p3",
        })

    # 2. Fall back to YouTube exemplars
    exampler = _load_exampler()
    if move_id in exampler:
        data = exampler[move_id]
        return JSONResponse({
            "move_id":     move_id,
            "fps":         data.get("fps", 29.97),
            "n_frames":    len(data["angles"]),
            "angle_names": None,   # 14-angle set (no named mapping provided)
            "angles":      data["angles"],
            "source":      "exampler",
        })

    raise HTTPException(
        status_code=404,
        detail=f"No skeleton reference found for move '{move_id}'. "
               "Run scripts/extract_mads_sequence_mads.py first."
    )


@router.get("/{move_id}/reference_stats")
def get_reference_stats(move_id: str):
    """
    Return MADS per-joint angle statistics for this move.
    Used by the frontend to render per-joint error bars and target angle display.
    """
    move_id   = move_id.lower().strip()
    p3_stats  = _load_p3_stats()
    move_data = p3_stats.get(move_id)

    if not move_data:
        raise HTTPException(
            status_code=404,
            detail=f"No reference statistics found for move '{move_id}'."
        )

    # Clean up — only return what the frontend needs
    result = {}
    for joint, stats in move_data.items():
        result[joint] = {
            "mean":  round(float(stats["mean"]), 1),
            "std":   round(float(stats.get("std", 15.0)), 1),
            "tight": [round(stats["tight"][0], 1), round(stats["tight"][1], 1)],
            "loose": [round(stats["loose"][0], 1), round(stats["loose"][1], 1)],
        }

    return JSONResponse({"move_id": move_id, "joints": result})


@router.get("/available")
def list_available():
    """Return all move IDs that have reference skeletons available."""
    mads = _load_mads() or {}
    exampler = _load_exampler()
    all_moves = sorted(set(list(mads.keys()) + list(exampler.keys())))
    return {"moves": all_moves}
