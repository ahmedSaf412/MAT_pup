"""
backend/scripts/extract_exampler_sequences.py

Runs MediaPipe on each Exemplar video and saves the FULL angle sequence
(one 14-float array per frame) to:

    backend/app/rag/data/exampler_sequences.json

Structure:
{
  "gyaku_zuki": {
    "fps": 30.0,
    "angles": [[a0,a1,...,a13], [...], ...]   ← N_frames × 14 angles (degrees)
  },
  "mae_geri":    { "fps": ..., "angles": [...] },
  "gedan_barai": { "fps": ..., "angles": [...] }
}

This file is loaded at runtime by the DTW comparator.

Usage (from project root with cvEnv active):
    cd backend
    python scripts/extract_exampler_sequences.py
"""

import cv2
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import mediapipe as mp
except ImportError:
    print("❌  mediapipe not installed. Activate cvEnv first.")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
EXAMPLERS_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "Examplers"
OUT_FILE      = Path(__file__).resolve().parent.parent / "app" / "rag" / "data" / "exampler_sequences.json"

MOVE_MAPPING = {
    "Gyakudzuki": "gyaku_zuki",
    "MaeGeri":    "mae_geri",
    "GedanBarai": "gedan_barai",
}

ANGLE_TRIPLETS = [          # (a, vertex_b, c) → angle at b
    (11, 13, 15),           # left_elbow
    (12, 14, 16),           # right_elbow
    (23, 25, 27),           # left_knee
    (24, 26, 28),           # right_knee
    (11, 23, 25),           # left_hip
    (12, 24, 26),           # right_hip
    (23, 11, 13),           # left_shoulder
    (24, 12, 14),           # right_shoulder
    ( 0, 11, 12),           # shoulder_alignment
    (11, 12, 24),           # torso_twist
    (25, 27, 31),           # left_ankle
    (26, 28, 32),           # right_ankle
    (13, 15, 17),           # left_wrist
    (14, 16, 18),           # right_wrist
]

def calc_angle(a, b, c) -> float:
    ba = (a.x - b.x, a.y - b.y, a.z - b.z)
    bc = (c.x - b.x, c.y - b.y, c.z - b.z)
    dot   = sum(ba[i] * bc[i] for i in range(3))
    mag_a = math.sqrt(sum(v**2 for v in ba))
    mag_c = math.sqrt(sum(v**2 for v in bc))
    if mag_a * mag_c == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (mag_a * mag_c)))))


def extract_sequence(video_path: Path) -> tuple[list[list[float]], float]:
    """Return (frames, fps) where frames is a list of 14-float angle arrays."""
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  {video_path.name}: {total} frames @ {fps:.1f} fps", flush=True)

    sequences = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not results.pose_landmarks:
            continue
        lm = results.pose_landmarks.landmark
        if len(lm) < 33:
            continue
        angles = [calc_angle(lm[a], lm[b], lm[c]) for a, b, c in ANGLE_TRIPLETS]
        sequences.append(angles)

    cap.release()
    pose.close()
    print(f"  → {len(sequences)} frames with pose detected.")
    return sequences, fps


if not EXAMPLERS_DIR.exists():
    print(f"❌  Examplers directory not found: {EXAMPLERS_DIR}")
    sys.exit(1)

video_files = sorted(
    list(EXAMPLERS_DIR.glob("*.mp4")) + list(EXAMPLERS_DIR.glob("*.mov"))
)
if not video_files:
    print("❌  No .mp4/.mov files found in Examplers/")
    sys.exit(1)

output = {}

for vf in video_files:
    move_id = None
    for kw, mid in MOVE_MAPPING.items():
        if kw.lower() in vf.stem.lower():
            move_id = mid
            break
    if move_id is None:
        print(f"⚠️  Skipping '{vf.name}' — cannot map to move id")
        continue

    print(f"\n📹  {vf.name}  →  {move_id}")
    sequences, fps = extract_sequence(vf)

    if not sequences:
        print("  No pose detected — skipped.")
        continue

    # If move already has data from another file, concatenate
    if move_id in output:
        output[move_id]["angles"].extend(sequences)
    else:
        output[move_id] = {"fps": fps, "angles": sequences}

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_FILE, "w") as f:
    json.dump(output, f)

print(f"\n✅  Saved exampler sequences to:\n   {OUT_FILE}\n")
for mid, data in output.items():
    print(f"   {mid:20s}  {len(data['angles'])} frames")
