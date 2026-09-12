'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './RepResultPanel.module.css';

// ── Pose connections ───────────────────────────────────────────────────────────
const POSE_CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],
  [9,10],[11,12],
  [11,13],[13,15],[15,17],[15,19],[15,21],[17,19],
  [12,14],[14,16],[16,18],[16,20],[16,22],[18,20],
  [11,23],[12,24],[23,24],
  [23,25],[25,27],[27,29],[29,31],[27,31],
  [24,26],[26,28],[28,30],[30,32],[28,32],
];

const LEFT_IDX  = new Set([1,2,3,7,9,11,13,15,17,19,21,23,25,27,29,31]);
const RIGHT_IDX = new Set([4,5,6,8,10,12,14,16,18,20,22,24,26,28,30,32]);

function jColor(idx) {
  if (LEFT_IDX.has(idx))  return '#00e676';
  if (RIGHT_IDX.has(idx)) return '#ff5252';
  return '#00d4ff';
}

function angle3D(lms, a, b, c) {
  if (!lms || !lms[a] || !lms[b] || !lms[c]) return 0;
  const pA = lms[a], pB = lms[b], pC = lms[c];
  if (pA.visibility < 0.2 || pB.visibility < 0.2 || pC.visibility < 0.2) return null;
  const bax = pA.x - pB.x, bay = pA.y - pB.y, baz = pA.z - pB.z;
  const bcx = pC.x - pB.x, bcy = pC.y - pB.y, bcz = pC.z - pB.z;
  const dot = bax*bcx + bay*bcy + baz*bcz;
  const mag = Math.sqrt(bax*bax + bay*bay + baz*baz) * Math.sqrt(bcx*bcx + bcy*bcy + bcz*bcz);
  if (mag < 1e-9) return 0;
  return Math.round((Math.acos(Math.max(-1.0, Math.min(1.0, dot / mag))) * 180) / Math.PI);
}

function project(lm, rotY, rotX, CX, CY, SXYZ, FOCAL) {
  const wx = (lm.x - 0.5) * SXYZ;
  const wy = (lm.y - 0.5) * SXYZ;
  const wz = (lm.z || 0) * SXYZ * 0.6;

  // Y-axis rotation (left/right drag)
  const rx =  wx * Math.cos(rotY) - wz * Math.sin(rotY);
  const rz =  wx * Math.sin(rotY) + wz * Math.cos(rotY);
  // X-axis rotation (up/down drag)
  const ry2 = wy * Math.cos(rotX) - rz * Math.sin(rotX);
  const rz2 = wy * Math.sin(rotX) + rz * Math.cos(rotX);

  const s = FOCAL / (FOCAL + rz2);
  return { sx: CX + rx * s, sy: CY + ry2 * s, sz: rz2, vis: lm.visibility ?? 1 };
}

const MADS_ANGLES = [
  { name: 'R-Elbow',    pts: [12, 14, 16], center: 14 },
  { name: 'L-Elbow',    pts: [11, 13, 15], center: 13 },
  { name: 'R-Shoulder', pts: [14, 12, 24], center: 12 },
  { name: 'L-Shoulder', pts: [13, 11, 23], center: 11 },
  { name: 'R-Knee',     pts: [24, 26, 28], center: 26 },
  { name: 'L-Knee',     pts: [23, 25, 27], center: 25 },
  { name: 'R-Hip',      pts: [12, 24, 26], center: 24 },
  { name: 'L-Hip',      pts: [11, 23, 25], center: 23 },
];

function drawPanel(ctx, lms, rotY, rotX, CX, CY, SXYZ, FOCAL, clipLeft, clipRight, label, drawAngles) {
  if (!lms) return;

  const pts = lms.map(lm => project(lm, rotY, rotX, CX, CY, SXYZ, FOCAL));

  ctx.save();
  ctx.beginPath();
  ctx.rect(clipLeft, 0, clipRight - clipLeft, ctx.canvas.height);
  ctx.clip();

  // Bones (depth-sorted for painter's algo)
  const lines = POSE_CONNECTIONS
    .filter(([i, j]) => pts[i] && pts[j] && pts[i].vis > 0.25 && pts[j].vis > 0.25)
    .map(([i, j])    => ({ i, j, depth: (pts[i].sz + pts[j].sz) / 2 }))
    .sort((a, b)     => b.depth - a.depth);

  lines.forEach(({ i, j, depth }) => {
    const p1 = pts[i], p2 = pts[j];
    const dn = Math.max(0, Math.min(1, (100 - depth) / 200));
    ctx.strokeStyle = `rgba(0,212,255,${0.3 + dn * 0.65})`;
    ctx.lineWidth   = 1.5 + dn * 2.5;
    ctx.lineCap     = 'round';
    ctx.beginPath(); ctx.moveTo(p1.sx, p1.sy); ctx.lineTo(p2.sx, p2.sy); ctx.stroke();
  });

  // Joints (depth-sorted)
  pts
    .map((p, idx) => ({ ...p, idx }))
    .filter(p => p.vis > 0.25)
    .sort((a, b) => b.sz - a.sz)
    .forEach(({ sx, sy, sz, idx }) => {
      const dn  = Math.max(0, Math.min(1, (100 - sz) / 200));
      const r   = 2.5 + dn * 3;
      const col = jColor(idx);
      ctx.save();
      ctx.shadowColor = col; ctx.shadowBlur = 8;
      ctx.fillStyle   = col;
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    });

  // Angle labels in Slow Mo
  if (drawAngles) {
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    MADS_ANGLES.forEach(ang => {
      const val = angle3D(lms, ang.pts[0], ang.pts[1], ang.pts[2]);
      if (val !== null && pts[ang.center] && pts[ang.center].vis > 0.2) {
        const { sx, sy } = pts[ang.center];
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(sx - 15, sy - 18, 30, 14);
        ctx.fillStyle = '#ffeb3b';
        ctx.fillText(`${val}°`, sx, sy - 6);
      }
    });
  }

  // Panel label
  ctx.fillStyle    = 'rgba(0,212,255,0.7)';
  ctx.font         = 'bold 12px monospace';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'bottom';
  ctx.fillText(label, (clipLeft + clipRight) / 2, ctx.canvas.height - 10);

  ctx.restore();
}

// ─────────────────────────────────────────────────────────────────────────────
// DualSkeletonCanvas — drag to rotate, auto-rotate when not dragging
// ─────────────────────────────────────────────────────────────────────────────
function DualSkeletonCanvas({ refFrames, traineeFrames, fps }) {
  const canvasRef  = useRef(null);
  const rafRef     = useRef(null);
  const frameIdx   = useRef(0);
  const lastTick   = useRef(0);

  // Rotation state (shared both panels when dragging canvas as a whole;
  // each panel has independent control via the ← / → buttons below)
  const rotY    = useRef(0);          // Y-rotation (horizontal drag)
  const rotX    = useRef(0.15);       // X-rotation (vertical drag — slight downward tilt)
  const autoRot = useRef(true);       // auto-rotate when idle

  // Drag state
  const drag    = useRef({ active: false, lastX: 0, lastY: 0 });

  // ── Mouse / Touch handlers ──────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onDown = (clientX, clientY) => {
      drag.current = { active: true, lastX: clientX, lastY: clientY };
      autoRot.current = false;
      canvas.style.cursor = 'grabbing';
    };
    const onMove = (clientX, clientY) => {
      if (!drag.current.active) return;
      const dx = clientX - drag.current.lastX;
      const dy = clientY - drag.current.lastY;
      rotY.current += dx * 0.008;           // 0.008 rad per pixel — feels natural
      rotX.current += dy * 0.006;
      // Clamp X so the skeleton doesn't flip upside-down
      rotX.current = Math.max(-Math.PI / 2.5, Math.min(Math.PI / 2.5, rotX.current));
      drag.current.lastX = clientX;
      drag.current.lastY = clientY;
    };
    const onUp = () => {
      drag.current.active = false;
      canvas.style.cursor = 'grab';
      // Resume slow auto-rotation after 2 s of inactivity
      setTimeout(() => { autoRot.current = true; }, 2000);
    };

    // Mouse
    const mouseDown  = (e) => { e.preventDefault(); onDown(e.clientX, e.clientY); };
    const mouseMove  = (e) => { onMove(e.clientX, e.clientY); };
    const mouseUp    = ()  => { onUp(); };

    // Touch (single-finger drag)
    const touchStart = (e) => { if (e.touches.length === 1) { e.preventDefault(); onDown(e.touches[0].clientX, e.touches[0].clientY); } };
    const touchMove  = (e) => { if (e.touches.length === 1) { e.preventDefault(); onMove(e.touches[0].clientX, e.touches[0].clientY); } };
    const touchEnd   = ()  => { onUp(); };

    canvas.addEventListener('mousedown',  mouseDown,  { passive: false });
    window.addEventListener('mousemove',  mouseMove);
    window.addEventListener('mouseup',    mouseUp);
    canvas.addEventListener('touchstart', touchStart, { passive: false });
    canvas.addEventListener('touchmove',  touchMove,  { passive: false });
    canvas.addEventListener('touchend',   touchEnd);
    canvas.style.cursor = 'grab';

    return () => {
      canvas.removeEventListener('mousedown',  mouseDown);
      window.removeEventListener('mousemove',  mouseMove);
      window.removeEventListener('mouseup',    mouseUp);
      canvas.removeEventListener('touchstart', touchStart);
      canvas.removeEventListener('touchmove',  touchMove);
      canvas.removeEventListener('touchend',   touchEnd);
    };
  }, []);

  // ── Snap buttons: preset angles ────────────────────────────────────────────
  const snapFront = () => { rotY.current = 0;           rotX.current = 0.15;  autoRot.current = false; };
  const snapSide  = () => { rotY.current = Math.PI / 2; rotX.current = 0.1;   autoRot.current = false; };
  const snapBack  = () => { rotY.current = Math.PI;     rotX.current = 0.15;  autoRot.current = false; };
  const snapTop   = () => { rotY.current = 0;           rotX.current = -1.2;  autoRot.current = false; };
  const resetAuto = () => { rotY.current = 0;           rotX.current = 0.15;  autoRot.current = true;  };

  // ── RAF draw loop ──────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const HALF = W / 2;
    const SXYZ = H * 0.82;
    const FOCAL = 500;
    const MS_PER_FRAME = 1000 / (fps || 30);

    const CX_LEFT  = HALF / 2;
    const CX_RIGHT = HALF + HALF / 2;
    const CY = H / 2 + 20;

    function draw(ts) {
      // Advance animation frame
      if (ts - lastTick.current >= MS_PER_FRAME) {
        const maxLen = Math.max(refFrames?.length || 0, traineeFrames?.length || 0);
        if (maxLen > 0) frameIdx.current = (frameIdx.current + 1) % maxLen;
        lastTick.current = ts;
      }

      // Auto-rotate slowly when idle
      if (autoRot.current) rotY.current += 0.007;

      // Background
      ctx.fillStyle = '#0b0f19';
      ctx.fillRect(0, 0, W, H);

      // Divider
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(HALF, 0); ctx.lineTo(HALF, H); ctx.stroke();

      // Ground grids
      [CX_LEFT, CX_RIGHT].forEach(cx => {
        const GY = H * 0.88;
        ctx.strokeStyle = 'rgba(0,180,255,0.07)'; ctx.lineWidth = 1;
        for (let i = -3; i <= 3; i++) {
          ctx.beginPath(); ctx.moveTo(cx, GY * 0.72); ctx.lineTo(cx + i * 28, GY); ctx.stroke();
        }
        for (let j = 0; j <= 4; j++) {
          const pct = j / 4, y = GY * 0.72 + (GY - GY * 0.72) * pct, sp = pct * 130;
          ctx.beginPath(); ctx.moveTo(cx - sp, y); ctx.lineTo(cx + sp, y); ctx.stroke();
        }
      });

      // Draw both panels with shared rotation
      const fi   = frameIdx.current;
      const refLms = refFrames?.[fi % (refFrames?.length || 1)]   || null;
      const trLms  = traineeFrames?.[fi % (traineeFrames?.length || 1)] || null;
      const isSlowMo = fps <= 5;

      drawPanel(ctx, refLms, rotY.current, rotX.current, CX_LEFT,  CY, SXYZ, FOCAL, 0,    HALF, 'MASTER REFERENCE', isSlowMo);
      drawPanel(ctx, trLms,  rotY.current, rotX.current, CX_RIGHT, CY, SXYZ, FOCAL, HALF, W,    'YOUR CAPTURE',     isSlowMo);

      // Empty-state messages
      const showMsg = (txt, cx, clipL, clipR) => {
        ctx.save();
        ctx.beginPath(); ctx.rect(clipL, 0, clipR - clipL, H); ctx.clip();
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '12px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(txt, cx, CY);
        ctx.restore();
      };
      if (!refFrames)    showMsg('Loading Reference...', CX_LEFT,  0,    HALF);
      if (!traineeFrames) showMsg('No Capture Data',    CX_RIGHT, HALF, W);

      // Drag hint (shown only when auto-rotating)
      if (autoRot.current) {
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('🖱 Drag to rotate · Pinch to tilt', W / 2, 8);
      }

      rafRef.current = requestAnimationFrame(draw);
    }

    rafRef.current = requestAnimationFrame(draw);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [refFrames, traineeFrames, fps]);

  return (
    <div style={{ position: 'relative' }}>
      {/* View-angle snap buttons */}
      <div style={{
        display: 'flex', gap: '6px', marginBottom: '8px',
        justifyContent: 'center', flexWrap: 'wrap',
      }}>
        {[
          { label: '⬛ Front',    fn: snapFront },
          { label: '◀  Side',    fn: snapSide  },
          { label: '⬛ Back',    fn: snapBack  },
          { label: '⬇️  Top',    fn: snapTop   },
          { label: '↺ Auto',     fn: resetAuto },
        ].map(({ label, fn }) => (
          <button
            key={label}
            onClick={fn}
            style={{
              fontSize: '0.72rem', padding: '3px 10px',
              borderRadius: '999px', border: '1px solid rgba(0,212,255,0.3)',
              background: 'rgba(0,212,255,0.08)', color: '#00d4ff',
              cursor: 'pointer', transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,212,255,0.2)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(0,212,255,0.08)'}
          >
            {label}
          </button>
        ))}
      </div>

      <canvas
        ref={canvasRef}
        width={800}
        height={400}
        className={styles.skeletonCanvas}
        title="Drag to rotate · Touch-drag on mobile"
      />

      <p style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.2)', textAlign: 'center', marginTop: '4px' }}>
        🖱 Drag canvas to rotate · 📱 Touch-drag on mobile
      </p>
    </div>
  );
}

// ── RepResultPanel ─────────────────────────────────────────────────────────────
export default function RepResultPanel({ moveId, moveName, confidence, inferenceMs, traineeFrames, refFrames, aiFeedback, errors }) {
  const [slowMo, setSlowMo] = useState(false);

  const formatFeedback = (text) => {
    if (!text) return null;
    return text.split('\n').map((line, i) => {
      if (line.trim().startsWith('-')) return <li key={i}>{line.replace(/^-/, '').trim()}</li>;
      if (line.trim().length === 0)    return <br key={i} />;
      return <p key={i}>{line}</p>;
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>🥋 Rep Analysis: {moveName || moveId}</h2>
        <div className={styles.stats}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: '#00d4ff', cursor: 'pointer', background: 'rgba(0,212,255,0.1)', padding: '4px 10px', borderRadius: 15, border: '1px solid rgba(0,212,255,0.3)' }}>
            <input type="checkbox" checked={slowMo} onChange={e => setSlowMo(e.target.checked)} style={{ cursor: 'pointer' }} />
            🐢 Slow Mo
          </label>
          <span className={styles.badgeConfidence}>Confidence: {(confidence * 100).toFixed(1)}%</span>
          <span className={styles.badgeTime}>⚡ {inferenceMs?.toFixed(1)} ms</span>
        </div>
      </div>

      <div className={styles.skeletonSection}>
        <DualSkeletonCanvas refFrames={refFrames} traineeFrames={traineeFrames} fps={slowMo ? 5 : 30} />
      </div>

      <div className={styles.analysisSection}>
        <div className={styles.feedbackCard}>
          <h3>🤖 AI Sensei Feedback</h3>
          <div className={styles.feedbackContent}>
            {aiFeedback ? (
              <ul>{formatFeedback(aiFeedback)}</ul>
            ) : (
              <p className={styles.loadingFeedback}>Analyzing movement patterns...</p>
            )}
          </div>
        </div>

        <div className={styles.errorsCard}>
          <h3>📊 Joint Deviation Analysis</h3>
          {errors && errors.length > 0 ? (
            <div className={styles.errorsList}>
              {errors.map((err, i) => (
                <div key={i} className={styles.errorItem}>
                  <div className={styles.errorHeader}>
                    <span className={styles.errorJoint}>{err.joint.replace('_', ' ')}</span>
                    <span className={`${styles.errorStatus} ${styles[err.status]}`}>
                      {err.status.toUpperCase()}
                    </span>
                  </div>
                  <div className={styles.errorBars}>
                    <div className={styles.errorMetric}>
                      <span className={styles.metricLabel}>You:</span>
                      <span className={styles.metricValue}>{err.user_val}°</span>
                    </div>
                    <div className={styles.errorMetric}>
                      <span className={styles.metricLabel}>Master:</span>
                      <span className={styles.metricValue}>{err.ref_val}°</span>
                    </div>
                    <div className={styles.errorMetric}>
                      <span className={styles.metricLabel}>Error:</span>
                      <span className={styles.metricValueDelta}>Δ {err.mean_error}°</span>
                    </div>
                  </div>
                  <div className={styles.errorDesc}>
                    <small>Target Range: {err.target_range}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.perfectForm}>
              <span className={styles.perfectIcon}>✨</span>
              <p>Excellent form! No significant deviations detected.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
