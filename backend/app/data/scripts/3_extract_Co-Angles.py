import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import os
from pathlib import Path

# 14 Biomechanical Angle triplets
ANGLE_INDICES = [(32,28,26), (31,27,25), (28,26,24), (27,25,23), (26,24,23), (25,23,24), 
                (12,24,26), (11,23,25), (14,12,24), (13,11,23), (16,14,12), (15,13,11), 
                (11,12,24), (12,11,23)]

def get_angle(p1, p2, p3):
    a, b, c = np.array(p1), np.array(p2), np.array(p3)
    ba, bc = a - b, c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))) / 180.0

def extract_split_datasets(input_dir):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1)
    
    angle_data = []
    coord_data = []
    
    clip_files = list(Path(input_dir).rglob("*.mp4")) + list(Path(input_dir).rglob("*.mov"))
    print(f"📂 Found {len(clip_files)} clips. Starting extraction...")

    for clip_path in clip_files:
        cap = cv2.VideoCapture(str(clip_path))
        temp_angles, temp_coords = [], []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.pose_landmarks:
                lm = results.pose_landmarks.landmark
                # 1. Angles
                angles = [get_angle([lm[i].x, lm[i].y], [lm[j].x, lm[j].y], [lm[k].x, lm[k].y]) for i,j,k in ANGLE_INDICES]
                temp_angles.append(angles)
                # 2. Coords (X, Y, Z, V)
                coords = []
                for i in range(33):
                    coords.extend([lm[i].x, lm[i].y, lm[i].z, lm[i].visibility])
                temp_coords.append(coords)
        cap.release()

        if len(temp_angles) < 10: continue
        indices = np.linspace(0, len(temp_angles)-1, 30).astype(int)
        
        tech = clip_path.stem.split('_')[0] # Using 'label' style

        for i, idx in enumerate(indices):
            # Row for Angles CSV
            a_row = {'label': tech, 'clip_id': clip_path.stem, 'frame': i+1}
            for j, val in enumerate(temp_angles[idx]): a_row[f'angle_{j:02d}'] = val
            angle_data.append(a_row)

            # Row for Coords CSV (Matches your requested format)
            c_row = {'label': tech, 'clip_id': clip_path.stem, 'frame': i+1}
            for j in range(33):
                c_row[f'x{j}'] = temp_coords[idx][j*4]
                c_row[f'y{j}'] = temp_coords[idx][j*4+1]
                c_row[f'z{j}'] = temp_coords[idx][j*4+2]
                c_row[f'v{j}'] = temp_coords[idx][j*4+3]
            coord_data.append(c_row)

    # Save both
    pd.DataFrame(angle_data).to_csv("karate_angles.csv", index=False)
    pd.DataFrame(coord_data).to_csv("karate_coords.csv", index=False)
    print("✅ Finished! Generated: 'karate_angles.csv' and 'karate_coords.csv'")

extract_split_datasets(r"D:\CS-Senior26'\GR\Karate_phase\Segmented")