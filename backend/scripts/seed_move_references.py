"""
scripts/seed_move_references.py
================================
Seeds the move_reference PostgreSQL table with MADS P3 professional
reference data (ideal_angles, angle_tolerances) for all 3 trained moves.

Reads:
  - MADS_correction/kata_reference/P3_mp_reference.json
      → ideal_angles     (mean for each joint)
      → angle_tolerances (tight/loose/std bands)
  - MADS_correction/kata_reference/thresholds.json
      → global fallback bands
  - MADS_correction/kata_reference/bassai_dai_moves.py
      → display_name, description, japanese names

Run from backend/ directory:
    python scripts/seed_move_references.py
"""

import json
import sys
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
BASE       = Path(__file__).resolve().parent.parent
ANDREW_DIR = BASE / "MADS_correction" / "kata_reference"
MP_REF     = ANDREW_DIR / "P3_mp_reference.json"
THRESH     = ANDREW_DIR / "thresholds.json"

sys.path.insert(0, str(BASE))

# ── metadata for the 3 trained moves ─────────────────────────────────────────
TRAINED_MOVES_META = {
    "gedan_barai": {
        "display_name":    "Down Block",
        "category":        "block",
        "difficulty_level": "beginner",
        "key_joints":      ["left_shoulder", "left_elbow", "spine_lean"],
        "tips": [
            "Sweep the blocking arm diagonally downward with force",
            "Chamber the other hand sharply at the hip (hikite)",
            "Kiai on completion",
            "Keep the blocking arm above the knee, not below",
        ],
    },
    "gyaku_zuki": {
        "display_name":    "Reverse Punch",
        "category":        "punch",
        "difficulty_level": "beginner",
        "key_joints":      ["left_elbow", "right_elbow", "left_hip", "spine_lean"],
        "tips": [
            "Drive the rear hip forward to power the punch",
            "Pull the lead hand back sharply to the hip",
            "Keep the punching shoulder relaxed until impact",
            "Body square — do not over-rotate",
        ],
    },
    "mae_geri": {
        "display_name":    "Front Kick",
        "category":        "kick",
        "difficulty_level": "beginner",
        "key_joints":      ["right_hip", "right_knee", "spine_lean"],
        "tips": [
            "Chamber the knee high before extending",
            "Kick with the ball of the foot, not the toe",
            "Keep hips square — do not lean back",
            "Retract the kick quickly after contact",
        ],
    },
}


def load_reference() -> dict:
    print(f"  Loading {MP_REF.name} …")
    with open(MP_REF, encoding="utf-8") as f:
        return json.load(f)


def load_thresholds() -> dict:
    print(f"  Loading {THRESH.name} …")
    with open(THRESH, encoding="utf-8") as f:
        return json.load(f)


def build_payload(move_name: str, mp_ref: dict, thresholds: dict) -> dict:
    """Build the ideal_angles and angle_tolerances dicts for one move."""
    move_stats = mp_ref.get("move_stats", {}).get(move_name, {})

    ideal_angles     = {}
    angle_tolerances = {}

    if move_stats:
        for joint, stats in move_stats.items():
            ideal_angles[joint] = round(float(stats["mean"]), 2)
            angle_tolerances[joint] = {
                "std":   round(float(stats.get("std", 15.0)), 2),
                "tight": [round(stats["tight"][0], 2), round(stats["tight"][1], 2)],
                "loose": [round(stats["loose"][0], 2), round(stats["loose"][1], 2)],
                "n":     stats.get("n", 0),
            }
        print(f"    Using move_stats for '{move_name}' ({len(move_stats)} joints)")
    else:
        # Fallback to global thresholds (less accurate)
        print(f"    WARNING: '{move_name}' not in move_stats — using global thresholds")
        for joint, stats in thresholds.items():
            ideal_angles[joint] = round(float(stats["mean"]), 2)
            angle_tolerances[joint] = {
                "std":   round(float(stats.get("std", 15.0)), 2),
                "tight": [round(stats["tight"][0], 2), round(stats["tight"][1], 2)],
                "loose": [round(stats["loose"][0], 2), round(stats["loose"][1], 2)],
                "priority": stats.get("priority", "MEDIUM"),
            }

    return ideal_angles, angle_tolerances


def main():
    print("\n" + "=" * 60)
    print("  move_reference DB Seeder  (MADS P3 data)")
    print("=" * 60 + "\n")

    mp_ref     = load_reference()
    thresholds = load_thresholds()

    # Import DB after sys.path setup
    from app.database import SessionLocal, init_db
    from app.models.move import MoveReference

    init_db()
    db = SessionLocal()

    try:
        upserted = 0
        for move_name, meta in TRAINED_MOVES_META.items():
            print(f"\n  [{move_name}]")
            ideal, tolerances = build_payload(move_name, mp_ref, thresholds)

            existing = db.query(MoveReference).filter_by(move_name=move_name).first()

            if existing:
                existing.display_name    = meta["display_name"]
                existing.category        = meta["category"]
                existing.difficulty_level = meta["difficulty_level"]
                existing.key_joints      = meta["key_joints"]
                existing.tips            = meta["tips"]
                existing.ideal_angles    = ideal
                existing.angle_tolerances = tolerances
                print(f"    Updated  (id={existing.id})")
            else:
                record = MoveReference(
                    move_name       = move_name,
                    display_name    = meta["display_name"],
                    category        = meta["category"],
                    difficulty_level= meta["difficulty_level"],
                    key_joints      = meta["key_joints"],
                    tips            = meta["tips"],
                    ideal_angles    = ideal,
                    angle_tolerances= tolerances,
                    description     = meta["tips"][0],
                )
                db.add(record)
                print(f"    Inserted (new row)")

            upserted += 1

        db.commit()
        print(f"\n  Done -- {upserted} moves seeded/updated [OK]\n")

    except Exception as e:
        db.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
