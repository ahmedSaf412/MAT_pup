# -*- coding: utf-8 -*-

  KARATE KATA CORRECTOR -- DEVELOPER PACKAGE
  ==========================================

  WHAT THIS DOES
  --------------
  Real-time karate pose correction system.
  Evaluates a practitioner performing Bassai Dai kata
  and gives joint-by-joint angle feedback.

  No training required -- reference data is pre-built
  from a professional performer (MADS dataset, P3).


  INPUT MODES
  -----------
  1. Live webcam feed
  2. Uploaded video file (.mp4  .avi  .mov)


  HOW TO RUN
  ----------
  Step 1:  pip install -r requirements.txt
  Step 2:  cd karate_corrector_export
  Step 3:  python kata_trainer.py
  Step 4:  Choose camera or video when prompted
  Step 5:  Select which kata technique to practice
  Step 6:  Perform the technique -- get live feedback


  CONTROLS (video mode)
  ---------------------
  SPACE       = pause / resume
  LEFT/RIGHT  = skip +/-30 frames
  R           = restart video from beginning
  N           = save current move and advance to next
  S           = save screenshot
  Q           = quit and show final report


  CONTROLS (camera mode)
  ----------------------
  N           = save current move and advance to next
  S           = save screenshot
  Q           = quit and show final report


  OUTPUT
  ------
  - Live skeleton overlay with colored joint arcs:
      GREEN  = joint angle correct (within tight range)
      YELLOW = acceptable (within loose range)
      RED    = needs correction

  - Feedback panel showing:
      Current angle vs target angle
      Text correction advice
      Overall form score (0-100%)

  - Final report saved to trainee_sessions\ as:
      {technique}_{YYYY-MM-DD_HH-MM}.json
      {technique}_{YYYY-MM-DD_HH-MM}.txt

  - Screenshots saved to screenshots\ as:
      screenshot_{YYYY-MM-DD_HH-MM-SS}.jpg


  REFERENCE DATA (pre-built -- do not modify)
  -------------------------------------------
  P3_mp_reference.json   Primary reference: MediaPipe angles from
                         professional performer (816 frames, 17 moves)
  thresholds.json        Joint angle tolerances (tight / loose bands)
  P3_angles.json         Raw professional angles -- MADS skeleton space
  P3_labels.json         17 Bassai Dai move segments with frame boundaries
  bassai_dai_moves.py    Move sequence + which joints to check per move
  joint_map.py           19-joint skeleton definition + angle formulas
  Kata_P3_Left.avi       Professional performer video (200 MB)
                         Used for side-by-side skeleton comparison.
                         Place in kata_reference\ folder to enable split view.
                         Without it the system runs in single-panel mode.


  TECHNIQUES COVERED
  ------------------
  Full Bassai Dai kata -- 17 moves:

  1.  yoi            (用意)        Ready position
  2.  morote_uke     (諸手受け)    Double forearm block
  3.  oi_zuki_jodan  (追い突き)    Lunge punch high
  4.  gedan_barai    (下段払い)    Downward block
  5.  uchi_uke_1     (内受け)      Inside forearm block
  6.  uchi_uke_2     (内受け)      Inside forearm block
  7.  uchi_uke_3     (内受け)      Inside forearm block
  8.  morote_zuki    (諸手突き)    Double punch
  9.  tate_zuki      (縦突き)      Vertical punch
  10. uke_sequence   (受け)        Block sequence
  11. yoko_geri      (横蹴り)      Side kick
  12. kiba_dachi     (騎馬立ち)    Horse stance section
  13. gyaku_zuki     (逆突き)      Reverse punch
  14. shuto_uke_1    (手刀受け)    Knife hand block
  15. shuto_uke_2    (手刀受け)    Knife hand block
  16. mae_geri       (前蹴り)      Front kick
  17. yame           (止め)        Finish


  KEY ANGLES EVALUATED
  --------------------
  spine_lean      Torso uprightness      (highest priority)
  left_knee       Left knee bend
  left_shoulder   Left arm elevation
  right_shoulder  Right arm elevation
  right_elbow     Right arm bend
  left_elbow      Left arm bend
  right_hip       Right hip angle
  left_hip        Left hip angle

  Each angle is compared against the professional reference with
  two tolerance bands:
    Tight band  (mean +/- 1 std dev)  -> GREEN
    Loose band  (mean +/- 1.5 std dev) -> YELLOW
    Outside     -> RED


  FOR WEB INTEGRATION
  -------------------
  The core logic is in kata_trainer.py.
  Key functions to expose as API endpoints:

    extract_angles(frame)
        Input : OpenCV BGR frame (numpy array)
        Output: dict of 9 joint angles (degrees)

    compare_to_reference(angles, move_name)
        Input : angle dict + move name string
        Output: score (0-100) + per-joint status

    get_move_feedback(angles, move_name)
        Output: list of text correction strings

  Sessions are saved as JSON in trainee_sessions\ --
  these can be read and displayed on the website.

  JSON session format:
  {
    "date":          "2026-05-22T14:30:00",
    "technique":     "gedan_barai",
    "japanese":      "下段払い",
    "overall_score": 73.5,
    "grade":         "Good",
    "angles": {
      "spine_lean": {"avg": 174.2, "target": 171.0,
                     "diff": 3.2, "status": "tight"},
      ...
    },
    "corrections": [
      {"angle": "left_knee", "hint": "bend left knee deeper",
       "avg": 162.0, "target": 145.0}
    ]
  }


  REQUIREMENTS
  ------------
  Python 3.9+
  Webcam (optional -- only for live mode)
  No GPU required -- runs on CPU

  See requirements.txt for exact package versions.


  FILE STRUCTURE
  --------------
  karate_corrector_export\
  |-- kata_trainer.py          Main script
  |-- joint_map.py             Skeleton joint definitions
  |-- requirements.txt         Python dependencies
  |-- README.txt               This file
  |-- trainee_sessions\        Session reports saved here (auto-created)
  |-- screenshots\             Screenshots saved here (auto-created)
  └-- kata_reference\
      |-- P3_mp_reference.json  Primary reference angles (MediaPipe)
      |-- thresholds.json       Angle tolerance bands
      |-- P3_angles.json        Raw MADS reference angles
      |-- P3_labels.json        Move segment frame boundaries
      |-- bassai_dai_moves.py   Move list and angle focus map
      |-- pose_landmarker_full.task  MediaPipe pose model (~9 MB)
      └-- Kata_P3_Left.avi      Professional reference video (200 MB)
