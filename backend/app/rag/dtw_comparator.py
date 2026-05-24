"""
backend/app/rag/dtw_comparator.py

Loads pre-extracted Exemplar angle sequences and compares a user's 30-frame
sequence frame-by-frame using Dynamic Time Warping (DTW).

UPGRADE (MADS P3 Reference):
─────────────────────────────────
Now uses MADS professional P3 performer data as the primary reference
(mads_reference_sequences.json) instead of YouTube-scraped exemplars.
This reference covers 9 anatomically critical joints computed from 100+ frames
of an expert performer.

Falls back to the original exampler_sequences.json if MADS file
is not available (e.g., before running scripts/extract_mads_sequences.py).

Key features:
• Temporal alignment: DTW matches each user frame to the nearest equivalent
  reference frame — correct for dynamic movements like kicks and punches.
• MADS tight/loose/out bands used as per-joint error thresholds for
  richer feedback messages (e.g. "target: 58.9°, loose band: 14°–103°").
• Mirroring: tries both original and left↔right mirrored orientations.
• score_all_classes(): per-class DTW distances for the OOD guard.
"""

import json
import numpy as np
from pathlib import Path

from .angle_calculator import ANGLE_NAMES, compute_14_angles

# ── Reference sequence paths ───────────────────────────────────────────────────
DATA_DIR              = Path(__file__).resolve().parent / "data"
ANDREW_SEQUENCES_PATH = DATA_DIR / "mads_reference_sequences.json"
EXAMPLER_PATH         = DATA_DIR / "exampler_sequences.json"
THRESHOLDS_PATH       = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "MADS_correction" / "kata_reference" / "thresholds.json"
)

# ── MADS 9-joint angle names (fixed order must match extractor script) ────
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
N_ANDREW_JOINTS = len(ANDREW_ANGLE_NAMES)  # 9

# Mapping: mads joint name → index in the 14-angle ANGLE_NAMES list
_ANGLE_NAMES_IDX = {name: i for i, name in enumerate(ANGLE_NAMES)}
ANDREW_TO_14_IDX = [_ANGLE_NAMES_IDX[j] for j in ANDREW_ANGLE_NAMES
                    if j in _ANGLE_NAMES_IDX]
# joints in ANDREW_ANGLE_NAMES that are NOT in the 14-angle set:
# spine_lean uses triplet (0, 23, 25) which exists in 14-angle as "left_hip" variant
# We'll compute it inline in compute_mads_angles()

# ── Error threshold ────────────────────────────────────────────────────────────
ERROR_THRESHOLD = 12.0   # degrees — deviations below this are not reported

# ── Mirror pairs for the 9 MADS joints ──────────────────────────────────────
# ANDREW_ANGLE_NAMES indices:
#   0=right_elbow, 1=left_elbow, 2=right_shoulder, 3=left_shoulder,
#   4=right_knee,  5=left_knee,  6=right_hip,      7=left_hip,  8=spine_lean
ANDREW_MIRROR_PAIRS = [
    (0, 1),  # right_elbow   ↔ left_elbow
    (2, 3),  # right_shoulder ↔ left_shoulder
    (4, 5),  # right_knee    ↔ left_knee
    (6, 7),  # right_hip     ↔ left_hip
    # spine_lean (8) is symmetric — not swapped
]

# ── Cache ──────────────────────────────────────────────────────────────────────
_mads_cache    = None
_exampler_cache  = None
_thresholds_cache = None
_using_mads    = None   # logged once


def _load_thresholds() -> dict:
    """Load MADS global tight/loose bands (used for richer error messages)."""
    global _thresholds_cache
    if _thresholds_cache is None:
        if THRESHOLDS_PATH.exists():
            with open(THRESHOLDS_PATH, encoding="utf-8") as f:
                _thresholds_cache = json.load(f)
        else:
            _thresholds_cache = {}
    return _thresholds_cache


def _load_mads() -> dict | None:
    """Load MADS P3 reference sequences (9 joints, 30 frames each)."""
    global _mads_cache
    if _mads_cache is None:
        if not ANDREW_SEQUENCES_PATH.exists():
            return None
        with open(ANDREW_SEQUENCES_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _mads_cache = {
            move: {
                "angles": np.array(data["angles"], dtype=np.float32),  # (30, 9)
                "fps":    data.get("fps", 15.0),
            }
            for move, data in raw.items()
        }
    return _mads_cache


def _load_exampler() -> dict:
    """Load original YouTube-scraped exampler sequences (14 joints)."""
    global _exampler_cache
    if _exampler_cache is None:
        if not EXAMPLER_PATH.exists():
            print("⚠️  Neither MADS nor exampler reference sequences found.")
            _exampler_cache = {}
        else:
            with open(EXAMPLER_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            _exampler_cache = {
                move: np.array(data["angles"], dtype=np.float32)
                for move, data in raw.items()
            }
    return _exampler_cache


def get_reference_sequences() -> dict:
    """
    Return the best available reference sequences.
    Prefers MADS P3 data; falls back to exampler_sequences.json.
    Returns dict: {move_id: np.ndarray}
    """
    global _using_mads
    mads = _load_mads()
    if mads:
        if _using_mads is not True:
            print("[DTW] ✅ Using MADS P3 reference sequences (expert-quality data)")
            _using_mads = True
        return {move: data["angles"] for move, data in mads.items()}

    if _using_mads is not False:
        print("[DTW] ⚠️  MADS sequences not found — falling back to exampler_sequences.json")
        print("[DTW]    Run: python scripts/extract_mads_sequence_mads.py")
        _using_mads = False
    return _load_exampler()


def _is_mads_mode() -> bool:
    """Returns True if currently using MADS 9-joint sequences."""
    return bool(_load_mads())


# ── MADS 9-angle computation from raw landmarks ─────────────────────────────

def compute_mads_angles(landmarks: list) -> list:
    """
    Compute the 9 angles in MADS ANDREW_ANGLE_NAMES order from
    a list of 33 MediaPipe landmarks (each a dict with x,y,z,visibility).

    MADS angle triplets (landmark indices):
      right_elbow:   (12, 14, 16)
      left_elbow:    (11, 13, 15)
      right_shoulder:(14, 12, 24)
      left_shoulder: (13, 11, 23)
      right_knee:    (24, 26, 28)
      left_knee:     (23, 25, 27)
      right_hip:     (12, 24, 26)
      left_hip:      (11, 23, 25)
      spine_lean:    (0,  23, 25)   ← uses nose landmark 0
    """
    import math

    def angle_3d(a_idx, b_idx, c_idx) -> float:
        if not landmarks or len(landmarks) < 33:
            return 0.0
        a, b, c = landmarks[a_idx], landmarks[b_idx], landmarks[c_idx]
        bax = a.get("x",0) - b.get("x",0)
        bay = a.get("y",0) - b.get("y",0)
        baz = a.get("z",0) - b.get("z",0)
        bcx = c.get("x",0) - b.get("x",0)
        bcy = c.get("y",0) - b.get("y",0)
        bcz = c.get("z",0) - b.get("z",0)
        dot   = bax*bcx + bay*bcy + baz*bcz
        mag   = math.sqrt(bax**2+bay**2+baz**2) * math.sqrt(bcx**2+bcy**2+bcz**2)
        if mag < 1e-9:
            return 0.0
        return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))

    return [
        angle_3d(12, 14, 16),  # right_elbow
        angle_3d(11, 13, 15),  # left_elbow
        angle_3d(14, 12, 24),  # right_shoulder
        angle_3d(13, 11, 23),  # left_shoulder
        angle_3d(24, 26, 28),  # right_knee
        angle_3d(23, 25, 27),  # left_knee
        angle_3d(12, 24, 26),  # right_hip
        angle_3d(11, 23, 25),  # left_hip
        angle_3d( 0, 23, 25),  # spine_lean
    ]


# ── DTW core ──────────────────────────────────────────────────────────────────

def _mirror_sequence(seq: np.ndarray, mirror_pairs: list) -> np.ndarray:
    """Return a copy of seq with left/right joint angles swapped."""
    mirrored = seq.copy()
    for l_idx, r_idx in mirror_pairs:
        mirrored[:, l_idx] = seq[:, r_idx]
        mirrored[:, r_idx] = seq[:, l_idx]
    return mirrored


def _dtw(user_seq: np.ndarray, ref_seq: np.ndarray):
    """Classic DTW between two angle sequences. Returns alignment path."""
    N, M = len(user_seq), len(ref_seq)
    diff = user_seq[:, np.newaxis, :] - ref_seq[np.newaxis, :, :]
    cost = np.mean(np.abs(diff), axis=-1)

    D = np.full((N, M), np.inf, dtype=np.float32)
    D[0, 0] = cost[0, 0]
    for i in range(1, N):
        D[i, 0] = D[i-1, 0] + cost[i, 0]
    for j in range(1, M):
        D[0, j] = D[0, j-1] + cost[0, j]
    for i in range(1, N):
        for j in range(1, M):
            D[i, j] = cost[i, j] + min(D[i-1, j], D[i, j-1], D[i-1, j-1])

    path = []
    i, j = N - 1, M - 1
    while i > 0 or j > 0:
        path.append((i, j))
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            best = int(np.argmin([D[i-1, j], D[i, j-1], D[i-1, j-1]]))
            if best == 0:   i -= 1
            elif best == 1: j -= 1
            else:           i -= 1; j -= 1
    path.append((0, 0))
    path.reverse()
    return path


def _dtw_distance(user_seq: np.ndarray, ref_seq: np.ndarray) -> float:
    """Mean per-frame angular deviation (degrees) along optimal DTW path."""
    path = _dtw(user_seq, ref_seq)
    u = user_seq[[p[0] for p in path]]
    r = ref_seq[[p[1]  for p in path]]
    return float(np.mean(np.abs(u - r)))


# ── Public API ────────────────────────────────────────────────────────────────

def score_all_classes(user_angles_deg: np.ndarray, user_landmark_frames: list = None) -> dict:
    """
    Run DTW against every available reference class and return per-class
    distances (degrees). Used by the OOD guard in classify.py.

    user_angles_deg: (N, K) numpy array. If mads_mode is true and user_landmark_frames
                     is provided, this will be recomputed to shape (N, 9).
    """
    sequences = get_reference_sequences()
    if not sequences:
        return {}

    mads_mode   = _is_mads_mode()
    mirror_pairs  = ANDREW_MIRROR_PAIRS if mads_mode else [
        (0, 1), (2, 3), (4, 5), (6, 7), (10, 11), (12, 13)
    ]
    
    if mads_mode and user_landmark_frames:
        user_angles_list = []
        for frame_lms in user_landmark_frames:
            user_angles_list.append(compute_mads_angles(frame_lms))
        user_angles_deg = np.array(user_angles_list, dtype=np.float32)

    mirrored = _mirror_sequence(user_angles_deg, mirror_pairs)
    scores   = {}
    for move_id, ref_seq in sequences.items():
        d_orig = _dtw_distance(user_angles_deg, ref_seq)
        d_mirr = _dtw_distance(mirrored,        ref_seq)
        scores[move_id] = min(d_orig, d_mirr)
    return scores


def compare_with_dtw(move_id: str, user_landmark_frames: list) -> list[dict]:
    """
    Compare a user's rep to the reference using DTW.

    Parameters
    ----------
    move_id              : e.g. "mae_geri"
    user_landmark_frames : list of frames, each frame = list of 33 dicts
                           [{x,y,z,visibility}, ...]

    Returns
    -------
    Sorted list of error dicts (worst-first), ready for RAG querying.
    Empty list if no reference or no errors above threshold.
    """
    sequences   = get_reference_sequences()
    mads_mode = _is_mads_mode()

    if move_id not in sequences:
        return []

    ref_seq = sequences[move_id]  # (M, 9 or 14)

    # ── Build user angle matrix ──────────────────────────────────────────────
    user_angles_list = []
    for frame_lms in user_landmark_frames:
        if mads_mode:
            row = compute_mads_angles(frame_lms)
        else:
            angles_dict = compute_14_angles(frame_lms)
            row = [angles_dict[name] for name in ANGLE_NAMES]
        user_angles_list.append(row)

    if not user_angles_list:
        return []

    user_seq      = np.array(user_angles_list, dtype=np.float32)
    mirror_pairs  = ANDREW_MIRROR_PAIRS if mads_mode else [
        (0, 1), (2, 3), (4, 5), (6, 7), (10, 11), (12, 13)
    ]
    mirrored      = _mirror_sequence(user_seq, mirror_pairs)

    # Choose orientation with lower DTW distance
    d_orig       = _dtw_distance(user_seq, ref_seq)
    d_mirr       = _dtw_distance(mirrored, ref_seq)
    use_mirrored = d_mirr < d_orig
    best_seq     = mirrored if use_mirrored else user_seq

    if use_mirrored:
        print(f"[DTW] Mirrored orientation matched better "
              f"({d_mirr:.1f}° vs {d_orig:.1f}°)")

    # Full DTW alignment
    path         = _dtw(best_seq, ref_seq)
    user_aligned = best_seq[[p[0] for p in path]]
    ref_aligned  = ref_seq[ [p[1] for p in path]]
    abs_diff     = np.abs(user_aligned - ref_aligned)

    mean_diff = np.mean(abs_diff, axis=0)   # (K,)
    user_mean = np.mean(user_aligned, axis=0)
    ref_mean  = np.mean(ref_aligned,  axis=0)

    joint_names = ANDREW_ANGLE_NAMES if mads_mode else ANGLE_NAMES
    thresholds  = _load_thresholds()

    errors = []
    for k, joint_name in enumerate(joint_names):
        md = float(mean_diff[k])
        if md < ERROR_THRESHOLD:
            continue

        um = float(user_mean[k])
        rm = float(ref_mean[k])
        direction = "too extended/large" if um > rm else "too bent/small"

        # Enrich with MADS tight/loose bands if available
        bands = thresholds.get(joint_name, {})
        if bands:
            lo_l, hi_l = bands.get("loose", [rm - 15, rm + 15])
            target_range = f"{round(lo_l, 0):.0f}°–{round(hi_l, 0):.0f}°"
            query = (
                f"User's {joint_name} is {md:.1f}° off from the master "
                f"during {move_id} ({direction}). "
                f"Target: {rm:.1f}° (acceptable range: {target_range})."
            )
            # Classify using MADS bands
            tight = bands.get("tight", [rm - 10, rm + 10])
            if tight[0] <= um <= tight[1]:
                status = "tight"
            elif lo_l <= um <= hi_l:
                status = "loose"
            else:
                status = "out"
        else:
            target_range = f"{round(rm - 15, 0):.0f}°–{round(rm + 15, 0):.0f}°"
            query        = (
                f"User's {joint_name} is {md:.1f}° off from the master "
                f"during {move_id} ({direction})."
            )
            status = "out" if md > 25 else "loose"

        errors.append({
            "joint":        joint_name,
            "query":        query,
            "user_val":     round(um, 1),
            "ref_val":      round(rm, 1),
            "mean_error":   round(md, 1),
            "target_range": target_range,
            "mirrored":     use_mirrored,
            "status":       status,          # "tight" | "loose" | "out"
        })

    return sorted(errors, key=lambda e: e["mean_error"], reverse=True)
