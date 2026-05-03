"""
backend/app/rag/dtw_comparator.py

Loads pre-extracted Exemplar angle sequences and compares a user's 30-frame
sequence frame-by-frame using Dynamic Time Warping (DTW).

Key features
────────────
• Mirroring: tries both the original user sequence AND a left↔right mirrored
  version, then picks whichever gives a lower DTW distance. This handles the
  case where the exemplar used the right arm but the user used the left.

• score_all_classes(): returns per-class DTW distances (degrees) so the
  classifier's OOD guard can validate or override the model's prediction.
"""

import json
import numpy as np
from pathlib import Path

from .angle_calculator import ANGLE_NAMES, compute_14_angles

SEQUENCES_PATH = Path(__file__).resolve().parent / "data" / "exampler_sequences.json"

# ── Error threshold for RAG coaching (ignore small deviations) ────────────────
ERROR_THRESHOLD = 12.0          # degrees

# ── Left / Right mirror pairs (indices into ANGLE_NAMES list) ────────────────
# Swapping these simulates the user doing the move on the opposite side.
# shoulder_alignment (8) and torso_twist (9) stay symmetric, not swapped.
MIRROR_PAIRS = [
    (0, 1),   # left_elbow   ↔ right_elbow
    (2, 3),   # left_knee    ↔ right_knee
    (4, 5),   # left_hip     ↔ right_hip
    (6, 7),   # left_shoulder ↔ right_shoulder
    (10, 11), # left_ankle   ↔ right_ankle
    (12, 13), # left_wrist   ↔ right_wrist
]

_sequences_cache = None


def get_reference_sequences() -> dict:
    """Load exampler_sequences.json once into memory as numpy arrays."""
    global _sequences_cache
    if _sequences_cache is None:
        if not SEQUENCES_PATH.exists():
            print(
                "⚠️  exampler_sequences.json not found — "
                "run scripts/extract_exampler_sequences.py first"
            )
            _sequences_cache = {}
        else:
            with open(SEQUENCES_PATH, "r") as f:
                raw = json.load(f)
            _sequences_cache = {
                move: np.array(data["angles"], dtype=np.float32)
                for move, data in raw.items()
            }
    return _sequences_cache


def _mirror_sequence(seq: np.ndarray) -> np.ndarray:
    """
    Return a copy of seq (N, 14) with left/right joint angles swapped.
    This normalises for practitioners who lead with the opposite limb.
    """
    mirrored = seq.copy()
    for l_idx, r_idx in MIRROR_PAIRS:
        mirrored[:, l_idx] = seq[:, r_idx]
        mirrored[:, r_idx] = seq[:, l_idx]
    return mirrored


def _dtw(user_seq: np.ndarray, ref_seq: np.ndarray):
    """
    Classic DTW between two angle sequences.

    Parameters
    ----------
    user_seq : (N, 14)  user's angle sequence   (degrees)
    ref_seq  : (M, 14)  reference angle sequence (degrees)

    Returns
    -------
    path : list[(i, j)] — optimal alignment index pairs
    """
    N, M = len(user_seq), len(ref_seq)

    # Per-pair cost: mean absolute angle difference (degrees)
    diff = user_seq[:, np.newaxis, :] - ref_seq[np.newaxis, :, :]   # (N, M, 14)
    cost = np.mean(np.abs(diff), axis=-1)                             # (N, M)

    # Accumulated cost (standard DTW DP)
    D = np.full((N, M), np.inf, dtype=np.float32)
    D[0, 0] = cost[0, 0]
    for i in range(1, N):
        D[i, 0] = D[i - 1, 0] + cost[i, 0]
    for j in range(1, M):
        D[0, j] = D[0, j - 1] + cost[0, j]
    for i in range(1, N):
        for j in range(1, M):
            D[i, j] = cost[i, j] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])

    # Traceback
    path = []
    i, j = N - 1, M - 1
    while i > 0 or j > 0:
        path.append((i, j))
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            best = int(np.argmin([D[i - 1, j], D[i, j - 1], D[i - 1, j - 1]]))
            if best == 0:
                i -= 1
            elif best == 1:
                j -= 1
            else:
                i -= 1; j -= 1
    path.append((0, 0))
    path.reverse()
    return path


def _dtw_distance(user_seq: np.ndarray, ref_seq: np.ndarray) -> float:
    """
    Return the mean per-frame angular deviation (degrees) along the optimal
    DTW path.  Lower = closer match.
    """
    path = _dtw(user_seq, ref_seq)
    u = user_seq[[p[0] for p in path]]
    r = ref_seq[[p[1] for p in path]]
    return float(np.mean(np.abs(u - r)))


def score_all_classes(user_angles_deg: np.ndarray) -> dict:
    """
    Run DTW against every available reference class and return per-class
    distances (degrees).  Handles mirroring automatically.

    Parameters
    ----------
    user_angles_deg : (N, 14) numpy array — angles in DEGREES
        (convert from normalized 0-1 by multiplying by 180 if needed)

    Returns
    -------
    { "mae_geri": 18.3, "gyaku_zuki": 31.7, "gedan_barai": 14.1 }
    Empty dict if no reference sequences exist.
    """
    sequences = get_reference_sequences()
    if not sequences:
        return {}

    mirrored = _mirror_sequence(user_angles_deg)
    scores = {}
    for move_id, ref_seq in sequences.items():
        d_orig = _dtw_distance(user_angles_deg, ref_seq)
        d_mirr = _dtw_distance(mirrored, ref_seq)
        scores[move_id] = min(d_orig, d_mirr)
    return scores


def compare_with_dtw(move_id: str, user_landmark_frames: list) -> list[dict]:
    """
    Compare a user's rep (list of 33-landmark dicts per frame) to the Exemplar
    reference using DTW.  Tries both original and mirrored orientations.

    Parameters
    ----------
    move_id              : e.g. "mae_geri"
    user_landmark_frames : list of frames, each frame = list of 33 dicts
                           [{"x":…,"y":…,"z":…,"visibility":…}, …]

    Returns
    -------
    List of error dicts sorted worst-first, ready for RAG querying:
        [
          {
            "joint":      "left_knee",
            "query":      "User's left_knee is 28.4° off from master …",
            "user_val":   82.3,
            "ref_val":    54.1,
            "mean_error": 28.4,
            "target_range": "39-69",
            "mirrored":   False,   ← True if mirrored orientation matched better
          },
          …
        ]
    Returns [] if no reference available or no errors exceed threshold.
    """
    sequences = get_reference_sequences()
    if move_id not in sequences:
        return []

    ref_seq = sequences[move_id]   # (M, 14)

    # Build user angle matrix from raw landmarks
    user_angles_list = []
    for frame_lms in user_landmark_frames:
        angles_dict = compute_14_angles(frame_lms)
        user_angles_list.append([angles_dict[name] for name in ANGLE_NAMES])

    if not user_angles_list:
        return []

    user_seq = np.array(user_angles_list, dtype=np.float32)    # (N, 14)
    mirrored = _mirror_sequence(user_seq)

    # Pick the orientation with the lower DTW distance
    d_orig = _dtw_distance(user_seq, ref_seq)
    d_mirr = _dtw_distance(mirrored, ref_seq)
    use_mirrored = d_mirr < d_orig
    best_seq      = mirrored if use_mirrored else user_seq

    if use_mirrored:
        print(f"[DTW] Mirrored orientation matched better "
              f"({d_mirr:.1f}° vs {d_orig:.1f}°) — using mirrored.")

    # Run full DTW with best orientation
    path = _dtw(best_seq, ref_seq)

    user_aligned = best_seq[[p[0] for p in path]]     # (P, 14)
    ref_aligned  = ref_seq[[p[1] for p in path]]      # (P, 14)
    abs_diff     = np.abs(user_aligned - ref_aligned)  # (P, 14)

    mean_diff = np.mean(abs_diff, axis=0)              # (14,)
    user_mean = np.mean(user_aligned, axis=0)          # (14,)
    ref_mean  = np.mean(ref_aligned, axis=0)           # (14,)

    errors = []
    for k, joint_name in enumerate(ANGLE_NAMES):
        md = float(mean_diff[k])
        if md < ERROR_THRESHOLD:
            continue
        um = float(user_mean[k])
        rm = float(ref_mean[k])
        direction = "too extended/large" if um > rm else "too bent/small"
        errors.append({
            "joint":        joint_name,
            "query":        (f"User's {joint_name} is {md:.1f}° off from the master "
                             f"during {move_id} ({direction})."),
            "user_val":     round(um, 1),
            "ref_val":      round(rm, 1),
            "mean_error":   round(md, 1),
            "target_range": f"{round(rm - 15, 0):.0f}-{round(rm + 15, 0):.0f}",
            "mirrored":     use_mirrored,
        })

    return sorted(errors, key=lambda e: e["mean_error"], reverse=True)
