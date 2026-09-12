# backend/app/rag/ood_config.py
#
# Thresholds for the three-layer Out-of-Distribution (OOD) guard in classify.py.

# ── Layer 1: Confidence ──────────────────────────────────────────────────────
# If the model's top softmax probability is below this → Unknown.
CONFIDENCE_THRESHOLD = 0.65

# ── Layer 2: Margin ─────────────────────────────────────────────────────────
# Minimum gap between top-1 and top-2 probabilities.
# Small margin = the model is "confused" between two classes.
MARGIN_THRESHOLD = 0.15

# ── Layer 3: DTW Validation ─────────────────────────────────────────────────
# Compare user's angle sequence (degrees) to all 3 exemplar sequences.
# If the DTW distance to the MODEL's predicted class is this many times
# larger than the distance to the TRUE best-matching class → override with
# the DTW winner (or flag Unknown if DTW distances are all high).
DTW_OVERRIDE_RATIO = 1.6        # dtw[predicted] / dtw[best] > 1.6 → DTW wins

# If the BEST DTW distance is above this threshold (degrees), the movement
# is too different from any reference → classify as Unknown.
DTW_UNKNOWN_THRESHOLD = 35.0    # degrees mean angular deviation
