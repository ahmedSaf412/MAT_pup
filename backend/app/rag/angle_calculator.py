import math

# Standard anatomical names for the 14 angles
ANGLE_NAMES = [
    "left_elbow",        # 0 (landmarks 11, 13, 15)
    "right_elbow",       # 1 (landmarks 12, 14, 16)
    "left_knee",         # 2 (landmarks 23, 25, 27)
    "right_knee",        # 3 (landmarks 24, 26, 28)
    "left_hip",          # 4 (landmarks 11, 23, 25)
    "right_hip",         # 5 (landmarks 12, 24, 26)
    "left_shoulder",     # 6 (landmarks 23, 11, 13)
    "right_shoulder",    # 7 (landmarks 24, 12, 14)
    "shoulder_alignment",# 8 (landmarks 0, 11, 12)
    "torso_twist",       # 9 (landmarks 11, 12, 24)
    "left_ankle",        # 10 (landmarks 25, 27, 31)
    "right_ankle",       # 11 (landmarks 26, 28, 32)
    "left_wrist",        # 12 (landmarks 13, 15, 17)
    "right_wrist"        # 13 (landmarks 14, 16, 18)
]

def calculate_angle(a: dict, b: dict, c: dict) -> float:
    """Calculate the angle between three 3D points (in degrees)."""
    if not (a and b and c):
        return 0.0

    ba_x = a.get('x', 0) - b.get('x', 0)
    ba_y = a.get('y', 0) - b.get('y', 0)
    ba_z = a.get('z', 0) - b.get('z', 0)

    bc_x = c.get('x', 0) - b.get('x', 0)
    bc_y = c.get('y', 0) - b.get('y', 0)
    bc_z = c.get('z', 0) - b.get('z', 0)

    dot = ba_x * bc_x + ba_y * bc_y + ba_z * bc_z
    mag_ba = math.sqrt(ba_x**2 + ba_y**2 + ba_z**2)
    mag_bc = math.sqrt(bc_x**2 + bc_y**2 + bc_z**2)

    if mag_ba * mag_bc == 0:
        return 0.0

    cosine_val = dot / (mag_ba * mag_bc)
    # Clip to avoid floating point errors out of [-1, 1] bounds
    cosine_val = max(-1.0, min(1.0, cosine_val))
    
    angle_rad = math.acos(cosine_val)
    angle_deg = math.degrees(angle_rad)
    return angle_deg

def compute_14_angles(landmarks: list) -> dict:
    """
    Given a list of 33 MediaPipe landmarks, calculate the 14 standard angles.
    Returns a dict mapping {"joint_name": angle_in_degrees}
    """
    if not landmarks or len(landmarks) < 33:
        return {name: 0.0 for name in ANGLE_NAMES}
        
    angles = [
        calculate_angle(landmarks[11], landmarks[13], landmarks[15]), # left elbow
        calculate_angle(landmarks[12], landmarks[14], landmarks[16]), # right elbow
        calculate_angle(landmarks[23], landmarks[25], landmarks[27]), # left knee
        calculate_angle(landmarks[24], landmarks[26], landmarks[28]), # right knee
        calculate_angle(landmarks[11], landmarks[23], landmarks[25]), # left hip
        calculate_angle(landmarks[12], landmarks[24], landmarks[26]), # right hip
        calculate_angle(landmarks[23], landmarks[11], landmarks[13]), # left shoulder
        calculate_angle(landmarks[24], landmarks[12], landmarks[14]), # right shoulder
        calculate_angle(landmarks[0], landmarks[11], landmarks[12]),  # shoulder array
        calculate_angle(landmarks[11], landmarks[12], landmarks[24]), # torso twist
        calculate_angle(landmarks[25], landmarks[27], landmarks[31]), # left ankle
        calculate_angle(landmarks[26], landmarks[28], landmarks[32]), # right ankle
        calculate_angle(landmarks[13], landmarks[15], landmarks[17]), # left wrist
        calculate_angle(landmarks[14], landmarks[16], landmarks[18]), # right wrist
    ]
    
    return {name: angle for name, angle in zip(ANGLE_NAMES, angles)}
