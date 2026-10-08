"""
backend/scripts/extract_master_reference.py
============================================
NEW Master Ground-Truth extractor (replaces extract_mads_sequence.py).

Reads the Academy Master videos (isolated textbook techniques) with MediaPipe
Pose, computes the 9 critical joint angles per frame (identical definitions to
dtw_comparator.compute_mads_angles), smooths them with a Savitzky-Golay filter
(window=5), downsamples to exactly 30 frames, and writes:

    backend/app/rag/data/master_reference_sequences.json

Expected video naming convention (stance is REQUIRED so we can build the
stance-specific keys used by the paper / app):

    <Move>_<stance>[_anything].mp4        e.g.
        MaeGeri_standing.mp4
        MaeGeri_zenkutsu.mp4
        GyakuZuki_standing_rep2.mp4
        GedanBarai_from_zenkutsu_dachi.mp4

    move   : MaeGeri | GyakuZuki | GedanBarai   (case-insensitive)
    stance : standing | zenkutsu                (also matches from_standing /
                                                 from_zenkutsu / zenkutsu_dachi)

If several clips exist for the same (move, stance), their angle trajectories
are averaged into ONE reference sequence per key (keeps the DTW comparator's
single-reference-per-class assumption; also saves every individual rep under
"<key>__rep<i>" for inspection).

Output keys:
    mae_geri_from_standing      gyaku_zuki_from_standing      gedan_barai_from_standing
    mae_geri_from_zenkutsu      gyaku_zuki_from_zenkutsu      gedan_barai_from_zenkutsu

Run (from backend/, cvEnv active):
    python scripts/extract_master_reference.py --videos "D:/path/to/MasterVideos"
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

# ── Make 'app' importable ─────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent          # backend/
sys.path.insert(0, str(BASE))

try:
    import mediapipe as mp
    import cv2
except ImportError:
    print("❌  mediapipe / opencv not found. Activate cvEnv first.")
    sys.exit(1)

try:
    from scipy.signal import savgol_filter
    HAVE_SAVGOL = True
except ImportError:
    HAVE_SAVGOL = False
    print("⚠️  scipy not found — skipping Savitzky-Golay smoothing.")

OUT_PATH = BASE / "app" / "rag" / "data" / "master_reference_sequences.json"
WINDOW_SIZE = 30

# Same order as dtw_comparator.ANDREW_ANGLE_NAMES (minus hip_rotation which is
# computed live in compute_mads_angles but is NOT part of the stored GT matrix
# in mads_reference_sequences.json either — keep consistent: 9 joints).
MASTER_ANGLE_NAMES = [
    "right_elbow", "left_elbow",
    "right_shoulder", "left_shoulder",
    "right_knee", "left_knee",
    "right_hip", "left_hip",
    "spine_lean",
]

MOVE_MAP = {
    "maegeri":    "mae_geri",
    "gyakuzuki":  "gyaku_zuki",
    "gyakudzuki": "gyaku_zuki", 
    "gedanbarai": "gedan_barai",
}


def parse_clip_name(stem: str):
    """Return (move_id, stance) or None if the name doesn't match."""
    parts = stem.split("_")
    if len(parts) < 2:
        return None
    move_raw = re.sub(r"[^a-z]", "", parts[0].lower())
    move_id = MOVE_MAP.get(move_raw)
    if move_id is None:
        # tolerate e.g. "Mae_Geri_side_..." style
        joined = re.sub(r"[^a-z]", "", "_".join(parts[:2]).lower())
        move_id = MOVE_MAP.get(joined)
    if move_id is None:
        return None

    tail = "_".join(p.lower() for p in parts[1:])
    if "standing" in tail:
        stance = "standing"
    elif "zenkutsu" in tail:
        stance = "zenkutsu"
    else:
        return (move_id, None)
    return (move_id, stance)


def _angle_3d(a, b, c):
    ba = a - b
    bc = c - b
    nba, nbc = np.linalg.norm(ba), np.linalg.norm(bc)
    if nba == 0 or nbc == 0:
        return 0.0
    cosv = np.clip(np.dot(ba, bc) / (nba * nbc + 1e-8), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosv)))


def compute_master_angles(lms: np.ndarray) -> list:
    """lms: (33, 3) array of x,y,z (MediaPipe normalized coords). 9 angles."""
    def A(i, j, k):
        return _angle_3d(lms[i], lms[j], lms[k])
    # Triplets identical to dtw_comparator.compute_mads_angles:
    #   shoulder = (hip, shoulder, elbow)  e.g. right_shoulder = (24, 12, 14)
    return [
        A(12, 14, 16),                    # right_elbow
        A(11, 13, 15),                    # left_elbow
        A(14, 12, 24),                    # right_shoulder
        A(13, 11, 23),                    # left_shoulder
        A(24, 26, 28),                    # right_knee
        A(23, 25, 27),                    # left_knee
        A(12, 24, 26),                    # right_hip
        A(11, 23, 25),                    # left_hip
        A(0, 23, 25),                     # spine_lean
    ]


def extract_video_angles(video_path: Path) -> np.ndarray:
    """Run MediaPipe Pose over the whole video → (T, 9) angle matrix (degrees)."""
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    cap = cv2.VideoCapture(str(video_path))
    rows = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        if res.pose_landmarks:
            lms = np.array([[lm.x, lm.y, lm.z]
                            for lm in res.pose_landmarks.landmark], dtype=np.float32)
            rows.append(compute_master_angles(lms))
    cap.release()
    pose.close()
    if len(rows) < WINDOW_SIZE:
        raise ValueError(f"{video_path.name}: only {len(rows)} detected frames (<{WINDOW_SIZE})")
    return np.array(rows, dtype=np.float32)


def smooth_downsample(ang: np.ndarray, window: int = 5) -> list:
    """Savitzky-Golay smooth (window=5) then linspace-downsample to 30 frames."""
    if HAVE_SAVGOL and ang.shape[0] >= window:
        ang = savgol_filter(ang, window_length=window, polyorder=2, axis=0)
    idx = np.linspace(0, ang.shape[0] - 1, WINDOW_SIZE).astype(int)
    return ang[idx].round(2).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True, help="Folder containing Master GT videos")
    args = ap.parse_args()
    vid_dir = Path(args.videos)
    if not vid_dir.is_dir():
        print(f"❌ Not a directory: {vid_dir}")
        sys.exit(1)

    grouped = {}   # (move_id, stance) -> list of (name, angles30)
    skipped = []
    for vf in sorted(vid_dir.glob("*")):
        if vf.suffix.lower() not in (".mp4", ".mov", ".avi", ".mk4", ".mkv"):
            continue
        parsed = parse_clip_name(vf.stem)
        if parsed is None or parsed[1] is None:
            skipped.append(vf.name)
            continue
        move_id, stance = parsed
        print(f"▶ Processing {vf.name}  →  {move_id}_from_{stance}")
        try:
            raw = extract_video_angles(vf)
        except Exception as e:
            print(f"   ❌ {e}")
            skipped.append(vf.name)
            continue
        grouped.setdefault((move_id, stance), []).append((vf.name, smooth_downsample(raw)))

    out = {}
    for (move_id, stance), reps in sorted(grouped.items()):
        key = f"{move_id}_from_{stance}"
        stack = np.array([r[1] for r in reps], dtype=np.float32)     # (R, 30, 9)

        # ── Dominant-limb selection (automatic mirroring) ─────────────────────
        # Master videos are recorded 45° front-right; the performing limb may be
        # right OR left depending on stance/lead. Pick the orientation whose
        # kicking/striking limb angles have the larger dynamic range, so the GT
        # is stored right-limb-dominant (the DTW comparator mirrors trainees as
        # needed anyway — this just keeps the reference canonical).
        def dyn_range(mat):   # mat: (R,30,9); joints 4..7 = R-knee,R-hip,L-knee,L-hip
            return float(np.mean(mat[:, :, 4:8].max(axis=1) - mat[:, :, 4:8].min(axis=1)))

        pairs = [(0, 1), (2, 3), (4, 5), (6, 7)]     # elbow, shoulder, knee, hip L/R swaps

        def _flip(mat):
            m = mat.copy()
            for a, b in pairs:
                m[:, :, a], m[:, :, b] = mat[:, :, b].copy(), mat[:, :, a].copy()
            return m

        flipped = _flip(stack)
        if dyn_range(flipped) > dyn_range(stack):
            stack = flipped
            print(f"   ↹ {key}: stored MIRRORED (right-limb dominant)")

        mean_seq = stack.mean(axis=0).round(2).tolist()              # (30, 9)
        out[key] = {
            "fps": 30.0,
            "angle_names": MASTER_ANGLE_NAMES,
            "n_frames": WINDOW_SIZE,
            "source_clips": [r[0] for r in reps],
            "angles": mean_seq,
        }
        for i, (name, seq) in enumerate(reps):
            if len(reps) > 1:
                one = np.array(seq, dtype=np.float32)[None, :, :]
                fl = _flip(one)
                if dyn_range(fl) > dyn_range(one):
                    seq = fl[0].round(2).tolist()
                out[f"{key}__rep{i}"] = {"angles": seq, "source_clip": name}
        print(f"✅ {key}: averaged {len(reps)} rep(s)")

    missing = {f"{m}_from_{s}" for m in MOVE_MAP.values() for s in ("standing", "zenkutsu")} - set(out)
    if missing:
        print(f"\n⚠️  Missing expected (move, stance) references: {sorted(missing)}")
    if skipped:
        print(f"⚠️  Skipped files (bad name / extraction failed): {skipped}")

    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n💾 Wrote {len(out)} entries → {OUT_PATH}")


if __name__ == "__main__":
    main()
