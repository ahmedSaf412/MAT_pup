# -*- coding: utf-8 -*-
BASSAI_DAI_MOVES = [
    {"move_id": 1,  "name": "yoi",           "japanese": "用意",          "description": "Ready position"},
    {"move_id": 2,  "name": "morote_uke",     "japanese": "諸手受け",  "description": "Double forearm block"},
    {"move_id": 3,  "name": "oi_zuki_jodan",  "japanese": "追い突き",  "description": "Lunge punch high"},
    {"move_id": 4,  "name": "gedan_barai",    "japanese": "下段払い",  "description": "Downward block"},
    {"move_id": 5,  "name": "uchi_uke_1",     "japanese": "内受け",    "description": "Inside forearm block"},
    {"move_id": 6,  "name": "uchi_uke_2",     "japanese": "内受け",    "description": "Inside forearm block"},
    {"move_id": 7,  "name": "uchi_uke_3",     "japanese": "内受け",    "description": "Inside forearm block"},
    {"move_id": 8,  "name": "morote_zuki",    "japanese": "諸手突き",  "description": "Double punch"},
    {"move_id": 9,  "name": "tate_zuki",      "japanese": "縦突き",        "description": "Vertical punch"},
    {"move_id": 10, "name": "uke_sequence",   "japanese": "受け",          "description": "Block sequence"},
    {"move_id": 11, "name": "yoko_geri",      "japanese": "横蹴り",    "description": "Side kick"},
    {"move_id": 12, "name": "kiba_dachi",     "japanese": "騎馬立ち",  "description": "Horse stance section"},
    {"move_id": 13, "name": "gyaku_zuki",     "japanese": "逆突き",        "description": "Reverse punch"},
    {"move_id": 14, "name": "shuto_uke_1",    "japanese": "手刀受け",  "description": "Knife hand block"},
    {"move_id": 15, "name": "shuto_uke_2",    "japanese": "手刀受け",  "description": "Knife hand block"},
    {"move_id": 16, "name": "mae_geri",       "japanese": "前蹴り",    "description": "Front kick"},
    {"move_id": 17, "name": "yame",           "japanese": "止め",          "description": "Finish"},
]

# Critical angles to check per move type
MOVE_ANGLE_FOCUS = {
    "morote_uke":   ["left_shoulder", "right_shoulder", "spine_lean"],
    "oi_zuki":      ["right_elbow", "right_shoulder", "left_knee", "spine_lean"],
    "gedan_barai":  ["left_shoulder", "left_elbow", "spine_lean"],
    "uchi_uke":     ["right_elbow", "right_shoulder", "spine_lean"],
    "morote_zuki":  ["left_elbow", "right_elbow", "spine_lean"],
    "yoko_geri":    ["right_hip", "right_knee", "spine_lean"],
    "kiba_dachi":   ["left_knee", "right_knee", "spine_lean", "right_hip"],
    "gyaku_zuki":   ["left_elbow", "right_elbow", "left_hip", "spine_lean"],
    "shuto_uke":    ["right_elbow", "right_shoulder", "left_knee"],
    "mae_geri":     ["right_hip", "right_knee", "spine_lean"],
}

print("Bassai Dai sequence loaded:", len(BASSAI_DAI_MOVES), "moves")
print("Angle focus defined for", len(MOVE_ANGLE_FOCUS), "move types")
