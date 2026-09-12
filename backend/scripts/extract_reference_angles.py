"""
backend/scripts/extract_reference_angles.py

Extracts the 14 joint angles from each Exemplar video using MediaPipe,
then computes per-joint statistics (mean, std, min, max) and writes them
to backend/app/rag/data/pro_reference_angles.json.

Run ONCE (from project root with cvEnv active):
    cd backend
    python scripts/extract_reference_angles.py

Requirements: mediapipe, opencv-python  (already in requirements.txt)
"""

import cv2
import math
import json
import sys
import numpy as np
from pathlib import Path

# ── Make 'app' importable ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import mediapipe as mp
except ImportError:
    print("❌  mediapipe not found. Activate cvEnv first.")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
EXAMPLERS_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "Examplers"
OUT_FILE      = Path(__file__).resolve().parent.parent / "app" / "rag" / "data" / "pro_reference_angles.json"

# Map video filename keywords → canonical move id
MOVE_MAPPING = {
    "Gyakudzuki": "gyaku_zuki",
    "MaeGeri":    "mae_geri",
    "GedanBarai": "gedan_barai",
}

# 14 angle names (same order as angle_calculator.py)
ANGLE_NAMES = [
    "left_elbow", "right_elbow",
    "left_knee",  "right_knee",
    "left_hip",   "right_hip",
    "left_shoulder", "right_shoulder",
    "shoulder_alignment", "torso_twist",
    "left_ankle", "right_ankle",
    "left_wrist", "right_wrist",
]

# Landmark triplets for each angle (a → b ← c, angle at b)
ANGLE_TRIPLETS = [
    (11, 13, 15),  # left_elbow
    (12, 14, 16),  # right_elbow
    (23, 25, 27),  # left_knee
    (24, 26, 28),  # right_knee
    (11, 23, 25),  # left_hip
    (12, 24, 26),  # right_hip
    (23, 11, 13),  # left_shoulder
    (24, 12, 14),  # right_shoulder
    ( 0, 11, 12),  # shoulder_alignment
    (11, 12, 24),  # torso_twist
    (25, 27, 31),  # left_ankle
    (26, 28, 32),  # right_ankle
    (13, 15, 17),  # left_wrist
    (14, 16, 18),  # right_wrist
]

def calc_angle(a, b, c) -> float:
    """3-D angle at vertex b (degrees)."""
    ba = (a.x - b.x, a.y - b.y, a.z - b.z)
    bc = (c.x - b.x, c.y - b.y, c.z - b.z)
    dot   = sum(ba[i] * bc[i] for i in range(3))
    mag_a = math.sqrt(sum(v ** 2 for v in ba))
    mag_c = math.sqrt(sum(v ** 2 for v in bc))
    if mag_a * mag_c == 0:
        return 0.0
    cos_v = max(-1.0, min(1.0, dot / (mag_a * mag_c)))
    return math.degrees(math.acos(cos_v))

def extract_angles_from_video(video_path: Path) -> list[dict]:
    """Run MediaPipe on every frame of the video and return per-frame angle dicts."""
    mp_pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ⚠️  Cannot open {video_path.name}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  Processing {total_frames} frames …", end="", flush=True)

    frame_angles = []
    good = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = mp_pose.process(rgb)
        if not res.pose_landmarks:
            continue
        lm = res.pose_landmarks.landmark
        if len(lm) < 33:
            continue

        angles = {}
        for name, (a, b, c) in zip(ANGLE_NAMES, ANGLE_TRIPLETS):
            angles[name] = calc_angle(lm[a], lm[b], lm[c])
        frame_angles.append(angles)
        good += 1

    cap.release()
    mp_pose.close()
    print(f"  {good} frames with pose detected.")
    return frame_angles

def compute_stats(frame_angles: list[dict]) -> dict:
    """Compute mean / std / min / max per joint across all frames."""
    if not frame_angles:
        return {}
    stats = {}
    for name in ANGLE_NAMES:
        vals = [f[name] for f in frame_angles if name in f]
        arr  = np.array(vals)
        stats[name] = {
            "mean": round(float(arr.mean()), 2),
            "std":  round(float(arr.std()),  2),
            "min":  round(float(arr.min()),  2),
            "max":  round(float(arr.max()),  2),
        }
    return stats

# ── Main ──────────────────────────────────────────────────────────────────────
if not EXAMPLERS_DIR.exists():
    print(f"❌  Examplers directory not found: {EXAMPLERS_DIR}")
    sys.exit(1)

video_files = list(EXAMPLERS_DIR.glob("*.mp4")) + list(EXAMPLERS_DIR.glob("*.mov"))
if not video_files:
    print(f"❌  No .mp4 / .mov files found in {EXAMPLERS_DIR}")
    sys.exit(1)

reference = {}

for vf in sorted(video_files):
    # Detect which move this video belongs to
    move_id = None
    for keyword, mid in MOVE_MAPPING.items():
        if keyword.lower() in vf.stem.lower():
            move_id = mid
            break
    if move_id is None:
        print(f"⚠️  Skipping '{vf.name}' — could not map to a move id")
        continue

    print(f"\n📹  {vf.name}  →  {move_id}")
    frames = extract_angles_from_video(vf)

    if not frames:
        print("  No pose landmarks extracted — skipping.")
        continue

    stats = compute_stats(frames)

    # Merge: if a move already has data from a previous video, average the means
    if move_id in reference:
        existing = reference[move_id]
        for joint in ANGLE_NAMES:
            if joint in stats and joint in existing:
                # Simple average of means (could be weighted by frame count)
                existing[joint]["mean"] = round(
                    (existing[joint]["mean"] + stats[joint]["mean"]) / 2, 2)
                existing[joint]["std"]  = round(
                    max(existing[joint]["std"], stats[joint]["std"]), 2)
                existing[joint]["min"]  = round(
                    min(existing[joint]["min"], stats[joint]["min"]), 2)
                existing[joint]["max"]  = round(
                    max(existing[joint]["max"], stats[joint]["max"]), 2)
    else:
        reference[move_id] = stats

# ── Write output ──────────────────────────────────────────────────────────────
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(reference, f, indent=2)

print(f"\n✅  Wrote reference angles for {list(reference.keys())} → {OUT_FILE}")
print("\nSummary:")
for move, joints in reference.items():
    print(f"  {move}:")
    for joint, st in joints.items():
        print(f"    {joint:22s}  mean={st['mean']:6.1f}°  std={st['std']:5.1f}°")
