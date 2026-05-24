# AQA Pipeline Upgrade + Dual-Skeleton Comparison UI

## Background

Your existing pipeline:
- Classifies with **Single Bi-LSTM** (102-feature, already done)
- Compares form via **DTW** on `exampler_sequences.json` (the old YouTube-scraped MP4 exemplars)
- Shows feedback in a side panel with raw text

Andrew's system (`kata_reference/`) brings a **mathematically superior reference** because:
- `P3_mp_reference.json` = per-move **mean ± std angle statistics** from a real professional (P3) performer extracted with the full MediaPipe Pose Landmarker task model
- `thresholds.json` = global **tight/loose/out** bands built from novice vs. expert deviation analysis
- The reference includes 9 joints (vs. your 14) but computed over 100+ frames per move and cross-validated against novice recordings

---

## Open Questions

> [!IMPORTANT]
> **The moves in Andrew's `P3_mp_reference.json` are Bassai Dai kata moves** (`gedan_barai`, `gyaku_zuki`, `mae_geri`, `shuto_uke`, etc.). The 3 moves your classifier knows are `gedan_barai`, `gyaku_zuki`, and `mae_geri` — all of which are **present in P3's reference**. So we have clean overlap for all 3 trained classes. ✅

> [!NOTE]
> **Angle mapping difference**: Andrew's 9 angles use a different triplet definition (`spine_lean` uses (0, 23, 25) which differs from your `angle_calculator.py` 14-angle set). The hybrid approach below handles this by keeping your 14-angle DTW engine and using Andrew's statistical reference (`mean/std/tight/loose`) as the **threshold system** rather than replacing DTW.

---

## Accuracy Analysis: Which Approach Wins?

| Scenario | Andrew's Mean/Std Approach | Your Existing DTW |
|---|---|---|
| **Static poses** (ready, yame) | ✅ Excellent | Overkill |
| **Dynamic kicks/punches** (Mae Geri, Gyaku Zuki) | ❌ **Meaningless mean** | ✅ Correct temporal alignment |
| **Reference quality** | ✅ P3 professional expert data | ❌ YouTube-scraped MP4s |

**Why Andrew's mean approach fails for Mae Geri:**  
For a front kick, the right_knee angle goes: 175° (stand) → 50° (chamber) → 165° (extend) → 160° (retract).  
The mean across 30 frames is ~130°. Comparing your 130° to the master's 104° and saying "you're 26° off" is meaningless — neither of you were ever AT your average simultaneously.

**The correct solution is a hybrid:**  
Use **DTW's temporal alignment** (your existing engine) + replace the YouTube reference with **Andrew's P3 expert per-frame data**.

`P3_mp_reference.json` contains:
- `per_frame_angles`: per-joint angle arrays for all **1400 frames** of the full kata
- `move_stats.{move}.video_frames: [start, end]`: exact frame range per move

We extract `per_frame_angles[start:end]` for each of the 3 moves → downsample to 30 frames → use as DTW reference. Andrew's mean/std data goes into the DB for display only (ideal target angles for the user to read).

---

## Proposed Architecture

### Layer 1 — Classifier (unchanged)
Single Bi-LSTM → 102 features → classifies `gedan_barai / gyaku_zuki / mae_geri`

### Layer 2 — DTW with Andrew's P3 Reference (UPGRADED)
Extract Andrew's per-frame angles for each move (from `P3_mp_reference.json`'s `per_frame_angles`),  
downsample to 30 frames, store as `andrew_reference_sequences.json`.  
Run DTW frame-by-frame alignment: user sequence vs. P3 expert sequence.  
This gives you **expert-level reference quality + temporal correctness**.  
Andrew's `tight/loose/out` bands are used as the **error threshold** for each joint deviation.

### Layer 3 — DTW OOD Guard (unchanged)
Keep existing DTW distance check for out-of-distribution detection.

### Layer 4 — RAG Coaching (enhanced)
Error strings from Layer 2 feed directly into ChromaDB vector search → Groq LLM feedback.


---

## Proposed Changes

---

### Component 1: Database Seeding Script

#### [NEW] `backend/scripts/seed_move_references.py`
- Reads `Andrew's_correction/kata_reference/P3_mp_reference.json` (which has per-move angle stats including `mean`, `std`, `tight`, `loose`)
- Reads `Andrew's_correction/kata_reference/thresholds.json` (global fallback thresholds)  
- Reads `Andrew's_correction/kata_reference/bassai_dai_moves.py` (move names + descriptions)
- Upserts into `move_reference` table:
  - `ideal_angles` JSONB: `{joint_name: mean_degrees}`
  - `angle_tolerances` JSONB: `{joint_name: {tight: [lo,hi], loose: [lo,hi], std: float}}`
  - Fills `key_joints`, `description`, `category`, `display_name` for all 3 trained moves

---

### Component 2: Reference Sequence Extractor

#### [NEW] `backend/scripts/extract_andrew_sequences.py`
Extracts Andrew's P3 per-frame angles for each of the 3 trained moves:
1. Loads `P3_mp_reference.json`
2. For each move (`mae_geri`, `gyaku_zuki`, `gedan_barai`), reads `move_stats[move].video_frames = [start, end]`
3. Slices `per_frame_angles[joint][start:end]` for each of the 9 joints
4. Downsamples to exactly 30 frames using `np.linspace` (same method as the original exemplar extractor)
5. Saves as `app/rag/data/andrew_reference_sequences.json` in the exact same schema as `exampler_sequences.json`:
   ```json
   {
     "mae_geri": { "fps": 15.0, "angles": [[9 angles per frame × 30 frames]] },
     ...
   }
   ```

#### [MODIFY] `backend/app/rag/dtw_comparator.py`
- Add `ANDREW_SEQUENCES_PATH` pointing to `andrew_reference_sequences.json`
- Update `get_reference_sequences()` to try Andrew's file first, fall back to `exampler_sequences.json`
- The 9-joint indices map to Andrew's `MP_ANGLE_MAP` (which overlaps with your existing `ANGLE_NAMES`)
- Update `MIRROR_PAIRS` to only include the 9 joints Andrew defines
- Update `ERROR_THRESHOLD` to cross-reference against Andrew's `thresholds.json` per-joint `loose` bands for richer error messages (e.g., `"User's left_knee is 23.4° off — target: 58.9° (loose band: 14°–103°)"` )

> [!NOTE]
> The 5 extra joints in your 14-angle set (ankle, wrist, shoulder_alignment, torso_twist) that Andrew doesn't have are simply **not compared** in the Andrew DTW run. The user still gets 9 critical joint assessments which is enough for coaching.

---

### Component 3: RAG Pipeline Wiring

#### [MODIFY] `backend/app/rag/pipeline.py`
- Replace `compare_with_dtw` call with `compare_to_reference` from `andrew_comparator.py`
- Save DTW call result (errors) to `Detection.corrections` JSONB column immediately, before waiting for LLM response
- Pass the error list to `retrieve()` then `generate_coaching_feedback()` exactly as before — the string format is already compatible

---

### Component 4: Skeleton Comparison API Route

#### [NEW] `backend/app/routers/skeleton.py`  
Route: `GET /api/moves/{move_id}/skeleton`
- Serves landmark sequences from `exampler_sequences.json` already in `app/rag/data/`
- Response format:
  ```json
  {
    "move_id": "mae_geri",
    "fps": 29.97,
    "frames": [[{x,y,z,visibility}×33], ...]
  }
  ```

> [!NOTE]
> The existing `exampler_sequences.json` stores `angles` (not raw landmarks). However `app/data/Animation/*.json` files already have pre-extracted landmark frames (front + side). The new route will serve these existing JSON files, which the frontend's `MoveSkeletonPreview` already knows how to consume!

---

### Component 5: Backend — Startup Performance Fix

#### [MODIFY] `backend/app/main.py`
- Move model loading (the ~5-7 second Keras startup) into a `@app.on_event("startup")` async background task with `asyncio.create_task()` so the server responds to health checks immediately instead of blocking
- Pre-warm `andrew_comparator`'s reference data cache on startup

---

### Component 6: Frontend — Post-Classification Dual-Skeleton + AI Feedback Panel

#### [NEW] `frontend/app/components/RepResultPanel.js`
A new rich component that appears **below the video** after classification fires. It shows:

**Left half** — Reference Skeleton Canvas (from Andrew's/exemplar data)  
**Right half** — Trainee Skeleton Canvas (from the 30 captured landmark frames)  
Both animated and rotatable exactly like the existing `SkeletonCanvas3D` logic.

Below the dual-skeleton:
- **Per-joint error bars**: colored bars (green/yellow/red) showing deviation per joint (from Andrew's comparator output)
- **AI Sensei Card**: Groq feedback in a premium-styled expandable card
- **Quick stats**: detected move, confidence, inference time

#### [MODIFY] `frontend/app/train/page.js`
1. Add `repUserFrames` state to hold the trainee's 30-frame landmark sequence after capture
2. After `sendToClassifier` resolves:
   - fetch `GET /api/moves/{move_id}/skeleton` to get reference frames
   - show `<RepResultPanel>` below the video container
3. Remove the current cluttered side-panel feedback text (the `ragFeedback` banner + `CorrectionPanel` below the skeleton preview)
4. Keep the side panel for the pre-session skeleton preview and history only

#### [MODIFY] `frontend/app/train/train.module.css`
- Adjust layout so `RepResultPanel` sits in a row below `videoContainer`, full-width
- The right panel remains for move selection + detection history only

---

### Component 7: Live Session / Networking Guide

#### [NEW] `docs/LIVE_SESSION_GUIDE.md`
Step-by-step instructions for joining from a second laptop on the same network.

---

## Verification Plan

### Automated Tests
```bash
# Test seeder
cd backend && python scripts/seed_move_references.py

# Test Andrew comparator end-to-end
python -c "
from app.rag.andrew_comparator import compare_to_reference, load_reference
data = load_reference()
print('Loaded moves:', list(data.keys()))
"

# Test skeleton API
curl http://localhost:8000/api/moves/mae_geri/skeleton | python -m json.tool | head -20

# Restart backend, confirm startup is fast
uvicorn app.main:app --reload
```

### Manual Verification
1. Perform `mae_geri` in front of camera → verify the **dual-skeleton panel** appears below the video
2. Confirm left panel shows the reference skeleton animating, right shows your captured frames
3. Verify per-joint error bars appear with colors
4. Verify Groq AI feedback appears with styled card (not plain text banner)
5. Open `http://localhost:8000/docs` → verify `GET /api/moves/{move_id}/skeleton` appears
6. Check DB: `SELECT move_name, ideal_angles, angle_tolerances FROM move_reference;`
