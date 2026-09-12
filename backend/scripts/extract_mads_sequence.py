"""
scripts/extract_mads_sequences.py
====================================
Extracts MADS P3 professional per-frame angle data for the 3 trained
moves (mae_geri, gyaku_zuki, gedan_barai) and saves them as a reference
sequence file compatible with the DTW comparator.

WHY NOT USE MEAN ANGLES?
─────────────────────────
For dynamic movements like Mae Geri, the right_knee angle sweeps from
~175° (standing) to ~40° (chamber) to ~165° (full extension) in a single rep.
Taking the mean gives ~130°, which the practitioner was never at.
DTW (Dynamic Time Warping) aligns each user frame to the nearest equivalent
reference frame — which is mathematically correct for temporal movements.

This script:
1. Reads P3_mp_reference.json  (9-joint per-frame angles for all 1400 video frames)
2. Reads P3_labels.json         (GT frame ranges for each of the 17 kata moves)
3. Scales GT frame indices → video frame indices using the frame_scale factor
4. Extracts per-joint angles for [start:end] of the 3 trained moves
5. Downsamples to exactly 30 frames (linspace) to match your WINDOW_SIZE
6. Saves to app/rag/data/mads_reference_sequences.json

Run from the backend/ directory:
    python scripts/extract_mads_sequences.py
"""

import json
import sys
from pathlib import Path

import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).resolve().parent.parent         # backend/
ANDREW_DIR  = BASE / "MADS_correction" / "kata_reference"
MP_REF_PATH = ANDREW_DIR / "P3_mp_reference.json"
LABELS_PATH = ANDREW_DIR / "P3_labels.json"
OUT_PATH    = BASE / "app" / "rag" / "data" / "mads_reference_sequences.json"

# Moves trained by the classifier — must match keys in P3_labels.json segments
TRAINED_MOVES = {"gedan_barai", "gyaku_zuki", "mae_geri"}

# MADS 9 angles in a fixed order (must stay consistent with dtw_comparator.py)
ANDREW_ANGLE_NAMES = [
    "right_elbow",
    "left_elbow",
    "right_shoulder",
    "left_shoulder",
    "right_knee",
    "left_knee",
    "right_hip",
    "left_hip",
    "spine_lean",
]

WINDOW_SIZE = 30   # frames the Bi-LSTM was trained on


def downsample(values: list, n: int) -> list:
    """Linearly downsample (or upsample) a 1-D list to exactly n samples."""
    arr   = np.array(values, dtype=np.float32)
    idx   = np.linspace(0, len(arr) - 1, n)
    left  = np.floor(idx).astype(int)
    right = np.minimum(left + 1, len(arr) - 1)
    frac  = idx - left
    return (arr[left] * (1 - frac) + arr[right] * frac).tolist()


def main():
    print("=" * 60)
    print("  MADS P3 Reference Sequence Extractor")
    print("=" * 60)

    # ── Load reference data ──────────────────────────────────────────────────
    print(f"\n  Loading {MP_REF_PATH.name}  ({MP_REF_PATH.stat().st_size // 1024} KB) …")
    with open(MP_REF_PATH, encoding="utf-8") as f:
        mp_ref = json.load(f)

    per_frame = mp_ref["per_frame_angles"]   # {joint: [float×1400]}
    frame_scale = float(mp_ref.get("frame_scale", 1.0))
    total_video_frames = mp_ref["total_frames"]
    fps = float(mp_ref["fps"])

    print(f"  Video: {total_video_frames} frames @ {fps} fps")
    print(f"  Frame scale factor (GT→video): {frame_scale:.4f}")
    print(f"  Joints available: {list(per_frame.keys())}")

    # Verify all 9 MADS angles are present
    missing = [a for a in ANDREW_ANGLE_NAMES if a not in per_frame]
    if missing:
        sys.exit(f"\n  ERROR: Missing angles in per_frame_angles: {missing}")

    # ── Load GT labels to get frame ranges ───────────────────────────────────
    print(f"\n  Loading {LABELS_PATH.name} …")
    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = json.load(f)

    gt_total = labels["total_frames"]   # 816 GT frames (from depth sensor data)

    segments_by_name = {seg["name"]: seg for seg in labels["segments"]}

    # ── Extract sequences for each trained move ──────────────────────────────
    output = {}

    for move_name in TRAINED_MOVES:
        print(f"\n  [{move_name}]")

        # Try move_stats first (most accurate — already scaled to video frames)
        move_stats = mp_ref.get("move_stats", {}).get(move_name, {})

        vid_start, vid_end = None, None
        if move_stats:
            # Grab frame range from any joint (they're all the same per move)
            for joint_stats in move_stats.values():
                vf = joint_stats.get("video_frames")
                if vf and len(vf) == 2:
                    vid_start, vid_end = int(vf[0]), int(vf[1])
                    break
            if vid_start is not None:
                print(f"    Using move_stats video_frames: [{vid_start}, {vid_end}]")

        # Fall back: scale GT frames using frame_scale
        if vid_start is None:
            if move_name not in segments_by_name:
                print(f"    SKIP — not found in P3_labels.json segments")
                continue
            seg = segments_by_name[move_name]
            gt_start = seg["frame_start"]
            gt_end   = seg["frame_end"]
            vid_start = max(0,                      int(gt_start * frame_scale))
            vid_end   = min(total_video_frames - 1, int(gt_end   * frame_scale))
            print(f"    GT frames: [{gt_start}, {gt_end}] → "
                  f"video frames: [{vid_start}, {vid_end}] (scale={frame_scale:.3f})")

        n_frames = vid_end - vid_start + 1
        print(f"    Extracting {n_frames} frames → downsampling to {WINDOW_SIZE}")

        # Slice per-frame angles for each joint
        joint_slices = {}
        for joint in ANDREW_ANGLE_NAMES:
            full = per_frame[joint]
            sliced = full[vid_start : vid_end + 1]
            if len(sliced) == 0:
                print(f"    WARNING: Empty slice for {joint} — using zeros")
                sliced = [0.0] * n_frames
            joint_slices[joint] = sliced

        # Build (WINDOW_SIZE, 9) matrix: rows=frames, cols=joints in fixed order
        angle_matrix = []
        for t in range(WINDOW_SIZE):
            idx = int(t * (n_frames - 1) / (WINDOW_SIZE - 1)) if WINDOW_SIZE > 1 else 0
            row = [float(joint_slices[j][min(idx, len(joint_slices[j]) - 1)])
                   for j in ANDREW_ANGLE_NAMES]
            angle_matrix.append(row)

        # Sanity check
        arr = np.array(angle_matrix, dtype=np.float32)
        print(f"    Shape: {arr.shape}  |  "
              f"right_knee range: [{arr[:,4].min():.1f}°, {arr[:,4].max():.1f}°]  "
              f"(mean={arr[:,4].mean():.1f}°)")

        output[move_name] = {
            "fps":          fps,
            "angle_names":  ANDREW_ANGLE_NAMES,
            "n_frames":     n_frames,
            "vid_start":    vid_start,
            "vid_end":      vid_end,
            "angles":       angle_matrix,
        }

    # ── Save ─────────────────────────────────────────────────────────────────
    if not output:
        sys.exit("\n  ERROR: No sequences extracted — check move names")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"\n  Saved {len(output)} sequences → {OUT_PATH}  ({size_kb} KB)")
    print("  Moves:", list(output.keys()))
    print("\n  Done! ✓\n")


if __name__ == "__main__":
    main()
