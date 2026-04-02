#!/usr/bin/env python3
"""
Extract MediaPipe pose landmarks from reference videos.
Run once per video to create precomputed landmark JSON files.
"""

import mediapipe as mp
import cv2
import json
import os
from pathlib import Path

# ─── Paths (FIXED: includes 'app' folder) ─────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent          # backend/scripts/
BACKEND_DIR = SCRIPT_DIR.parent              # backend/
# ✅ Correct path: backend/app/data/Animation
ANIMATION_DIR = BACKEND_DIR / "app" / "data" / "Animation"

print(f"📁 Animation directory: {ANIMATION_DIR}")
print(f"📁 Exists: {ANIMATION_DIR.exists()}")

# ─── MediaPipe Pose ────────────────────────────────────────────────────────────
pose = mp.solutions.pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

def extract_landmarks(video_path: str, output_json: str):
    """Extract 33 pose landmarks from each frame of a video."""
    print(f"📹 Processing: {video_path}")
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_data = []
    frame_count = 0
    
    print(f"⏳ Extracting landmarks from {total_frames} frames at {fps:.1f} FPS...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Convert to RGB for MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        
        if results.pose_landmarks:
            landmarks = []
            for lm in results.pose_landmarks.landmark:
                landmarks.append({
                    'x': float(lm.x),
                    'y': float(lm.y),
                    'z': float(lm.z),
                    'visibility': float(lm.visibility) if hasattr(lm, 'visibility') else 1.0
                })
            frames_data.append(landmarks)
            frame_count += 1
            
            if frame_count % 30 == 0:
                print(f"  Progress: {frame_count}/{total_frames} frames")
        else:
            # Append None for frames without detection (keeps timing aligned)
            frames_data.append(None)
            frame_count += 1
    
    cap.release()
    
    # Save to JSON
    output_data = {
        'fps': fps,
        'total_frames': total_frames,
        'extracted_frames': frame_count,
        'frames': frames_data
    }
    
    with open(output_json, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✅ Saved {len(frames_data)} frames to {output_json}")
    return True

def process_all_videos():
    """Process all videos in Animation directory."""
    if not ANIMATION_DIR.exists():
        print(f"❌ Animation directory not found: {ANIMATION_DIR}")
        print("💡 Make sure you're running this from the backend folder")
        return
    
    print("🔍 Scanning for videos...")
    
    processed = 0
    for move_folder in ANIMATION_DIR.iterdir():
        if not move_folder.is_dir():
            continue
        
        print(f"\n📁 Processing folder: {move_folder.name}")
        
        for video_file in move_folder.glob("*.mov"):
            if "landmarks" in video_file.name.lower():
                continue
            
            output_json = video_file.with_suffix('.json')
            
            # Check if already extracted
            if output_json.exists():
                print(f"  ⏭️  Skipping {video_file.name} (already extracted)")
                continue
            
            if extract_landmarks(video_file, output_json):
                processed += 1
    
    print(f"\n✅ Done! Processed {processed} video(s)")
    print(f"📁 Landmark files saved in: {ANIMATION_DIR}")

if __name__ == "__main__":
    print("🥋 Martial Arts Landmark Extractor")
    print("=" * 50)
    process_all_videos()