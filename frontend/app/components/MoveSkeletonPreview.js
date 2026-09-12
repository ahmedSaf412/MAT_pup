'use client';
import { useEffect, useRef, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const VIDEO_MOVES = new Set(['mae_geri', 'gyaku_zuki', 'gedan_barai']);

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

function project(lm, rotY, CX, CY, SXYZ, FOCAL) {
  const wx = (lm.x - 0.5) * SXYZ;
  const wy = (lm.y - 0.5) * SXYZ;
  const wz = (lm.z  || 0) * SXYZ * 0.6;
  const rx =  wx * Math.cos(rotY) - wz * Math.sin(rotY);
  const rz =  wx * Math.sin(rotY) + wz * Math.cos(rotY);
  const s  = FOCAL / (FOCAL + rz);
  return { sx: CX + rx * s, sy: CY + wy * s, sz: rz, vis: lm.visibility ?? 1 };
}

// Draw one skeleton panel onto context at given CX pivot
function drawPanel(ctx, lms, rotY, CX, CY, SXYZ, FOCAL, clipLeft, clipRight, label) {
  if (!lms) return;

  const pts = lms.map(lm => project(lm, rotY, CX, CY, SXYZ, FOCAL));

  ctx.save();
  ctx.beginPath();
  ctx.rect(clipLeft, 0, clipRight - clipLeft, ctx.canvas.height);
  ctx.clip();

  // Bones — back to front
  const lines = POSE_CONNECTIONS
    .filter(([i, j]) => pts[i] && pts[j] && pts[i].vis > 0.25 && pts[j].vis > 0.25)
    .map(([i, j]) => ({ i, j, depth: (pts[i].sz + pts[j].sz) / 2 }))
    .sort((a, b) => b.depth - a.depth);

  lines.forEach(({ i, j, depth }) => {
    const p1 = pts[i], p2 = pts[j];
    const dn = Math.max(0, Math.min(1, (100 - depth) / 200));
    ctx.strokeStyle = `rgba(0,212,255,${0.3 + dn * 0.65})`;
    ctx.lineWidth   = 1.5 + dn * 2.5;
    ctx.lineCap     = 'round';
    ctx.beginPath(); ctx.moveTo(p1.sx, p1.sy); ctx.lineTo(p2.sx, p2.sy); ctx.stroke();
  });

  // Joints — back to front
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

  // Panel label
  ctx.fillStyle    = 'rgba(0,212,255,0.55)';
  ctx.font         = 'bold 9px monospace';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'bottom';
  ctx.fillText(label, (clipLeft + clipRight) / 2, ctx.canvas.height - 6);

  ctx.restore();
}

// ── 3D Canvas — split front + side ──────────────────────────────────────────
function SkeletonCanvas3D({ frontFrames, sideFrames, fps }) {
  const canvasRef = useRef(null);
  const rafRef    = useRef(null);
  const frameIdx  = useRef(0);
  const lastTick  = useRef(0);
  const angle     = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const HALF = W / 2;
    const SXYZ  = H * 0.82;
    const FOCAL = 500;
    const MS_PER_FRAME = 1000 / (fps || 30);

    // Centers for each panel
    const CX_LEFT  = HALF / 2;      // center of left panel
    const CX_RIGHT = HALF + HALF / 2; // center of right panel
    const CY = H / 2 + 10;

    function draw(ts) {
      // Advance frame
      if (ts - lastTick.current >= MS_PER_FRAME) {
        if (frontFrames?.length) frameIdx.current = (frameIdx.current + 1) % frontFrames.length;
        lastTick.current = ts;
      }
      angle.current += 0.007;
      // Front panel slight oscillation to show depth; side panel offset 90°
      const rotFront = Math.sin(angle.current * 0.4) * 0.35;         // ±20°
      const rotSide  = Math.PI / 2 + Math.sin(angle.current * 0.4) * 0.2; // 90° ±11°

      // Background
      ctx.fillStyle = '#060a14';
      ctx.fillRect(0, 0, W, H);

      // Divider line
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth   = 1;
      ctx.beginPath(); ctx.moveTo(HALF, 0); ctx.lineTo(HALF, H); ctx.stroke();

      // Ground grids for each panel
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

      const fi = frameIdx.current;
      const frontLms = frontFrames?.[fi] || null;
      const sideLms  = sideFrames?.[fi % (sideFrames?.length || 1)] || null;

      drawPanel(ctx, frontLms, rotFront, CX_LEFT,  CY, SXYZ * 1.0, FOCAL, 0,    HALF, 'FRONT VIEW');
      drawPanel(ctx, sideLms,  rotSide,  CX_RIGHT, CY, SXYZ * 1.0, FOCAL, HALF, W,    'SIDE VIEW');

      // Loading states per panel
      const showMsg = (txt, cx, clipL, clipR) => {
        ctx.save();
        ctx.beginPath(); ctx.rect(clipL, 0, clipR - clipL, H); ctx.clip();
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '12px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(txt, cx, CY);
        ctx.restore();
      };
      if (!frontFrames) showMsg('⏳ Loading front…',  CX_LEFT,  0,    HALF);
      if (!sideFrames)  showMsg('⏳ Loading side…',   CX_RIGHT, HALF, W);
      if (frontFrames?.length === 0) showMsg('⚠ No front data', CX_LEFT,  0,    HALF);
      if (sideFrames?.length  === 0) showMsg('⚠ No side data',  CX_RIGHT, HALF, W);

      // Frame counter
      if (frontFrames?.length) {
        ctx.fillStyle = 'rgba(0,212,255,0.4)';
        ctx.font = 'bold 8px monospace'; ctx.textAlign = 'right'; ctx.textBaseline = 'bottom';
        ctx.fillText(`${fi + 1}/${frontFrames.length}`, W - 8, H - 18);
      }

      rafRef.current = requestAnimationFrame(draw);
    }

    rafRef.current = requestAnimationFrame(draw);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [frontFrames, sideFrames, fps]);

  return (
    <canvas ref={canvasRef} width={640} height={370}
      style={{ width: '100%', height: '100%', display: 'block' }} />
  );
}

// ── Reference video ───────────────────────────────────────────────────────────
function ReferenceVideo({ move }) {
  const [view, setView] = useState('front');
  const [err,  setErr]  = useState(false);
  const hasVideo = move?.id && VIDEO_MOVES.has(move.id);

  if (!hasVideo) return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', minHeight:240, color:'rgba(255,255,255,0.3)', padding:20 }}>
      <span style={{ fontSize:'2.5rem', marginBottom:8 }}>📂</span>
      <p style={{ margin:0, fontSize:'0.82rem', textAlign:'center' }}>
        {move?.id ? 'No reference video for this move yet' : 'Select a specific move to see a reference video'}
      </p>
    </div>
  );

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', gap:8, padding:'8px 10px 12px' }}>
      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
        {['front','side'].map(v => (
          <button key={v} onClick={() => { setView(v); setErr(false); }}
            style={{ padding:'5px 14px', borderRadius:7, border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.78rem', transition:'all .2s',
              background: view===v ? 'rgba(0,212,255,0.18)' : 'rgba(255,255,255,0.05)',
              color:      view===v ? '#00d4ff'               : 'rgba(255,255,255,0.4)' }}>
            {v === 'front' ? '⬆ Front' : '➡ Side'}
          </button>
        ))}
        <span style={{ marginLeft:'auto', fontSize:'0.7rem', color:'rgba(255,255,255,0.25)' }}>master demonstration</span>
      </div>
      <div style={{ position:'relative', flex:1, borderRadius:10, overflow:'hidden', background:'#060a12', minHeight:250 }}>
        {!err
          ? <video key={`${move.id}-${view}`}
              src={`${API_BASE}/api/video/${move.id}/${view}`}
              autoPlay loop muted playsInline controls
              style={{ width:'100%', height:'100%', objectFit:'contain', display:'block' }}
              onError={() => setErr(true)} />
          : <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', color:'rgba(255,255,255,0.3)', padding:20 }}>
              <span style={{ fontSize:'2rem', marginBottom:8 }}>📹</span>
              <p style={{ margin:0, fontSize:'0.78rem', textAlign:'center' }}>Video not found on server</p>
            </div>
        }
      </div>
      <p style={{ fontSize:'0.72rem', color:'rgba(255,255,255,0.22)', textAlign:'center', margin:0 }}>🎓 Study the master&apos;s form before you practice</p>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function MoveSkeletonPreview({ move, defaultTab = 'skeleton' }) {
  const [tab,         setTab]         = useState(defaultTab);
  const [frontFrames, setFrontFrames] = useState(null);
  const [sideFrames,  setSideFrames]  = useState(null);
  const [fps,         setFps]         = useState(30);

  useEffect(() => {
    if (!move?.id || !VIDEO_MOVES.has(move.id)) {
      setFrontFrames([]); setSideFrames([]); return;
    }
    setFrontFrames(null); setSideFrames(null);
    const ctrl = new AbortController();

    const fetchView = (view, setter) =>
      fetch(`${API_BASE}/api/video/${move.id}/landmarks?view=${view}`, { signal: ctrl.signal })
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(data => {
          setFps(Math.round(data.fps) || 30);
          setter((data.frames || []).filter(Boolean));
        })
        .catch(err => { if (err.name !== 'AbortError') { console.warn(`${view} landmarks:`, err.message); setter([]); } });

    fetchView('front', setFrontFrames);
    fetchView('side',  setSideFrames);

    return () => ctrl.abort();
  }, [move?.id]);

  return (
    <div style={{ display:'flex', flexDirection:'column', background:'rgba(255,255,255,0.025)', border:'1px solid rgba(255,255,255,0.07)', borderRadius:14, overflow:'hidden', minHeight:380 }}>
      {/* Tabs */}
      <div style={{ display:'flex', padding:'10px 10px 0', gap:4 }}>
        {[['skeleton','🤖 AI Preview'],['video','📹 Reference']].map(([key,label]) => (
          <button key={key} onClick={() => setTab(key)}
            style={{ flex:1, padding:'8px 10px', borderRadius:'8px 8px 0 0', border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.8rem', transition:'all .2s',
              borderBottom: tab===key ? '2px solid #00d4ff' : '2px solid transparent',
              background:   tab===key ? 'rgba(0,212,255,0.07)' : 'transparent',
              color:        tab===key ? '#00d4ff' : 'rgba(255,255,255,0.38)' }}>
            {label}
          </button>
        ))}
      </div>
      <div style={{ fontSize:'0.68rem', fontWeight:700, letterSpacing:'0.09em', textTransform:'uppercase', color:'rgba(255,255,255,0.28)', padding:'5px 14px 2px' }}>
        {move?.name || 'Select a move'}
      </div>
      <div style={{ flex:1 }}>
        {tab === 'skeleton'
          ? <SkeletonCanvas3D frontFrames={frontFrames} sideFrames={sideFrames} fps={fps} />
          : <ReferenceVideo move={move} />
        }
      </div>
    </div>
  );
}