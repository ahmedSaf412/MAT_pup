import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from pathlib import Path

# 14 Triplet Joint Indices for Biomechanical Angles
ANGLE_INDICES = [
    (32,28,26), (31,27,25), (28,26,24), (27,25,23), (26,24,23), (25,23,24), 
    (12,24,26), (11,23,25), (14,12,24), (13,11,23), (16,14,12), (15,13,11), 
    (11,12,24), (12,11,23)
]

def calculate_angle(p1, p2, p3):
    """Calculates 2D joint angle normalized between 0.0 and 1.0."""
    a, b, c = np.array(p1), np.array(p2), np.array(p3)
    ba, bc = a - b, c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))) / 180.0

def process_and_normalize_frame(pose_landmarks):
    """Applies Translation Invariance (Mid-Hip) and Scale Invariance (Shoulders)."""
    raw_coords = np.zeros((33, 4))
    for i in range(33):
        lm = pose_landmarks.landmark[i]
        raw_coords[i] = [lm.x, lm.y, lm.z, lm.visibility]
        
    # Mid-Hip Fix: Translate coordinate system to center on the body
    mid_hip_x = (raw_coords[23, 0] + raw_coords[24, 0]) / 2.0
    mid_hip_y = (raw_coords[23, 1] + raw_coords[24, 1]) / 2.0
    mid_hip_z = (raw_coords[23, 2] + raw_coords[24, 2]) / 2.0
    
    raw_coords[:, 0] -= mid_hip_x
    raw_coords[:, 1] -= mid_hip_y
    raw_coords[:, 2] -= mid_hip_z
    
    # Scale Invariance: Divide by shoulder distance to erase body-size differences
    shoulder_dist = np.sqrt((raw_coords[11, 0] - raw_coords[12, 0])**2 + 
                            (raw_coords[11, 1] - raw_coords[12, 1])**2) + 1e-6
    raw_coords[:, 0:3] /= shoulder_dist
    
    return raw_coords

def extract_clean_base_dataset(segmented_dir, output_csv):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1)
    all_rows = []
    
    # EXPLICIT LIST OF TARGET CLASSES (Prevents 'Segmented' or '3aw' folder pollution)
    target_classes = ['GedanBarai', 'Gyakudzuki', 'MaeGeri']
    
    total_processed_clips = 0
    
    for cls in target_classes:
        class_path = Path(segmented_dir) / cls
        if not class_path.exists():
            print(f"⚠️ Warning: Folder for class '{cls}' not found at {class_path}. Skipping.")
            continue
            
        # Target only video clips inside this specific technique's folder
        video_clips = list(class_path.glob("*.mp4")) + list(class_path.glob("*.mov"))
        print(f"\n📂 Processing target class: [{cls}] ── Found {len(video_clips)} clean clips.")
        
        for clip_path in video_clips:
            folder_label = cls  # Set directly to the target class name
            clip_id = clip_path.stem
            
            cap = cv2.VideoCapture(str(clip_path))
            extracted_frames = []
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: break
                res = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if res.pose_landmarks:
                    extracted_frames.append(process_and_normalize_frame(res.pose_landmarks))
            cap.release()
            
            # Skip corrupted clips or short cut segments with insufficient data
            if len(extracted_frames) < 10:
                print(f"⚠️ Skipping short/invalid clip: {clip_id} (Frames: {len(extracted_frames)})")
                continue
                
            # Downsample cleanly to exactly 30 chronological tracking points
            indices = np.linspace(0, len(extracted_frames) - 1, 30).astype(int)
            
            for frame_idx, original_frame_num in enumerate(indices):
                coords_matrix = extracted_frames[original_frame_num]
                angles = [calculate_angle(coords_matrix[i, 0:2], coords_matrix[j, 0:2], coords_matrix[k, 0:2]) 
                          for i, j, k in ANGLE_INDICES]
                
                row = {
                    'folder_label': folder_label,
                    'clip_id': clip_id,
                    'frame_idx': frame_idx + 1
                }
                
                # Append 14 Angles
                for idx, val in enumerate(angles):
                    row[f'angle_{idx:02d}'] = val
                    
                # Append 132 Centered and Scaled Coordinates
                for idx in range(33):
                    row[f'x{idx}'], row[f'y{idx}'], row[f'z{idx}'], row[f'v{idx}'] = coords_matrix[idx]
                    
                all_rows.append(row)
                
            print(f"   ✅ Successfully Processed: {clip_id}")
            total_processed_clips += 1

    # Compile dataset and export to target output directory
    output_df = pd.DataFrame(all_rows)
    output_df.to_csv(output_csv, index=False)
    
    print("\n" + "="*70)
    print(f"🏆 SUCCESS: Structured database file created!")
    print(f"📂 Location: {output_csv}")
    print(f"📊 Summary Data: {total_processed_clips} total clips engineered ({len(output_df):,} total frame rows)")
    print("="*70)

# Run the complete cleaning pipeline
extract_clean_base_dataset(
    r"D:\CS-Senior26'\GR\Karate_phase\Segmented", 
    r"D:\CS-Senior26'\GR\Karate_phase\karate_normalized_base.csv"
)