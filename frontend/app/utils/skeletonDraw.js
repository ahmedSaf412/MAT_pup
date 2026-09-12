/**
 * skeletonDraw.js — shared skeleton drawing utility
 *
 * Used by both the kata page (direct canvas drawing in a RAF loop) and
 * exported as constants for the PoseCanvas React component.
 *
 * All drawing is pure Canvas2D — no React, no dependencies.
 */

// ── Connections ─────────────────────────────────────────────────────────────
export const POSE_CONNECTIONS = [
  // Face
  [0, 1], [1, 2], [2, 3], [3, 7],
  [0, 4], [4, 5], [5, 6], [6, 8],
  [9, 10],
  // Torso
  [11, 12], [11, 23], [12, 24], [23, 24],
  // Left arm
  [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
  // Right arm
  [12, 14], [14, 16], [16, 18], [16, 20], [16, 22],
  // Left leg
  [23, 25], [25, 27], [27, 29], [29, 31],
  // Right leg
  [24, 26], [26, 28], [28, 30], [30, 32],
];

// ── Region sets ──────────────────────────────────────────────────────────────
export const TORSO = new Set([11, 12, 23, 24]);
export const ARMS  = new Set([13, 14, 15, 16, 17, 18, 19, 20, 21, 22]);
export const LEGS  = new Set([25, 26, 27, 28, 29, 30, 31, 32]);
export const FACE  = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

// ── Colours ──────────────────────────────────────────────────────────────────
export function connectionColor(a, b, correctionSet = null) {
  if (correctionSet && (correctionSet.has(a) || correctionSet.has(b))) {
    return { stroke: '#FF4646', shadow: 'rgba(255,70,70,0.6)', width: 4 };
  }
  if (TORSO.has(a) || TORSO.has(b)) return { stroke: 'rgba(0,212,255,0.90)',   shadow: 'rgba(0,212,255,0.45)',   width: 2.5 };
  if (ARMS.has(a)  || ARMS.has(b))  return { stroke: 'rgba(124,58,237,0.90)',  shadow: 'rgba(124,58,237,0.45)',  width: 2.5 };
  if (LEGS.has(a)  || LEGS.has(b))  return { stroke: 'rgba(0,220,120,0.90)',   shadow: 'rgba(0,220,120,0.45)',   width: 2.5 };
  if (FACE.has(a)  || FACE.has(b))  return { stroke: 'rgba(255,180,0,0.75)',   shadow: 'rgba(255,180,0,0.35)',   width: 1.8 };
  return                                    { stroke: 'rgba(200,200,200,0.6)',  shadow: 'transparent',            width: 2 };
}

export function dotColor(i, correctionSet = null) {
  if (correctionSet && correctionSet.has(i)) return '#FF4646';
  if (FACE.has(i))  return 'rgba(255,180,0,0.95)';
  if (TORSO.has(i)) return 'rgba(0,212,255,0.95)';
  if (ARMS.has(i))  return 'rgba(124,58,237,0.95)';
  if (LEGS.has(i))  return 'rgba(0,220,120,0.95)';
  return 'rgba(255,255,255,0.85)';
}

// ── Core drawing function ────────────────────────────────────────────────────
/**
 * drawSkeleton(ctx, W, H, landmarks, options)
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} W  - canvas pixel width
 * @param {number} H  - canvas pixel height
 * @param {Array}  landmarks  - 33 {x,y,z,visibility} objects (normalised 0-1)
 * @param {object} options
 *   @param {Set}     [correctionSet]  - landmark indices to highlight red
 *   @param {boolean} [mirrored=false] - flip X axis (for live camera)
 *   @param {number}  [visThreshold=0.35]
 */
export function drawSkeleton(ctx, W, H, landmarks, {
  correctionSet  = null,
  mirrored       = false,
  visThreshold   = 0.35,
} = {}) {
  ctx.clearRect(0, 0, W, H);

  const lx = (lm) => (mirrored ? 1 - lm.x : lm.x) * W;
  const ly = (lm) => lm.y * H;
  const vis = (lm) => (lm.visibility ?? 1) >= visThreshold;

  // ── Connections ────────────────────────────────────────────────────────────
  for (const [a, b] of POSE_CONNECTIONS) {
    const lmA = landmarks[a];
    const lmB = landmarks[b];
    if (!lmA || !lmB || !vis(lmA) || !vis(lmB)) continue;

    const c = connectionColor(a, b, correctionSet);
    ctx.beginPath();
    ctx.moveTo(lx(lmA), ly(lmA));
    ctx.lineTo(lx(lmB), ly(lmB));
    ctx.strokeStyle = c.stroke;
    ctx.lineWidth   = c.width;
    ctx.shadowColor = c.shadow;
    ctx.shadowBlur  = c.shadow === 'transparent' ? 0 : 7;
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // ── Joints ────────────────────────────────────────────────────────────────
  for (let i = 0; i < landmarks.length; i++) {
    const lm = landmarks[i];
    if (!vis(lm)) continue;

    const x  = lx(lm);
    const y  = ly(lm);
    const corr = correctionSet?.has(i);
    const r    = corr ? 7 : (FACE.has(i) ? 3.5 : 5);
    const dc   = dotColor(i, correctionSet);

    // Subtle glow ring
    ctx.beginPath();
    ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
    ctx.fillStyle = corr ? 'rgba(255,70,70,0.22)' : 'rgba(255,255,255,0.06)';
    ctx.fill();

    // Core dot
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fillStyle  = dc;
    ctx.shadowColor = corr ? '#FF4646' : dc;
    ctx.shadowBlur  = corr ? 12 : 4;
    ctx.fill();
    ctx.shadowBlur = 0;

    // White outline
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth   = 1.2;
    ctx.stroke();
  }
}
