# -*- coding: utf-8 -*-
r"""
REALTIME_TEST_ALL_MODELS.PY
───────────────────────────
Runs all models in REAL-TIME using a 30-frame sliding window.
Displays a continuous video feed with a live dashboard showing 
all 7 models' predictions simultaneously.

Run:
    python test_all_models.py --video "path\to\video.mp4"
"""

import sys, os, argparse, pickle
import collections
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Default paths ─────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_ENSEMBLE_DIR = os.path.join(BASE, "models")
DEFAULT_KERAS_DIR    = r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\app\models\Results\Production_Best"

# ── Shared constants ──────────────────────────────────────────────────────────
SEQ_LEN     = 30
KERAS_CLS   = ["GedanBarai", "Gyakudzuki", "MaeGeri"]
WEIGHTS = {"XGBoost": 0.35, "SVM": 0.30, "RF": 0.25, "KNN": 0.10}
VIS_JOINTS = {0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28}

# ── Feature column definitions ────────────────────────────────────────────────
UPPER_COORDS = [f"{c}{i}" for i in range(11, 23) for c in ["x", "y", "z", "v"]]
UPPER_ANGLES = [f"angle_{i:02d}" for i in range(8, 14)]
UPPER_FEATS  = UPPER_COORDS + UPPER_ANGLES   # 54

LOWER_COORDS = [f"{c}{i}" for i in range(23, 33) for c in ["x", "y", "z", "v"]]
LOWER_ANGLES = [f"angle_{i:02d}" for i in range(0, 8)]
LOWER_FEATS  = LOWER_COORDS + LOWER_ANGLES   # 48

ALL_FEATS    = UPPER_FEATS + LOWER_FEATS     # 102

ANGLE_TRIPLETS = [
    (23, 25, 27), (24, 26, 28), (11, 23, 25), (12, 24, 26), 
    (25, 27, 29), (26, 28, 30), (23, 24, 26), (24, 23, 25), 
    (11, 13, 15), (12, 14, 16), (13, 11, 23), (14, 12, 24), 
    (15, 13, 11), (16, 14, 12),                              
]

ENSEMBLE_ANGLES = {
    "right_elbow":    (12, 14, 16), "left_elbow":     (11, 13, 15),
    "right_shoulder": (14, 12, 24), "left_shoulder":  (13, 11, 23),
    "right_knee":     (24, 26, 28), "left_knee":      (23, 25, 27),
    "right_hip":      (12, 24, 26), "left_hip":       (11, 23, 25),
    "spine_lean":     (0,  23, 25),
}
ENSEMBLE_ANGLE_NAMES = list(ENSEMBLE_ANGLES.keys())

# ── Math helpers ──────────────────────────────────────────────────────────────
def angle_2d(a, b, c):
    ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
    bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
    d  = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8
    return float(np.degrees(np.arccos(np.clip(np.dot(ba, bc) / d, -1.0, 1.0))))

def compute_ensemble_features(angles_list):
    arr = np.array(angles_list, dtype=float)
    if arr.ndim == 1: arr = arr.reshape(1, -1)
    if arr.shape[0] < 2: arr = np.vstack([arr, arr])
    features = []
    for col in range(arr.shape[1]):
        v = arr[:, col]
        features.extend([float(np.mean(v)), float(np.std(v)), float(np.min(v)), float(np.max(v))])
    for col in range(arr.shape[1]): features.append(float(np.mean(np.abs(np.diff(arr[:, col])))))
    for col in range(arr.shape[1]): features.append(float(np.max(np.abs(arr[:, col]))))
    return np.array(features, dtype=float)

# ── MediaPipe ─────────────────────────────────────────────────────────────────
def init_mediapipe(mp_path):
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision as mp_vision
    opts = mp_vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=mp_path),
        running_mode=mp_vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
    )
    return mp_vision.PoseLandmarker.create_from_options(opts), mp

# ── Load models ───────────────────────────────────────────────────────────────
def load_ensemble(ensemble_dir):
    files = {"KNN": "model_knn.pkl", "SVM": "model_svm.pkl", "RF": "model_rf.pkl", "XGBoost": "model_xgb.pkl"}
    models = {}
    for key, fname in files.items():
        with open(os.path.join(ensemble_dir, fname), "rb") as f: models[key] = pickle.load(f)
    with open(os.path.join(ensemble_dir, "scaler.pkl"), "rb") as f: scaler = pickle.load(f)
    with open(os.path.join(ensemble_dir, "label_encoder.pkl"), "rb") as f: le = pickle.load(f)
    return models, scaler, le

def load_keras(keras_dir):
    from tensorflow import keras as tf_keras
    
    # Updated to match your exact filenames in Production_Best!
    dual = tf_keras.models.load_model(os.path.join(keras_dir, "best_dual_stem_fusion.keras"))
    single_v1 = tf_keras.models.load_model(os.path.join(keras_dir, "best_single_bilstmV1.keras"))
    single_v2 = tf_keras.models.load_model(os.path.join(keras_dir, "best_single_bilstmV2.keras")) 
    
    return dual, single_v1, single_v2
# ── Real-Time Inference Helpers ───────────────────────────────────────────────
def predict_ensemble_window(window, models, scaler, le):
    fvec = compute_ensemble_features(window)
    X = scaler.transform(fvec.reshape(1, -1))
    results = {}
    for mname, clf in models.items():
        if hasattr(clf, "predict_proba"):
            probs = clf.predict_proba(X)[0]
            idx = int(np.argmax(probs))
            results[mname] = (le.classes_[idx], probs[idx])
        else:
            idx = int(clf.predict(X)[0])
            results[mname] = (le.classes_[idx], 1.0)
    return results

def predict_keras_window(seq_102, dual_model, sing_v1, sing_v2):
    seq = np.array(seq_102, dtype=np.float32)
    upper_idx = [ALL_FEATS.index(f) for f in UPPER_FEATS]
    lower_idx = [ALL_FEATS.index(f) for f in LOWER_FEATS]
    
    X_u = seq[:, upper_idx][np.newaxis]
    X_l = seq[:, lower_idx][np.newaxis]
    
    p_dual = dual_model.predict([X_u, X_l], verbose=0)[0]
    p_v1 = sing_v1.predict(seq[np.newaxis], verbose=0)[0]
    p_v2 = sing_v2.predict(seq[np.newaxis], verbose=0)[0]
    
    return {
        "Dual-Stem": (KERAS_CLS[np.argmax(p_dual)], np.max(p_dual)),
        "Single_V1": (KERAS_CLS[np.argmax(p_v1)], np.max(p_v1)),
        "Single_V2": (KERAS_CLS[np.argmax(p_v2)], np.max(p_v2))
    }

# ── Visualization ─────────────────────────────────────────────────────────────
def draw_dashboard(frame, predictions):
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, 320), (15, 15, 20), -1)
    frame = cv2.addWeighted(overlay, 0.75, frame, 0.25, 0)
    
    cv2.putText(frame, "LIVE KATA ANALYSIS", (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    y = 80
    for category, (move, conf) in predictions.items():
        # Color coding: Green for high conf, Yellow for med, Red for low
        color = (0, 255, 0) if conf > 0.85 else ((0, 200, 255) if conf > 0.6 else (0, 0, 255))
        
        text = f"{category:<12}: {move} ({conf*100:.0f}%)"
        cv2.putText(frame, text, (25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
        y += 30
        if category == "KNN": y += 15 # Add a gap between Ensemble and Keras
        
    return frame

# ── Main Real-Time Loop ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, default=None)
    args = parser.parse_args()

    print("Loading Models...")
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    ens_models, scaler, le = load_ensemble(DEFAULT_ENSEMBLE_DIR)
    dual_model, single_v1, single_v2 = load_keras(DEFAULT_KERAS_DIR)
    
    mp_path = os.path.join(BASE, "pose_landmarker_full.task")
    if not os.path.exists(mp_path): mp_path = input("Path to pose_landmarker_full.task: ").strip('"')
    landmarker, mp_mod = init_mediapipe(mp_path)
    mp_drawing = mp_mod.solutions.drawing_utils
    mp_pose = mp_mod.solutions.pose

    video_path = args.video if args.video else input("Enter video path: ").strip('"')
    cap = cv2.VideoCapture(video_path)
    
    # ── THE SLIDING WINDOWS ──
    ens_buffer = collections.deque(maxlen=SEQ_LEN)
    keras_buffer = collections.deque(maxlen=SEQ_LEN)
    current_predictions = {"Waiting...": ("Fill Buffer", 0.0)}

    print("\nStarting Real-Time Analysis... Press 'q' to quit window.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        # Resize for consistent viewing if the video is massive
        height, width = frame.shape[:2]
        if width > 1280: frame = cv2.resize(frame, (1280, int(height * (1280/width))))

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp_mod.Image(image_format=mp_mod.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_img)
        
        if result.pose_landmarks and len(result.pose_landmarks[0]) >= 29:
            lm = result.pose_landmarks[0]
            
            # Draw Skeleton for the presentation visual
            annotated_rgb = rgb.copy()
            
            # Convert MediaPipe Tasks output back to Protobuf so the drawing utility can read it
            from mediapipe.framework.formats import landmark_pb2
            proto_landmarks = landmark_pb2.NormalizedLandmarkList()
            proto_landmarks.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=l.x, y=l.y, z=l.z, visibility=l.visibility) 
                for l in lm
            ])
            
            mp_drawing.draw_landmarks(annotated_rgb, proto_landmarks, mp_pose.POSE_CONNECTIONS)
            frame = cv2.cvtColor(annotated_rgb, cv2.COLOR_RGB2BGR)

            # 1. Ensemble Feature Extraction
            pts_2d = [(l.x, l.y) for l in lm]
            ens_row = [angle_2d(pts_2d[i], pts_2d[j], pts_2d[k]) if (i<len(pts_2d) and j<len(pts_2d) and k<len(pts_2d)) else 0.0 
                       for name in ENSEMBLE_ANGLE_NAMES for i, j, k in [ENSEMBLE_ANGLES[name]]]
            ens_buffer.append(ens_row)

            # 2. Keras Feature Extraction
            raw_coords = np.array([[l.x, l.y, l.z, l.visibility] for l in lm[:33]])
            # Mid-Hip Fix
            mid_hip = (raw_coords[23, :3] + raw_coords[24, :3]) / 2.0
            raw_coords[:, :3] -= mid_hip
            # Shoulder Scale
            shoulder_dist = np.linalg.norm(raw_coords[11, :2] - raw_coords[12, :2]) + 1e-6
            raw_coords[:, :3] /= shoulder_dist
            
            row_dict = {f"{c}{i}": raw_coords[i, j] for i in range(11, 33) for j, c in enumerate(['x','y','z','v'])}
            for idx, (ai, bi, ci) in enumerate(ANGLE_TRIPLETS):
                row_dict[f"angle_{idx:02d}"] = (angle_2d(raw_coords[ai, :2], raw_coords[bi, :2], raw_coords[ci, :2]) / 180.0) if ai<33 and bi<33 and ci<33 else 0.0
            keras_buffer.append([row_dict.get(f, 0.0) for f in ALL_FEATS])

            # ── TRIGGER PREDICTION WHEN WINDOW IS FULL ──
            if len(keras_buffer) == SEQ_LEN:
                ens_preds = predict_ensemble_window(ens_buffer, ens_models, scaler, le)
                keras_preds = predict_keras_window(keras_buffer, dual_model, single_v1, single_v2)
                current_predictions = {**ens_preds, **keras_preds}

        # Draw the live overlay
        frame = draw_dashboard(frame, current_predictions)
        
        cv2.imshow("Smart Training System - Live Kata Analysis", frame)
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()