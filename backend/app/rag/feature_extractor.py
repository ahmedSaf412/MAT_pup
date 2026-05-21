import numpy as np

ANGLE_INDICES = [
    (32,28,26), (31,27,25), (28,26,24), (27,25,23), (26,24,23), (25,23,24), 
    (12,24,26), (11,23,25), (14,12,24), (13,11,23), (16,14,12), (15,13,11), 
    (11,12,24), (12,11,23)
]

def _calculate_angle_2d(a, b, c):
    ba = a - b
    bc = c - b
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba == 0 or norm_bc == 0:
        return 0.0
    cosine = np.dot(ba, bc) / (norm_ba * norm_bc + 1e-6)
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))) / 180.0

def process_and_normalize_landmarks(landmarks_list):
    """
    Takes a list of 33 dicts (x, y, z, visibility) or objects with these attributes.
    Applies mid-hip translation and shoulder scaling.
    Returns a (33, 4) numpy array.
    """
    raw_coords = np.zeros((33, 4))
    for i, lm in enumerate(landmarks_list):
        if isinstance(lm, dict):
            raw_coords[i] = [lm.get('x', 0), lm.get('y', 0), lm.get('z', 0), lm.get('visibility', 1.0)]
        else:
            raw_coords[i] = [lm.x, lm.y, lm.z, getattr(lm, 'visibility', 1.0)]
            
    # Mid-Hip Fix
    mid_hip_x = (raw_coords[23, 0] + raw_coords[24, 0]) / 2.0
    mid_hip_y = (raw_coords[23, 1] + raw_coords[24, 1]) / 2.0
    mid_hip_z = (raw_coords[23, 2] + raw_coords[24, 2]) / 2.0
    
    raw_coords[:, 0] -= mid_hip_x
    raw_coords[:, 1] -= mid_hip_y
    raw_coords[:, 2] -= mid_hip_z
    
    # Shoulder Scale
    shoulder_dist = np.sqrt((raw_coords[11, 0] - raw_coords[12, 0])**2 + 
                            (raw_coords[11, 1] - raw_coords[12, 1])**2) + 1e-6
    raw_coords[:, 0:3] /= shoulder_dist
    
    return raw_coords

def extract_102_features(landmarks_list):
    """
    Converts 33 landmarks into the exact 102 features expected by the Bi-LSTM.
    """
    coords_matrix = process_and_normalize_landmarks(landmarks_list)
    
    angles = [_calculate_angle_2d(coords_matrix[i, 0:2], coords_matrix[j, 0:2], coords_matrix[k, 0:2]) 
              for i, j, k in ANGLE_INDICES]
    
    features = []
    
    # upper_features
    # Points 11 through 22 (inclusive)
    for idx in range(11, 23):
        features.extend(coords_matrix[idx])
    # Angles 08 through 13
    features.extend(angles[8:14])
    
    # lower_features
    # Points 23 through 32 (inclusive)
    for idx in range(23, 33):
        features.extend(coords_matrix[idx])
    # Angles 00 through 07
    features.extend(angles[0:8])
    
    return features
