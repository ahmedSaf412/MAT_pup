# -*- coding: utf-8 -*-
"""
kata_trainer.py  --  Karate Kata Corrector (Bassai Dai)

Side-by-side split view: Professional P3 reference skeleton vs. your pose.

INPUT MODES
  1. Live webcam
  2. Uploaded video file

CONTROLS
  SPACE       : pause / resume  (video mode only)
  LEFT/RIGHT  : skip +/-30 frames  (video mode only)
  R           : restart video  (video mode only)
  N           : save and advance to next move
  S           : save screenshot
  T           : toggle reference panel on/off
  Q           : quit and show report
"""

import sys
import os
import json
import time
import urllib.request
from datetime import datetime
import numpy as np

# ── UTF-8 console (Windows) ───────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# ── paths ─────────────────────────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.abspath(__file__))
REF_DIR  = os.path.join(BASE, "kata_reference")
SESS_DIR = os.path.join(BASE, "trainee_sessions")
SCR_DIR  = os.path.join(BASE, "screenshots")

if not os.path.isdir(REF_DIR):
    print(f"\n  ERROR: Reference folder not found: {REF_DIR}")
    print("  Make sure you run from inside the karate_corrector_export\\ folder.")
    sys.exit(1)

sys.path.insert(0, REF_DIR)
sys.path.insert(0, BASE)

try:
    from bassai_dai_moves import BASSAI_DAI_MOVES, MOVE_ANGLE_FOCUS
except ImportError:
    print(f"\n  ERROR: bassai_dai_moves.py not found in {REF_DIR}")
    print("  Make sure you run from inside the karate_corrector_export\\ folder.")
    sys.exit(1)

try:
    import cv2
    cv2.destroyAllWindows()
except ImportError:
    sys.exit("pip install opencv-python")

try:
    import mediapipe as mp
    BaseOptions        = mp.tasks.BaseOptions
    PoseLandmarker     = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOpts = mp.tasks.vision.PoseLandmarkerOptions
    RunningMode        = mp.tasks.vision.RunningMode
except Exception as e:
    sys.exit(f"mediapipe import failed: {e}")

MODEL_PATH  = os.path.join(REF_DIR, "pose_landmarker_full.task")
MODEL_URL   = ("https://storage.googleapis.com/mediapipe-models/"
               "pose_landmarker/pose_landmarker_full/float16/1/"
               "pose_landmarker_full.task")
MP_REF_PATH = os.path.join(REF_DIR, "P3_mp_reference.json")
ANGLES_PATH = os.path.join(REF_DIR, "P3_angles.json")
LABELS_PATH = os.path.join(REF_DIR, "P3_labels.json")
P3_FPS      = 15.0   # MADS depth video frame rate

# ── angle definitions ─────────────────────────────────────────────────────────
MP_ANGLE_MAP = {
    "right_elbow":    (12, 14, 16),
    "left_elbow":     (11, 13, 15),
    "right_shoulder": (14, 12, 24),
    "left_shoulder":  (13, 11, 23),
    "right_knee":     (24, 26, 28),
    "left_knee":      (23, 25, 27),
    "right_hip":      (12, 24, 26),
    "left_hip":       (11, 23, 25),
    "spine_lean":     (0,  23, 25),
}
ALL_ANGLES = list(MP_ANGLE_MAP.keys())

HINTS = {
    "right_elbow":    ("bend right arm more",    "straighten right arm"),
    "left_elbow":     ("bend left arm more",     "straighten left arm"),
    "right_shoulder": ("raise right elbow",      "lower right elbow"),
    "left_shoulder":  ("raise left elbow",       "lower left elbow"),
    "right_knee":     ("bend right knee deeper", "straighten right knee"),
    "left_knee":      ("bend left knee deeper",  "straighten left knee"),
    "right_hip":      ("close right hip",        "open right hip"),
    "left_hip":       ("close left hip",         "open left hip"),
    "spine_lean":     ("stand straighter",       "lean back less"),
}

# ── colours (BGR) ─────────────────────────────────────────────────────────────
C_GREEN  = ( 50, 210,  50)
C_YELLOW = (  0, 210, 230)
C_RED    = ( 50,  50, 230)
C_WHITE  = (240, 240, 240)
C_GRAY   = (110, 110, 110)
C_PANEL  = ( 28,  28,  40)
C_HDRBG  = ( 48,  48,  72)
C_ORANGE = ( 40, 160, 255)
C_DARK   = ( 18,  18,  28)
C_BLUE   = (210,  80,  20)   # BGR — steel blue (reference joints)
C_GOLD   = (  0, 200, 255)   # BGR — gold (highlighted bones)

# ── layout constants ──────────────────────────────────────────────────────────
PANEL_W  = 300   # side panel in single mode
FONT     = cv2.FONT_HERSHEY_SIMPLEX
FONTB    = cv2.FONT_HERSHEY_DUPLEX

# Split-view layout (fixed window size for both modes)
REF_W   = 580    # left (reference) panel width
REF_H   = 640    # panel height
DIV_W   = 4      # center divider
BBAR_H  = 80     # bottom bar
WIN_W   = REF_W * 2 + DIV_W   # 1164
WIN_H   = REF_H + BBAR_H      # 720

# Skeleton bones for split view (main body only — cleaner visually)
BONES_SPLIT = [
    (11, 12),                       # shoulders
    (11, 13), (13, 15),             # left arm
    (12, 14), (14, 16),             # right arm
    (11, 23), (12, 24),             # torso sides
    (23, 24),                       # hips
    (23, 25), (25, 27),             # left leg
    (24, 26), (26, 28),             # right leg
]

# ── skeleton drawing (single-mode, on original frame) ─────────────────────────
_SKEL_FULL = [
    (11,12),(11,13),(13,15),(12,14),(14,16),
    (15,17),(15,19),(17,19),(16,18),(16,20),(18,20),
    (11,23),(12,24),(23,24),
    (23,25),(25,27),(27,29),(27,31),(29,31),
    (24,26),(26,28),(28,30),(28,32),(30,32),
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),(9,10),
]

def draw_pose(frame, norm_lms, w, h):
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in norm_lms]
    for a, b in _SKEL_FULL:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], (70, 70, 70), 2, cv2.LINE_AA)
    for px, py in pts:
        cv2.circle(frame, (px, py), 4, (0, 200, 80), -1, cv2.LINE_AA)

# ── math ──────────────────────────────────────────────────────────────────────
def angle_3d(a, b, c):
    ba = a - b;  bc = c - b
    d  = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8
    return np.degrees(np.arccos(np.clip(np.dot(ba, bc) / d, -1.0, 1.0)))

def lm_xyz(wlms, i):
    lm = wlms[i];  return np.array([lm.x, lm.y, lm.z])

def lm_px(lms, i, w, h):
    lm = lms[i];  return (int(lm.x * w), int(lm.y * h))

def classify(v, t):
    if t["tight"][0] <= v <= t["tight"][1]: return "tight"
    if t["loose"][0] <= v <= t["loose"][1]: return "loose"
    return "out"

def status_color(s):
    return {"tight": C_GREEN, "loose": C_YELLOW, "out": C_RED}.get(s, C_GRAY)

def put(img, text, xy, scale=0.45, color=C_WHITE, thickness=1, font=FONT, bg=None):
    x, y = xy
    if bg is not None:
        (tw, th), bl = cv2.getTextSize(text, font, scale, thickness)
        cv2.rectangle(img, (x-2, y-th-2), (x+tw+2, y+bl+2), bg, -1)
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

def draw_arc(frame, pt_a, pt_b, pt_c, color, r=28, t=2):
    cx, cy = pt_b
    va = np.array(pt_a, float) - np.array(pt_b, float)
    vc = np.array(pt_c, float) - np.array(pt_b, float)
    if np.linalg.norm(va) < 1e-6 or np.linalg.norm(vc) < 1e-6: return
    aa = np.degrees(np.arctan2(va[1], va[0]))
    ac = np.degrees(np.arctan2(vc[1], vc[0]))
    diff = (ac - aa + 180) % 360 - 180
    s, e = sorted([aa, aa + diff])
    cv2.ellipse(frame, (cx, cy), (r, r), 0, s, e, color, t, cv2.LINE_AA)
    for ang in (aa, ac):
        p1 = (int(cx + (r-4)*np.cos(np.radians(ang))),
              int(cy + (r-4)*np.sin(np.radians(ang))))
        p2 = (int(cx + (r+4)*np.cos(np.radians(ang))),
              int(cy + (r+4)*np.sin(np.radians(ang))))
        cv2.line(frame, p1, p2, color, t, cv2.LINE_AA)

# ── model ─────────────────────────────────────────────────────────────────────
def ensure_model():
    if os.path.exists(MODEL_PATH):
        return
    print("  Downloading pose landmarker model (~9 MB)...")
    os.makedirs(REF_DIR, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"  Model saved -> {MODEL_PATH}")

# ── focus angles ──────────────────────────────────────────────────────────────
def get_focus_angles(move_name):
    if move_name in MOVE_ANGLE_FOCUS:
        return list(MOVE_ANGLE_FOCUS[move_name])
    base = move_name.rstrip("_0123456789")
    if base in MOVE_ANGLE_FOCUS:
        return list(MOVE_ANGLE_FOCUS[base])
    for key in MOVE_ANGLE_FOCUS:
        if move_name.startswith(key):
            return list(MOVE_ANGLE_FOCUS[key])
    return list(ALL_ANGLES)

# ── reference data ────────────────────────────────────────────────────────────
def load_move_reference(move_name, focus_angles):
    if os.path.exists(MP_REF_PATH):
        with open(MP_REF_PATH, encoding="utf-8") as f:
            mp_ref = json.load(f)
        stats = mp_ref.get("move_stats", {}).get(move_name, {})
        ref = {a: stats[a] for a in focus_angles if a in stats}
        if ref:
            return ref
        print("  WARNING: move not found in MP reference — falling back.")

    print("  NOTE: P3_mp_reference.json not found — using P3_angles.json.")
    if os.path.exists(ANGLES_PATH) and os.path.exists(LABELS_PATH):
        with open(ANGLES_PATH) as f:
            angles_data = json.load(f)
        with open(LABELS_PATH, encoding="utf-8") as f:
            labels_data = json.load(f)
        seg = next((s for s in labels_data["segments"]
                    if s["name"] == move_name), None)
        if seg:
            fs, fe = seg["frame_start"], seg["frame_end"]
            ref = {}
            for angle in focus_angles:
                if angle not in angles_data:
                    continue
                vals = np.array(angles_data[angle][fs:fe+1], dtype=float)
                if len(vals) == 0:
                    continue
                mean = float(np.mean(vals))
                std  = max(float(np.std(vals)), 1.0)
                ref[angle] = {
                    "mean":  mean, "std": std,
                    "tight": [mean - 1.0*std, mean + 1.0*std],
                    "loose": [mean - 1.5*std, mean + 1.5*std],
                }
            if ref:
                return ref

    thresh_path = os.path.join(REF_DIR, "thresholds.json")
    if not os.path.exists(thresh_path):
        sys.exit("  No reference data. Run build_mp_reference.py first.")
    with open(thresh_path) as f:
        all_thresh = json.load(f)
    return {a: all_thresh[a] for a in focus_angles if a in all_thresh}

# ══════════════════════════════════════════════════════════════════════════════
#  P3 REFERENCE VIDEO
# ══════════════════════════════════════════════════════════════════════════════

def find_p3_video():
    """Search common locations for the P3 professional reference video."""
    candidates = [
        os.path.join(BASE, "kata_reference", "Kata_P3_Left.avi"),
        os.path.join(BASE, "Kata_P3_Left.avi"),
        os.path.join(BASE, "..", "MADS_depth", "depth_data", "Kata", "Kata_P3_Left.avi"),
        os.path.join(BASE, "MADS_depth", "depth_data", "Kata", "Kata_P3_Left.avi"),
        os.path.join(BASE, "MADS_depth", "P3", "Left.avi"),
    ]
    for p in candidates:
        norm = os.path.normpath(p)
        if os.path.exists(norm):
            return norm
    return None


def _p3_video_frame_range(move_name, p3_total_frames):
    """
    Return (vid_start, vid_end) frame indices in the P3 video for a move.
    Uses video_frames from P3_mp_reference.json when available (most accurate).
    Falls back to scaling P3_labels.json GT frame indices.
    """
    # Preferred: video_frames already computed by build_mp_reference.py
    if os.path.exists(MP_REF_PATH):
        with open(MP_REF_PATH, encoding="utf-8") as f:
            mp_ref = json.load(f)
        stats = mp_ref.get("move_stats", {}).get(move_name, {})
        for angle_stats in stats.values():
            vf = angle_stats.get("video_frames")
            if vf and len(vf) == 2:
                return int(vf[0]), int(vf[1])

    # Fallback: scale GT frame indices
    if not os.path.exists(LABELS_PATH):
        return None, None
    with open(LABELS_PATH, encoding="utf-8") as f:
        labels_data = json.load(f)
    seg = next((s for s in labels_data["segments"] if s["name"] == move_name), None)
    if seg is None:
        return None, None
    gt_total = labels_data.get("total_frames", 816)
    scale = p3_total_frames / gt_total
    fs = max(0, int(seg["frame_start"] * scale))
    fe = min(p3_total_frames - 1, int(seg["frame_end"] * scale))
    return fs, fe


def precompute_ref_lms(p3_path, vid_start, vid_end):
    """
    Extract MediaPipe pose landmarks from P3 video for the given frame range.
    Uses IMAGE mode (stateless, no tracking between frames).
    Returns list of pose_landmarks[0] or None per sampled frame.
    """
    MAX_FRAMES = 60   # cap for responsiveness; still smooth when looped
    cap = cv2.VideoCapture(p3_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, vid_start)

    count = max(vid_end - vid_start + 1, 1)
    step  = max(1, count // MAX_FRAMES)

    ref_opts = PoseLandmarkerOpts(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )

    lms_list = []
    with PoseLandmarker.create_from_options(ref_opts) as lm_ref:
        for i in range(count):
            ok, frame = cap.read()
            if not ok:
                break
            if i % step != 0:
                continue
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = lm_ref.detect(mp_img)
            lms_list.append(result.pose_landmarks[0]
                            if result.pose_landmarks else None)
            if len(lms_list) % 10 == 0:
                print(".", end="", flush=True)

    cap.release()
    return lms_list

# ══════════════════════════════════════════════════════════════════════════════
#  SPLIT VIEW — HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _get_highlight_joints(focus_angles):
    """Return set of MediaPipe landmark indices involved in focus angles."""
    joints = set()
    for a in focus_angles:
        if a in MP_ANGLE_MAP:
            joints.update(MP_ANGLE_MAP[a])
    return joints


def _get_joint_colors(focus_angles, ref_stats, results_map):
    """
    Return dict: landmark_idx → color based on angle status.
    Red takes priority over yellow, yellow over green.
    """
    priority = {C_GREEN: 0, C_YELLOW: 1, C_RED: 2}
    colors = {}
    for a in focus_angles:
        if a not in MP_ANGLE_MAP:
            continue
        i, j, k = MP_ANGLE_MAP[a]
        if a in ref_stats and a in results_map:
            col = status_color(classify(results_map[a], ref_stats[a]))
        else:
            col = C_GRAY
        for idx in (i, j, k):
            if idx not in colors or priority.get(col, -1) > priority.get(colors[idx], -1):
                colors[idx] = col
    return colors


def _lms_to_px_ref(lms, pw=REF_W, ph=REF_H):
    """
    Map normalized landmarks to reference panel pixel coords.
    Applies 9% horizontal and 6% vertical margins so the skeleton
    stays away from panel edges.
    """
    mx, my = 0.09, 0.06
    sx, sy = 1.0 - 2*mx, 1.0 - 2*my
    return {i: (int((lm.x * sx + mx) * pw),
                int((lm.y * sy + my) * ph))
            for i, lm in enumerate(lms)}


def _draw_bones_px(canvas, pts, highlight_set, ref_mode=False, joint_colors=None):
    """
    Draw BONES_SPLIT skeleton using pixel-coordinate dict {idx: (x, y)}.

    ref_mode=True  → gray bones, GOLD highlights, BLUE joints
    ref_mode=False → dark bones, GOLD highlights, status-colored joints
    """
    if joint_colors is None:
        joint_colors = {}

    bone_normal = (150, 150, 150) if ref_mode else (55, 55, 55)

    for a, b in BONES_SPLIT:
        if a not in pts or b not in pts:
            continue
        in_hl = (a in highlight_set) and (b in highlight_set)
        cv2.line(canvas, pts[a], pts[b],
                 C_GOLD if in_hl else bone_normal,
                 3 if in_hl else (1 if ref_mode else 2),
                 cv2.LINE_AA)

    for idx, (px, py) in pts.items():
        in_hl = idx in highlight_set
        if in_hl:
            col = C_BLUE if ref_mode else joint_colors.get(idx, C_WHITE)
            r   = 6
        else:
            col = (90, 90, 90) if ref_mode else (40, 40, 40)
            r   = 3
        cv2.circle(canvas, (px, py), r, col, -1, cv2.LINE_AA)


def _build_ref_panel(p3_lms, ref_idx, focus_angles, move):
    """Build the left reference panel: black background + P3 skeleton."""
    panel = np.zeros((REF_H, REF_W, 3), dtype=np.uint8)

    # Header
    cv2.rectangle(panel, (0, 0), (REF_W, 44), C_HDRBG, -1)
    put(panel, "REFERENCE  Professional P3", (8, 18),
        font=FONTB, scale=0.50, color=C_GOLD)
    put(panel, move["name"].replace("_", " "), (8, 38), scale=0.40, color=C_WHITE)

    # Skeleton
    if p3_lms and 0 <= ref_idx < len(p3_lms) and p3_lms[ref_idx] is not None:
        hl  = _get_highlight_joints(focus_angles)
        pts = _lms_to_px_ref(p3_lms[ref_idx])
        _draw_bones_px(panel, pts, hl, ref_mode=True)
    else:
        msg = "Detecting..." if p3_lms else "No reference video"
        put(panel, msg, (REF_W//2 - 60, REF_H//2), scale=0.50, color=C_GRAY)

    # Legend: BLUE = joint, GOLD = highlighted bone
    cv2.line(panel, (0, REF_H - 28), (REF_W, REF_H - 28), C_HDRBG, 1)
    cv2.circle(panel, (12, REF_H - 12), 5, C_BLUE, -1, cv2.LINE_AA)
    put(panel, "= focus joint", (22, REF_H - 8), scale=0.32, color=C_GRAY)
    put(panel, move["japanese"], (REF_W - 70, REF_H - 8), scale=0.38, color=C_GOLD)
    return panel


def _build_trainee_split(frame, lms_img, w_orig, h_orig,
                          focus_angles, ref_stats, results_map, score):
    """Build the right trainee panel: resized video + skeleton + feedback overlay."""
    # Fit video in panel (letterbox)
    scale = min(REF_W / w_orig, REF_H / h_orig)
    nw    = int(w_orig * scale)
    nh    = int(h_orig * scale)
    xo    = (REF_W - nw) // 2
    yo    = (REF_H - nh) // 2

    panel = np.zeros((REF_H, REF_W, 3), dtype=np.uint8)
    panel[yo:yo+nh, xo:xo+nw] = cv2.resize(frame, (nw, nh))

    # Draw skeleton in panel coords
    if lms_img is not None:
        hl  = _get_highlight_joints(focus_angles)
        jc  = _get_joint_colors(focus_angles, ref_stats, results_map)
        pts = {i: (int(lm.x * w_orig * scale) + xo,
                   int(lm.y * h_orig * scale) + yo)
               for i, lm in enumerate(lms_img)}
        _draw_bones_px(panel, pts, hl, ref_mode=False, joint_colors=jc)
        # Angle arcs on highlighted joints
        for name in focus_angles:
            if name not in results_map or name not in ref_stats or name not in MP_ANGLE_MAP:
                continue
            i, j, k = MP_ANGLE_MAP[name]
            if any(x not in pts for x in (i, j, k)):
                continue
            col = status_color(classify(results_map[name], ref_stats[name]))
            draw_arc(panel, pts[i], pts[j], pts[k], col, r=24)

    # Header bar
    hdr = panel.copy()
    cv2.rectangle(hdr, (0, 0), (REF_W, 44), C_HDRBG, -1)
    cv2.addWeighted(hdr, 0.82, panel, 0.18, 0, panel)
    put(panel, "YOUR POSE", (8, 24), font=FONTB, scale=0.55, color=C_ORANGE)

    # Feedback overlay (top-right corner)
    _draw_feedback_overlay(panel, focus_angles, ref_stats, results_map, score)
    return panel


def _draw_feedback_overlay(panel, focus_angles, ref_stats, results_map, score):
    """Semi-transparent angle correction overlay in the top-right of the panel."""
    lines = []
    for a in focus_angles[:5]:
        if a not in ref_stats:
            continue
        meas = results_map.get(a)
        if meas is not None:
            st  = classify(meas, ref_stats[a])
            col = status_color(st)
            sym = "OK" if st == "tight" else "!!" if st == "loose" else "XX"
            lines.append((f"[{sym}] {a.replace('_',' ')[:12]}: {meas:.0f}", col))
            if st != "tight":
                lo, _ = ref_stats[a]["tight"]
                hint  = HINTS.get(a, ("", ""))[0 if meas < lo else 1]
                lines.append((f"  {hint[:18]}", col))
        else:
            lines.append((f"--- {a.replace('_',' ')[:12]}", C_GRAY))

    if not lines:
        return

    n_lines = len(lines)
    box_h   = 12 + n_lines * 17 + 6
    box_x   = REF_W - 220
    box_y   = 46

    sub = panel[box_y:box_y+box_h, box_x-4:REF_W-4]
    if sub.size == 0:
        return
    dark = np.full_like(sub, 18)
    cv2.addWeighted(dark, 0.68, sub, 0.32, 0, sub)
    panel[box_y:box_y+box_h, box_x-4:REF_W-4] = sub

    y = box_y + 14
    for text, col in lines:
        put(panel, text, (box_x, y), scale=0.36, color=col)
        y += 17


def _build_split_bbar(move, move_idx, n_moves, frame_idx, total_frames,
                       fps, paused, score, is_camera, show_ref):
    """Build the 80px bottom bar for the split window."""
    bar       = np.full((BBAR_H, WIN_W, 3), C_DARK, dtype=np.uint8)
    score_col = C_GREEN if score >= 75 else C_YELLOW if score >= 50 else C_RED

    # Row 1 — left label, center move name, right score
    left_lbl = "REFERENCE  P3 Professional" if show_ref else "SINGLE VIEW  (T = show ref)"
    put(bar, left_lbl, (8, 17), scale=0.38,
        color=C_GOLD if show_ref else C_GRAY)

    center = f"Move {move_idx}/{n_moves}  {move['name'].replace('_',' ')}  {move['japanese']}"
    (tw, _), _ = cv2.getTextSize(center, FONT, 0.42, 1)
    put(bar, center, ((WIN_W - tw) // 2, 17), scale=0.42, color=C_WHITE)

    score_txt = f"SCORE: {score:.0f}%"
    (tw2, _), _ = cv2.getTextSize(score_txt, FONTB, 0.52, 1)
    put(bar, score_txt, (WIN_W - tw2 - 10, 19), scale=0.52,
        color=score_col, font=FONTB)

    # Row 2 — progress bar (video) or LIVE dot (camera)
    if is_camera:
        put(bar, " LIVE", (8, 40), scale=0.46, color=C_RED)
    else:
        cur = frame_idx / max(fps, 1)
        tot = max(total_frames, 1) / max(fps, 1)
        tstr = f"{int(cur//60):02d}:{int(cur%60):02d} / {int(tot//60):02d}:{int(tot%60):02d}"
        (tw3, _), _ = cv2.getTextSize(tstr, FONT, 0.38, 1)
        BX0, BX1, BY0, BY1 = 8, WIN_W - tw3 - 14, 26, 40
        cv2.rectangle(bar, (BX0, BY0), (BX1, BY1), (45, 45, 65), -1)
        if total_frames > 0:
            fill = int((BX1 - BX0) * frame_idx / total_frames)
            cv2.rectangle(bar, (BX0, BY0), (BX0+fill, BY1), C_ORANGE, -1)
            cv2.rectangle(bar, (BX0+fill, BY0-1), (BX0+fill+3, BY1+1), C_WHITE, -1)
        put(bar, tstr, (WIN_W - tw3 - 8, 40), scale=0.38, color=C_GRAY)
        if paused:
            put(bar, "|| PAUSED", (BX0 + 4, 39), scale=0.36, color=C_YELLOW)

    # Row 3 — score bar
    SX0, SX1 = 8, WIN_W - 12
    cv2.rectangle(bar, (SX0, 48), (SX1, 60), (45, 45, 65), -1)
    fw = int((SX1 - SX0) * score / 100)
    cv2.rectangle(bar, (SX0, 48), (SX0+fw, 60), score_col, -1)

    # Row 4 — controls
    ctrl = ("SPACE=pause  LEFT/RIGHT=+/-30f  R=restart  "
            "N=next  S=shot  T=ref toggle  Q=quit")
    if is_camera:
        ctrl = "N=next move   S=screenshot   T=toggle ref   Q=quit"
    put(bar, ctrl, (8, BBAR_H - 6), scale=0.29, color=C_GRAY)

    return bar

# ══════════════════════════════════════════════════════════════════════════════
#  SINGLE-MODE PANELS  (used when T=off, same 1164×720 window)
# ══════════════════════════════════════════════════════════════════════════════

def build_info_panel(h, move, focus_angles, ref_stats, results_map, is_camera=False):
    panel = np.full((h, PANEL_W, 3), C_PANEL, dtype=np.uint8)

    cv2.rectangle(panel, (0, 0), (PANEL_W, 52), C_HDRBG, -1)
    put(panel, "KARATE KATA CORRECTOR", (8, 18), font=FONTB, scale=0.50, color=C_ORANGE)
    put(panel, f"Technique: {move['name'].replace('_', ' ')}",
        (8, 38), scale=0.42, color=C_WHITE)

    y = 64
    put(panel, "ANGLES", (8, y), scale=0.40, color=C_GRAY)
    cv2.line(panel, (8, y+5), (PANEL_W-8, y+5), C_HDRBG, 1)
    y += 18

    for angle in focus_angles:
        if angle not in ref_stats or y > h - 44:
            break
        ref  = ref_stats[angle]
        meas = results_map.get(angle)

        if meas is not None:
            status  = classify(meas, ref)
            sq_col  = status_color(status)
            val_str = f"{meas:.0f}"
        else:
            status  = "none"
            sq_col  = C_GRAY
            val_str = "--"

        cv2.rectangle(panel, (8, y-10), (18, y-1), sq_col, -1)
        put(panel, f"{angle.replace('_', ' ')}: {val_str}",
            (22, y), scale=0.42, color=C_WHITE if meas is not None else C_GRAY)
        y += 15
        put(panel, f"  target: {ref['mean']:.0f}", (22, y), scale=0.35, color=C_GRAY)
        y += 13
        if meas is not None and status != "tight":
            lo, _ = ref["tight"]
            hint = HINTS[angle][0] if meas < lo else HINTS[angle][1]
            put(panel, f"  {hint}", (22, y), scale=0.33, color=sq_col)
            y += 13
        y += 6

    cv2.line(panel, (0, h-28), (PANEL_W, h-28), C_HDRBG, 1)
    if is_camera:
        put(panel, "N=next  S=shot  T=ref  Q=quit", (6, h-10), scale=0.31, color=C_GRAY)
    else:
        put(panel, "SPC  N=next  T=ref  Q=quit", (6, h-10), scale=0.31, color=C_GRAY)
    return panel

# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL MENUS
# ══════════════════════════════════════════════════════════════════════════════

def select_input_mode():
    W = 40;  B = "  "
    print()
    print(B + "╔" + "═"*W + "╗")
    print(B + "║" + "  KARATE KATA CORRECTOR".ljust(W) + "║")
    print(B + "╠" + "═"*W + "╣")
    print(B + "║" + "  Select input mode:".ljust(W) + "║")
    print(B + "║" + "  1. Live camera (webcam)".ljust(W) + "║")
    print(B + "║" + "  2. Upload a video file".ljust(W) + "║")
    print(B + "╚" + "═"*W + "╝")
    print()
    while True:
        try:
            n = int(input("  Enter choice (1 or 2): ").strip())
            if n in (1, 2):
                return n
        except (ValueError, EOFError):
            pass
        print("  Please enter 1 or 2.")


def select_technique():
    W = 46;  B = "  "
    print()
    print(B + "╔" + "═"*W + "╗")
    print(B + "║" + "  Select a technique to practice:".ljust(W) + "║")
    print(B + "╠" + "═"*W + "╣")
    for m in BASSAI_DAI_MOVES:
        line = f"  {m['move_id']:2d}.  {m['name']:<24} {m['japanese']}"
        print(B + "║" + line.ljust(W) + "║")
    print(B + "╚" + "═"*W + "╝")
    print()
    while True:
        try:
            n = int(input("  Enter number (1-17): ").strip())
            if 1 <= n <= len(BASSAI_DAI_MOVES):
                return n - 1
        except (ValueError, EOFError):
            pass
        print(f"  Please enter a number between 1 and {len(BASSAI_DAI_MOVES)}.")


def get_video_path():
    print()
    print("  Enter video path (drag & drop): ", end="", flush=True)
    path = input().strip().strip('"').strip("'")
    if not os.path.exists(path):
        sys.exit(f"\n  File not found: {path}")
    return path

# ══════════════════════════════════════════════════════════════════════════════
#  REPORT
# ══════════════════════════════════════════════════════════════════════════════

def print_report(move, focus_angles, ref_stats, angle_frames, frame_scores,
                 auto_save=False):
    overall = float(np.mean(frame_scores)) if frame_scores else 0.0
    grade   = "Excellent" if overall >= 75 else "Good" if overall >= 50 else "Needs work"
    g_sym   = "OK"        if overall >= 75 else "!!"   if overall >= 50 else "XX"

    angle_stats = {}
    for a in focus_angles:
        vals = angle_frames.get(a, [])
        if not vals or a not in ref_stats:
            continue
        avg    = float(np.mean(vals))
        target = ref_stats[a]["mean"]
        diff   = avg - target
        status = classify(avg, ref_stats[a])
        sym    = "OK" if status == "tight" else "!!" if status == "loose" else "XX"
        lo, _  = ref_stats[a]["tight"]
        hint   = HINTS.get(a, ("adjust", "adjust"))[0 if avg < lo else 1]
        angle_stats[a] = dict(avg=avg, target=target, diff=diff,
                              status=status, sym=sym, hint=hint)

    corrections = sorted(
        [(a, s) for a, s in angle_stats.items() if s["status"] != "tight"],
        key=lambda x: abs(x[1]["diff"]), reverse=True
    )

    W = 50;  B = "  "
    def row(t): return B + "║" + t.ljust(W) + "║"
    sep = B + "╠" + "═"*W + "╣"

    print()
    print(B + "╔" + "═"*W + "╗")
    print(row(f"  EVALUATION REPORT — {move['name']}"))
    print(sep)
    print(row(f"  Overall Score:   {overall:.0f}%   [{g_sym}] {grade}"))
    print(sep)
    for a, s in angle_stats.items():
        sign = "+" if s["diff"] >= 0 else ""
        print(row(f"  {a:<16} [{s['sym']}]  avg {s['avg']:.0f}   "
                  f"target {s['target']:.0f}   ({sign}{s['diff']:.0f})"))
    print(sep)
    if corrections:
        print(row("  TOP CORRECTIONS:"))
        for rank, (a, s) in enumerate(corrections[:3], 1):
            sign = "+" if s["diff"] >= 0 else ""
            print(row(f"  {rank}. {s['hint'].capitalize()}"))
            print(row(f"     ({s['avg']:.0f} avg vs {s['target']:.0f} target,"
                      f" {sign}{s['diff']:.0f})"))
    else:
        print(row("  All angles within target range — great work!"))
    print(B + "╚" + "═"*W + "╝")
    print()

    if auto_save:
        answer = "y"
        print("  Auto-saving report...")
    else:
        try:
            answer = input("  Save report? (y/n): ").strip().lower()
        except EOFError:
            answer = "n"

    if answer == "y":
        _save_report(move, angle_stats, corrections, overall, grade)


def _save_report(move, angle_stats, corrections, overall, grade):
    os.makedirs(SESS_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y-%m-%d_%H-%M")
    stem = os.path.join(SESS_DIR, f"{move['name']}_{ts}")

    data = {
        "date":          datetime.now().isoformat(),
        "technique":     move["name"],
        "japanese":      move["japanese"],
        "overall_score": round(overall, 1),
        "grade":         grade,
        "angles": {
            a: {"avg":    round(s["avg"], 1),
                "target": round(s["target"], 1),
                "diff":   round(s["diff"], 1),
                "status": s["status"]}
            for a, s in angle_stats.items()
        },
        "corrections": [
            {"angle": a, "hint": s["hint"],
             "avg":   round(s["avg"], 1), "target": round(s["target"], 1)}
            for a, s in corrections[:3]
        ],
    }
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    txt = [
        "KARATE KATA CORRECTOR — EVALUATION REPORT",
        f"Date      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Technique : {move['name']}  ({move['japanese']})",
        f"Overall   : {overall:.1f}%  [{grade}]", "",
        f"{'Angle':<18} {'Stat':<6} {'Avg':>5}   {'Target':>6}   {'Diff':>6}",
        "-" * 52,
    ]
    for a, s in angle_stats.items():
        sign = "+" if s["diff"] >= 0 else ""
        txt.append(f"{a:<18} [{s['sym']}]  {s['avg']:>5.0f}   "
                   f"{s['target']:>6.0f}   {sign}{s['diff']:>5.0f}")
    txt += ["", "TOP CORRECTIONS:"]
    for rank, (a, s) in enumerate(corrections[:3], 1):
        sign = "+" if s["diff"] >= 0 else ""
        txt += [f"  {rank}. {s['hint'].capitalize()}",
                f"     ({s['avg']:.0f} avg vs {s['target']:.0f} target,"
                f" {sign}{s['diff']:.0f})"]

    with open(stem + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(txt))

    print(f"\n  Saved  ->  {stem}.json")
    print(f"         ->  {stem}.txt")

# ══════════════════════════════════════════════════════════════════════════════
#  CORE SESSION LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_session(cap, move, move_idx, n_moves, focus_angles, ref_stats,
                landmarker, is_camera, total_frames=0, fps=30.0,
                p3_lms=None, auto_save=False):
    """
    Run the pose-analysis loop for one technique.

    p3_lms  — list of P3 reference landmarks (or None for single view only)

    Returns 'next' if N was pressed, 'quit' otherwise.
    """
    delay      = max(1, int(1000 / fps))
    ts_counter = int(time.time() * 1000) if is_camera else 0
    session_t0 = time.time()

    angle_frames  = {a: [] for a in focus_angles}
    frame_scores  = []
    running_score = 0.0
    results_map   = {}
    lms_img_last  = None

    paused       = False
    frame        = None
    last_view    = None
    frame_idx    = 0
    cam_frames   = 0
    need_redraw  = True
    signal       = "quit"
    show_ref     = (p3_lms is not None)

    os.makedirs(SCR_DIR,  exist_ok=True)
    os.makedirs(SESS_DIR, exist_ok=True)

    while True:
        # ── advance frame ─────────────────────────────────────────────────────
        if not paused:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx  = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            cam_frames += 1
            need_redraw = True

        # ── MediaPipe inference ───────────────────────────────────────────────
        if need_redraw and frame is not None:
            h, w = frame.shape[:2]
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            if is_camera:
                ts_counter = int(time.time() * 1000)
            else:
                ts_counter += 1

            result = landmarker.detect_for_video(mp_img, ts_counter)

            if result.pose_landmarks and result.pose_world_landmarks:
                lms_img_last = result.pose_landmarks[0]
                lms_world    = result.pose_world_landmarks[0]

                results_map = {}
                for name, (i, j, k) in MP_ANGLE_MAP.items():
                    try:
                        results_map[name] = angle_3d(
                            lm_xyz(lms_world, i),
                            lm_xyz(lms_world, j),
                            lm_xyz(lms_world, k))
                    except Exception:
                        pass

                relevant = [a for a in focus_angles
                            if a in results_map and a in ref_stats]
                if relevant:
                    for a in relevant:
                        angle_frames[a].append(results_map[a])
                    n_ok = sum(classify(results_map[a], ref_stats[a])
                               in ("tight", "loose") for a in relevant)
                    frame_scores.append(n_ok / len(relevant) * 100)
                    running_score = float(np.mean(frame_scores))
            else:
                lms_img_last = None

            # ── compute reference frame index ─────────────────────────────────
            if p3_lms:
                n_ref = max(len(p3_lms), 1)
                if is_camera:
                    # Play reference at P3's natural 15fps
                    elapsed = time.time() - session_t0
                    ref_idx = int(elapsed * P3_FPS) % n_ref
                else:
                    # Proportional sync to trainee video position
                    progress = frame_idx / max(total_frames, 1)
                    ref_idx  = min(int(progress * n_ref), n_ref - 1)
            else:
                ref_idx = 0

            # ── build composite view ──────────────────────────────────────────
            if show_ref and p3_lms:
                ref_panel = _build_ref_panel(p3_lms, ref_idx, focus_angles, move)
                tr_panel  = _build_trainee_split(
                    frame, lms_img_last, w, h,
                    focus_angles, ref_stats, results_map, running_score)
                divider   = np.full((REF_H, DIV_W, 3), 200, dtype=np.uint8)
                top       = np.hstack([ref_panel, divider, tr_panel])
            else:
                # Single mode — trainee video + info panel at full 1164 width
                frame_draw = frame.copy()
                if lms_img_last is not None:
                    draw_pose(frame_draw, lms_img_last, w, h)
                    for name in focus_angles:
                        if name not in results_map or name not in ref_stats:
                            continue
                        if name not in MP_ANGLE_MAP:
                            continue
                        i, j, k = MP_ANGLE_MAP[name]
                        col = status_color(classify(results_map[name], ref_stats[name]))
                        draw_arc(frame_draw,
                                 lm_px(lms_img_last, i, w, h),
                                 lm_px(lms_img_last, j, w, h),
                                 lm_px(lms_img_last, k, w, h), col)
                # Fit video in (WIN_W - PANEL_W) × REF_H
                vid_w = WIN_W - PANEL_W
                scale = min(vid_w / w, REF_H / h)
                nw, nh = int(w * scale), int(h * scale)
                xo, yo = (vid_w - nw) // 2, (REF_H - nh) // 2
                vid_area = np.zeros((REF_H, vid_w, 3), dtype=np.uint8)
                vid_area[yo:yo+nh, xo:xo+nw] = cv2.resize(frame_draw, (nw, nh))
                info  = build_info_panel(REF_H, move, focus_angles, ref_stats,
                                         results_map, is_camera)
                top   = np.hstack([vid_area, info])

            bbar     = _build_split_bbar(move, move_idx, n_moves, frame_idx,
                                          total_frames, fps, paused,
                                          running_score, is_camera, show_ref)
            last_view = np.vstack([top, bbar])
            need_redraw = False

        # ── display ───────────────────────────────────────────────────────────
        if last_view is not None:
            cv2.imshow("Kata Corrector", last_view)

        # ── key handling ──────────────────────────────────────────────────────
        wait = delay if not paused else 30
        key  = cv2.waitKey(wait) & 0xFF

        if key == ord("q"):
            signal = "quit";  break

        elif key == ord("n"):
            signal = "next";  break

        elif key == ord("t"):
            if p3_lms:
                show_ref = not show_ref
                need_redraw = True

        elif key == ord("s"):
            if last_view is not None:
                ts_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                fname  = os.path.join(SCR_DIR, f"screenshot_{ts_str}.jpg")
                cv2.imwrite(fname, last_view)
                print(f"  Screenshot -> {fname}")

        elif not is_camera:
            if key == ord(" "):
                paused = not paused

            elif key == 83:   # RIGHT +30 frames
                target = min(frame_idx + 30, max(total_frames - 1, 0))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                ok, frame = cap.read()
                if ok:
                    frame_idx = target;  need_redraw = True

            elif key == 81:   # LEFT -30 frames
                target = max(frame_idx - 30, 0)
                cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                ok, frame = cap.read()
                if ok:
                    frame_idx = target;  need_redraw = True

            elif key == ord("r"):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx     = 0
                paused        = False
                need_redraw   = True
                angle_frames  = {a: [] for a in focus_angles}
                frame_scores  = []
                running_score = 0.0

    cv2.destroyAllWindows()
    print_report(move, focus_angles, ref_stats, angle_frames, frame_scores,
                 auto_save=(auto_save or signal == "next"))
    return signal

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Karate Kata Corrector")
    parser.add_argument("--mode",  type=int, default=None,
                        help="1=camera  2=video  (skips mode menu)")
    parser.add_argument("--move",  type=int, default=None,
                        help="Technique number 1-17  (skips technique menu)")
    parser.add_argument("--video", type=str, default=None,
                        help="Path to video file  (skips path prompt)")
    parser.add_argument("--save",  action="store_true",
                        help="Auto-save reports without prompting")
    args = parser.parse_args()

    # ── mode selection ────────────────────────────────────────────────────────
    mode      = args.mode if args.mode in (1, 2) else select_input_mode()
    is_camera = (mode == 1)

    # ── video path ────────────────────────────────────────────────────────────
    video_path = None
    if not is_camera:
        if args.video and os.path.exists(args.video):
            video_path = args.video
            print(f"\n  Video: {os.path.basename(video_path)}")
        else:
            video_path = get_video_path()

    # ── starting technique ────────────────────────────────────────────────────
    if args.move and 1 <= args.move <= len(BASSAI_DAI_MOVES):
        move_idx = args.move - 1
    else:
        move_idx = select_technique()

    # ── locate P3 reference video ─────────────────────────────────────────────
    p3_path = find_p3_video()
    if p3_path:
        print(f"\n  Reference video: {os.path.basename(p3_path)}")
        p3_cap_check = cv2.VideoCapture(p3_path)
        p3_total_frames = int(p3_cap_check.get(cv2.CAP_PROP_FRAME_COUNT))
        p3_cap_check.release()
    else:
        print("\n  Reference video not found — running in single view mode.")
        print("  (Place Kata_P3_Left.avi in kata_reference\\ to enable split view)")
        p3_total_frames = 0

    # ── load model once ───────────────────────────────────────────────────────
    ensure_model()

    options = PoseLandmarkerOpts(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    # ── open trainee capture source ───────────────────────────────────────────
    if is_camera:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            sys.exit("\n  Cannot open webcam. Is a camera connected?")
        total_frames = 0
        fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
        print(f"\n  Webcam opened.  FPS: {fps:.1f}")
    else:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            sys.exit(f"\n  Cannot open: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
        print(f"\n  Video  : {os.path.basename(video_path)}")
        print(f"  Frames : {total_frames}  |  FPS: {fps:.1f}  |  "
              f"Duration: {total_frames/fps:.1f}s")

    n_moves = len(BASSAI_DAI_MOVES)

    # ── move loop ─────────────────────────────────────────────────────────────
    with PoseLandmarker.create_from_options(options) as landmarker:
        while move_idx < n_moves:
            move         = BASSAI_DAI_MOVES[move_idx]
            focus_angles = get_focus_angles(move["name"])

            print(f"\n  Technique : {move['name']}  ({move['japanese']})")
            print(f"  Focus     : {', '.join(focus_angles)}")

            print(f"\n  Loading reference data...", end="", flush=True)
            ref_stats = load_move_reference(move["name"], focus_angles)
            print(f" {len(ref_stats)} angle(s) loaded.")

            # ── precompute P3 reference landmarks for this move ───────────────
            p3_lms = None
            if p3_path and p3_total_frames > 0:
                fs, fe = _p3_video_frame_range(move["name"], p3_total_frames)
                if fs is not None and fe > fs:
                    n_ref_frames = fe - fs + 1
                    print(f"  Pre-loading P3 reference frames {fs}-{fe}"
                          f"  ({n_ref_frames} frames)", end="", flush=True)
                    p3_lms = precompute_ref_lms(p3_path, fs, fe)
                    good   = sum(1 for x in p3_lms if x is not None)
                    print(f"  {good}/{len(p3_lms)} detected.")
                    if good == 0:
                        print("  WARNING: No poses detected in P3 frames — "
                              "falling back to single view.")
                        p3_lms = None
                else:
                    print("  No P3 frame range for this move — single view.")

            mode_tag = "split view" if p3_lms else "single view"
            print(f"\n  Opening window ({mode_tag})...  "
                  f"Q=quit  N=next  T=toggle ref  S=screenshot\n")

            signal = run_session(
                cap, move, move_idx + 1, n_moves,
                focus_angles, ref_stats, landmarker,
                is_camera, total_frames, fps,
                p3_lms=p3_lms, auto_save=args.save
            )

            if signal == "next":
                move_idx += 1
                if move_idx >= n_moves:
                    print("\n  All techniques complete!")
                    break
                nxt = BASSAI_DAI_MOVES[move_idx]
                print(f"\n  Advancing to move {move_idx + 1}: "
                      f"{nxt['name']}  ({nxt['japanese']})")
                if not is_camera:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
