# ML Model Technology Documentation

## Overview

The AI model classifies **4 Kyokushin karate moves** in real time from body pose landmarks:

| # | Move | Japanese Name | Key Body Parts |
|---|------|--------------|----------------|
| 1 | Reverse Lunge Punch | Gyaku-Zuki | Arms, shoulders, hips |
| 2 | Front Kick | Mae Geri | Knee, hip, ankle |
| 3 | Roundhouse Kick | Mawashi Geri | Hip rotation, knee, ankle |
| 4 | Spinning Back Kick | Ushiro Mawashi Geri | Full body rotation, kick leg |

---

## Dataset

**Source**: [Multimodal Kyokushin Karate Dataset](https://springernature.figshare.com/articles/dataset/Multimodal_dataset_of_37_Kyokushin_karate_athletes_/12315629)

| Property | Value |
|----------|-------|
| Athletes | 37 |
| Moves | 4 (listed above) |
| Data Types | Motion Capture (.c3d), Video, Audio |
| Total Size | ~9.19 GB |
| File Format | `.c3d` (3D marker positions per frame) |
| Sampling Rate | 100–200 Hz (MoCap) |

### Dataset Structure
Each athlete performed multiple repetitions of each move. The `.c3d` files contain:
- **3D marker positions** (x, y, z) for body markers
- **Frame-by-frame** temporal data
- **Analog data** (force plates, if available)

---

## Pipeline Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  .c3d Files  │────▶│  parse_c3d.py   │────▶│  Raw CSV Data   │
│  (MoCap)     │     │  (extract 3D    │     │  (markers ×     │
│              │     │   marker coords) │     │   frames)       │
└──────────────┘     └─────────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ extract_features │
                                             │ .py              │
                                             │ (joint angles,   │
                                             │  distances,      │
                                             │  velocities)     │
                                             └────────┬────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ build_sequences  │
                                             │ .py              │
                                             │ (sliding window  │
                                             │  30 frames,      │
                                             │  train/val/test) │
                                             └────────┬────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ train_model.py   │
                                             │ (LSTM training,  │
                                             │  save model.h5)  │
                                             └─────────────────┘
```

---

## Step 1: Parse C3D Files (`parse_c3d.py`)

Uses the `c3d` Python library to read motion capture files.

```python
import c3d
import pandas as pd
import numpy as np

def parse_c3d_file(filepath):
    """Extract 3D marker positions from a .c3d file."""
    reader = c3d.Reader(open(filepath, 'rb'))
    
    # Get marker labels
    labels = reader.point_labels
    
    frames = []
    for i, points, analog in reader.read_frames():
        # points shape: (num_markers, 5) → x, y, z, residual, camera_mask
        frame_data = {'frame': i}
        for j, label in enumerate(labels):
            label = label.strip()
            frame_data[f'{label}_x'] = points[j, 0]
            frame_data[f'{label}_y'] = points[j, 1]
            frame_data[f'{label}_z'] = points[j, 2]
        frames.append(frame_data)
    
    return pd.DataFrame(frames)
```

**Output**: CSV with columns like `RSHO_x, RSHO_y, RSHO_z, LSHO_x, ...` for every frame.

---

## Step 2: Extract Features (`extract_features.py`)

Maps MoCap markers to a **MediaPipe-compatible skeleton** and computes joint angles.

### Key Features Extracted

| Feature | Description | Relevant Moves |
|---------|-------------|----------------|
| Elbow angles (L/R) | Angle at elbow joint | Punch |
| Knee angles (L/R) | Angle at knee joint | All kicks |
| Hip angles (L/R) | Angle at hip joint | All kicks |
| Shoulder angles (L/R) | Arm raise angle | Punch, guard |
| Hip rotation | Angle in transverse plane | Roundhouse, spinning kick |
| Ankle-to-shoulder dist | Kick extension metric | All kicks |

### Joint Angle Calculation
```python
def calculate_angle(a, b, c):
    """
    Calculate angle at point b given 3 points.
    a, b, c are (x, y, z) arrays.
    Returns angle in degrees.
    """
    ba = a - b
    bc = c - b
    
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return angle
```

### MoCap → MediaPipe Marker Mapping

The dataset uses Vicon-style markers. We map them to the 33-point MediaPipe format:

| MediaPipe Landmark | MoCap Marker(s) |
|-------------------|-----------------|
| LEFT_SHOULDER (11) | LSHO |
| RIGHT_SHOULDER (12) | RSHO |
| LEFT_ELBOW (13) | LELB |
| RIGHT_ELBOW (14) | RELB |
| LEFT_WRIST (15) | LWRA / LWRB avg |
| RIGHT_WRIST (16) | RWRA / RWRB avg |
| LEFT_HIP (23) | LASI / LPSI avg |
| RIGHT_HIP (24) | RASI / RPSI avg |
| LEFT_KNEE (25) | LKNE |
| RIGHT_KNEE (26) | RKNE |
| LEFT_ANKLE (27) | LANK |
| RIGHT_ANKLE (28) | RANK |

---

## Step 3: Build Sequences (`build_sequences.py`)

Creates temporal sequences for the LSTM model using a **sliding window** approach.

```python
WINDOW_SIZE = 30      # frames (~0.3s at 100Hz, ~1s at 30fps webcam)
STRIDE = 15           # 50% overlap
NUM_FEATURES = 12     # number of joint angles/distances per frame
```

**Output shapes**:
- `X_train`: `(N, 30, 12)` — N sequences, 30 timesteps, 12 features
- `y_train`: `(N,)` — labels 0–3

**Data split**: 70% train / 15% validation / 15% test, stratified by move type.

---

## Step 4: Train LSTM Model (`train_model.py`)

### Model Architecture

```
┌───────────────────────────────────┐
│ Input: (batch, 30, 12)            │
├───────────────────────────────────┤
│ LSTM Layer 1: 128 units           │
│   - return_sequences=True         │
│   - dropout=0.3                   │
├───────────────────────────────────┤
│ LSTM Layer 2: 64 units            │
│   - return_sequences=False        │
│   - dropout=0.3                   │
├───────────────────────────────────┤
│ Dense: 32 units, ReLU             │
│   - dropout=0.2                   │
├───────────────────────────────────┤
│ Dense: 4 units, Softmax           │
│   (reverse_lunge_punch,           │
│    front_kick,                    │
│    roundhouse_kick,               │
│    spinning_back_kick)            │
└───────────────────────────────────┘
```

### Training Configuration

| Parameter | Value |
|-----------|-------|
| Optimizer | Adam, lr=0.001 |
| Loss | Categorical Crossentropy |
| Batch Size | 32 |
| Epochs | 100 (early stopping, patience=10) |
| Metrics | Accuracy, F1-score |

### Code Sketch
```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(30, 12)),
    Dropout(0.3),
    LSTM(64, return_sequences=False),
    Dropout(0.3),
    Dense(32, activation='relu'),
    Dropout(0.2),
    Dense(4, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=100,
    batch_size=32,
    callbacks=[
        EarlyStopping(patience=10, restore_best_weights=True),
        ModelCheckpoint('model.h5', save_best_only=True)
    ]
)
```

---

## Real-Time Inference

During live training, the flow is:

1. **MediaPipe** extracts 33 landmarks from the webcam (in browser)
2. **Frontend** buffers 30 frames and sends via WebSocket
3. **Backend** receives landmarks and:
   - Maps MediaPipe landmarks → same 12 joint angle features
   - Scales using the saved `StandardScaler`
   - Feeds `(1, 30, 12)` tensor into the LSTM
   - Gets softmax probabilities for 4 classes
   - Returns `argmax class + confidence`

### Inference Code
```python
import numpy as np
from tensorflow.keras.models import load_model
import joblib

# Load once at startup
model = load_model('ml/model.h5')
scaler = joblib.load('ml/scaler.pkl')
label_encoder = joblib.load('ml/label_encoder.pkl')

def predict_move(landmarks_buffer):
    """
    landmarks_buffer: list of 30 frames, each with 33 landmarks
    Returns: (move_name, confidence)
    """
    # Extract features (joint angles) from landmarks
    features = extract_angles_from_landmarks(landmarks_buffer)  # (30, 12)
    
    # Scale
    features_flat = features.reshape(30, -1)
    features_scaled = scaler.transform(features_flat)
    
    # Predict
    X = features_scaled.reshape(1, 30, 12)
    probs = model.predict(X, verbose=0)[0]
    
    class_idx = np.argmax(probs)
    confidence = float(probs[class_idx])
    move_name = label_encoder.inverse_transform([class_idx])[0]
    
    return move_name, confidence
```

---

## Correction System

The correction engine is **rule-based** (not ML), comparing user angles to ideal reference angles:

### Reference Angles (stored in DB `move_catalog`)

```json
{
  "front_kick": {
    "kicking_knee_angle": {"min": 160, "max": 180, "message": "Extend your knee fully"},
    "kicking_hip_angle": {"min": 80, "max": 100, "message": "Raise your knee to waist height"},
    "guard_elbow_angle": {"min": 30, "max": 60, "message": "Keep your guard hands close"},
    "supporting_knee_angle": {"min": 160, "max": 180, "message": "Keep supporting leg straight"}
  }
}
```

### Correction Logic
```python
def generate_corrections(user_angles, move_name, reference_angles):
    corrections = []
    ref = reference_angles[move_name]
    
    for joint, bounds in ref.items():
        if joint in user_angles:
            angle = user_angles[joint]
            if angle < bounds['min']:
                corrections.append({
                    'joint': joint,
                    'message': bounds['message'],
                    'severity': 'warning' if abs(angle - bounds['min']) > 20 else 'info'
                })
            elif angle > bounds['max']:
                corrections.append({
                    'joint': joint,
                    'message': bounds['message'],
                    'severity': 'warning' if abs(angle - bounds['max']) > 20 else 'info'
                })
    
    return corrections
```

---

## Expanding to More Martial Arts (Future)

The architecture supports expansion:

1. **Add new moves**: Insert into `move_catalog` DB table with reference angles
2. **Add new martial arts**: Just change the `martial_art` field (e.g., "taekwondo")
3. **Retrain model**: Add new labeled sequences and increase the output layer size
4. **Bigger dataset**: Download more data from YouTube, use MediaPipe to extract poses from video, label them, and add to the training set

---

## Dependencies

```
tensorflow>=2.15
numpy>=1.24
pandas>=2.0
scikit-learn>=1.3
c3d>=0.5
joblib>=1.3
matplotlib>=3.7  # for training visualization
```
