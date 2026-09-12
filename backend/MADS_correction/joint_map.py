JOINTS_19 = [
    "neck",           # 0
    "head",           # 1
    "left_shoulder",  # 2
    "right_shoulder", # 3
    "left_elbow",     # 4
    "right_elbow",    # 5
    "left_wrist",     # 6
    "right_wrist",    # 7
    "left_hip",       # 8
    "right_hip",      # 9
    "left_knee",      # 10
    "right_knee",     # 11
    "left_ankle",     # 12
    "right_ankle",    # 13
    "pelvis",         # 14
    "spine",          # 15
    "left_hand",      # 16
    "right_hand",     # 17
    "head_top"        # 18
]

# Critical angle definitions for karate kata
KARATE_ANGLES = {
    "right_elbow":    (3, 5, 7),   # right_shoulder → right_elbow → right_wrist
    "left_elbow":     (2, 4, 6),   # left_shoulder  → left_elbow  → left_wrist
    "right_shoulder": (5, 3, 9),   # right_elbow → right_shoulder → right_hip
    "left_shoulder":  (4, 2, 8),   # left_elbow  → left_shoulder  → left_hip
    "right_knee":     (9, 11, 13), # right_hip   → right_knee     → right_ankle
    "left_knee":      (8, 10, 12), # left_hip    → left_knee      → left_ankle
    "right_hip":      (3, 9, 11),  # right_shoulder → right_hip   → right_knee
    "left_hip":       (2, 8, 10),  # left_shoulder  → left_hip    → left_knee
    "spine_lean":     (0, 14, 8),  # neck → pelvis → left_hip (torso uprightness)
}
