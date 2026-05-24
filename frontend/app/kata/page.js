'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useAuth } from '../context/AuthContext';
import styles from './kata.module.css';

// ─── Constants ─────────────────────────────────────────────────────────────────
const WS_URL      = 'ws://localhost:8000/api/kata/ws';
const MOVE_NAMES  = ['GedanBarai', 'Gyakudzuki', 'MaeGeri'];

const MOVE_DISPLAY = {
  GedanBarai: '🛡️ Gedan Barai',
  Gyakudzuki: '👊 Gyaku Zuki',
  MaeGeri:    '🦵 Mae Geri',
  Disagree:   '🤔 Disagree',
};

// MediaPipe skeleton connections (same set as used in train/page.js)
const POSE_CONNECTIONS = [
  [11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],
  [23,24],[23,25],[25,27],[27,29],[27,31],[24,26],[26,28],[28,30],[28,32],
  [15,17],[15,19],[15,21],[16,18],[16,20],[16,22],
  [0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],
];

// Colour by body region
function connectionColor(a, b) {
  const torso  = new Set([11,12,23,24]);
  const arms   = new Set([13,14,15,16,17,18,19,20,21,22]);
  const legs   = new Set([25,26,27,28,29,30,31,32]);
  const face   = new Set([0,1,2,3,4,5,6,7,8]);
  if (torso.has(a) || torso.has(b))  return 'rgba(0, 212, 255, 0.85)';
  if (arms.has(a)  || arms.has(b))   return 'rgba(124, 58, 237, 0.85)';
  if (legs.has(a)  || legs.has(b))   return 'rgba(0, 220, 120, 0.85)';
  if (face.has(a)  || face.has(b))   return 'rgba(255, 180, 0, 0.7)';
  return 'rgba(200, 200, 200, 0.6)';
}

function confClass(c) {
  if (c >= 0.85) return 'high';
  if (c >= 0.60) return 'medium';
  return 'low';
}

// Global MediaPipe singleton
let globalPose = null;

// ─── Skeleton Canvas ────────────────────────────────────────────────────────────
function SkeletonCanvas({ landmarksRef, canvasRef }) {
  // Canvas is drawn externally via the frame pump — just render the element
  return (
    <canvas
      ref={canvasRef}
      style={{
        position:  'absolute',
        top: 0, left: 0,
        width:  '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
}

// ─── Component ──────────────────────────────────────────────────────────────────
export default function KataPage() {
  useAuth();   // auth guard if needed

  // ── Media state
  const [mode,        setMode]        = useState('idle');
  const [cameraError, setCameraError] = useState('');

  // ── WebSocket / inference state
  const [wsStatus,    setWsStatus]    = useState('disconnected');
  const [frameCount,  setFrameCount]  = useState(0);
  const [bufferFill,  setBufferFill]  = useState(0);
  const [dualResult,  setDualResult]  = useState(null);
  const [sinv1Result, setSinv1Result] = useState(null);
  const [consensus,   setConsensus]   = useState(null);

  // ── Refs
  const videoRef       = useRef(null);
  const canvasRef      = useRef(null);
  const fileInputRef   = useRef(null);
  const wsRef          = useRef(null);
  const poseRef        = useRef(null);
  const streamRef      = useRef(null);
  const rafRef         = useRef(null);
  const sendingRef     = useRef(false);
  const landmarksRef   = useRef(null);   // latest landmark array for canvas draw

  // ─── Cleanup on unmount ──────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      sendingRef.current = false;
      if (rafRef.current)    cancelAnimationFrame(rafRef.current);
      if (wsRef.current)     wsRef.current.close();
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // ─── Draw skeleton on canvas ─────────────────────────────────────────────────
  const drawSkeleton = useCallback((landmarks) => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video) return;

    canvas.width  = video.videoWidth  || video.clientWidth;
    canvas.height = video.videoHeight || video.clientHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const W = canvas.width;
    const H = canvas.height;

    // Draw connections
    ctx.lineWidth = 2.5;
    for (const [a, b] of POSE_CONNECTIONS) {
      if (a >= landmarks.length || b >= landmarks.length) continue;
      const lmA = landmarks[a], lmB = landmarks[b];
      if ((lmA.visibility ?? 1) < 0.3 || (lmB.visibility ?? 1) < 0.3) continue;
      ctx.strokeStyle = connectionColor(a, b);
      ctx.beginPath();
      ctx.moveTo(lmA.x * W, lmA.y * H);
      ctx.lineTo(lmB.x * W, lmB.y * H);
      ctx.stroke();
    }

    // Draw joint dots
    for (let i = 0; i < landmarks.length; i++) {
      const lm = landmarks[i];
      if ((lm.visibility ?? 1) < 0.3) continue;
      ctx.beginPath();
      ctx.arc(lm.x * W, lm.y * H, 4, 0, 2 * Math.PI);
      ctx.fillStyle = i < 11 ? 'rgba(255,180,0,0.9)' : 'rgba(255,255,255,0.85)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.5)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }, []);

  // ─── Open WebSocket ──────────────────────────────────────────────────────────
  const openWS = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    setWsStatus('connecting');

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen  = () => setWsStatus('live');
    ws.onerror = () => setWsStatus('disconnected');
    ws.onclose = () => setWsStatus('disconnected');

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        setFrameCount(msg.frame_count ?? 0);
        setBufferFill(msg.buffer_fill ?? 0);
        if (msg.status === 'live') {
          setDualResult(msg.dual_stem  ?? null);
          setSinv1Result(msg.single_v1 ?? null);
          setConsensus(msg.consensus   ?? null);
        }
      } catch (_) {}
    };
  }, []);

  // ─── Send one landmark frame to WS ───────────────────────────────────────────
  const sendFrame = useCallback((landmarks) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({
      landmarks: landmarks.map(lm => ({
        x:          lm.x,
        y:          lm.y,
        z:          lm.z          ?? 0,
        visibility: lm.visibility ?? 1.0,
      })),
    }));
  }, []);

  // ─── Initialize MediaPipe ─────────────────────────────────────────────────────
  const initMediaPipe = useCallback(async () => {
    if (!globalPose) {
      const { Pose } = await import('@mediapipe/pose');
      globalPose = new Pose({
        locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${f}`,
      });
      globalPose.setOptions({
        modelComplexity:        1,
        smoothLandmarks:        true,
        enableSegmentation:     false,
        minDetectionConfidence: 0.5,
        minTrackingConfidence:  0.5,
      });
    }

    globalPose.onResults((results) => {
      if (!results.poseLandmarks) return;
      const lms = Array.from(results.poseLandmarks);
      landmarksRef.current = lms;
      drawSkeleton(lms);      // draw on canvas immediately
      sendFrame(lms);          // stream to backend
    });

    poseRef.current = globalPose;
  }, [drawSkeleton, sendFrame]);

  // ─── Frame pump ──────────────────────────────────────────────────────────────
  const pumpFrames = useCallback(() => {
    const pump = async () => {
      if (!sendingRef.current) return;
      if (videoRef.current && poseRef.current && !videoRef.current.paused) {
        await poseRef.current.send({ image: videoRef.current });
      }
      rafRef.current = requestAnimationFrame(pump);
    };
    pump();
  }, []);

  // ─── Start Camera ─────────────────────────────────────────────────────────────
  const startCamera = useCallback(async () => {
    setCameraError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setMode('camera');
      await initMediaPipe();
      openWS();
      sendingRef.current = true;
      pumpFrames();
    } catch (_) {
      setCameraError('Camera access denied or not available.');
    }
  }, [initMediaPipe, openWS, pumpFrames]);

  // ─── Start Video ──────────────────────────────────────────────────────────────
  const handleFileChange = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMode('video');
    const url = URL.createObjectURL(file);
    videoRef.current.src = url;
    videoRef.current.load();
    await videoRef.current.play();
    await initMediaPipe();
    openWS();
    sendingRef.current = true;
    pumpFrames();
  }, [initMediaPipe, openWS, pumpFrames]);

  // ─── Stop ─────────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    sendingRef.current = false;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (wsRef.current)  wsRef.current.close();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
      videoRef.current.src = '';
    }
    // Clear skeleton canvas
    const canvas = canvasRef.current;
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);

    landmarksRef.current = null;
    setMode('idle');
    setWsStatus('disconnected');
    setDualResult(null);
    setSinv1Result(null);
    setConsensus(null);
    setFrameCount(0);
    setBufferFill(0);
  }, []);

  // ─── ModelCard subcomponent ───────────────────────────────────────────────────
  const ModelCard = useCallback(({ title, result }) => {
    const cc = result ? confClass(result.confidence) : null;
    return (
      <div className={`${styles.modelCard} ${result ? styles.active : ''}`}>
        <div className={styles.modelHeader}>
          <span className={styles.modelName}>{title}</span>
          {result && (
            <span className={`${styles.modelConf} ${styles[cc]}`}>
              {(result.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <div className={`${styles.moveName} ${!result ? styles.buffering : ''}`}>
          {result ? (MOVE_DISPLAY[result.move] ?? result.move) : '— Buffering —'}
        </div>
        {result?.all_probs && (
          <div className={styles.probBars}>
            {MOVE_NAMES.map((name, i) => {
              const p   = result.all_probs[i] ?? 0;
              const bar = confClass(p);
              return (
                <div key={name} className={styles.probRow}>
                  <span className={styles.probLabel}>{name}</span>
                  <div className={styles.probTrack}>
                    <div
                      className={`${styles.probBar} ${styles[bar]}`}
                      style={{ width: `${(p * 100).toFixed(1)}%` }}
                    />
                  </div>
                  <span className={styles.probPct}>{(p * 100).toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }, []);

  const bufferPct = Math.round((bufferFill / 30) * 100);

  // ─── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      {/* ── Header ── */}
      <div className={styles.header}>
        <Link href="/train" className={styles.backBtn}>← Back</Link>
        <div className={styles.headerTitle}>
          <span>🥋</span>
          <span>Full Kata Practice</span>
        </div>
        <div className={`${styles.statusBadge} ${styles[wsStatus]}`}>
          <div className={styles.statusDot} />
          {wsStatus === 'connecting'   && 'Connecting…'}
          {wsStatus === 'live'         && '🟢 Live'}
          {wsStatus === 'disconnected' && 'Offline'}
        </div>
      </div>

      {/* ── Body ── */}
      <div className={styles.body}>

        {/* ────────── Camera / Video panel ────────── */}
        <div className={styles.cameraPanel}>
          <div className={styles.cameraToolbar}>
            {mode === 'idle' ? (
              <>
                <button
                  id="kata-start-camera"
                  className={`${styles.toolbarBtn} ${styles.primary}`}
                  onClick={startCamera}
                >
                  📹 Start Camera
                </button>
                <button
                  id="kata-upload-video"
                  className={`${styles.toolbarBtn} ${styles.secondary}`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  📁 Upload Video
                </button>
                <input
                  type="file"
                  accept="video/*"
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                />
              </>
            ) : (
              <button
                id="kata-stop"
                className={`${styles.toolbarBtn} ${styles.danger}`}
                onClick={stop}
              >
                ⏹ Stop
              </button>
            )}
            {cameraError && (
              <span style={{ color: '#ff4646', fontSize: '0.8rem' }}>{cameraError}</span>
            )}
          </div>

          {/* Video + skeleton canvas stacked */}
          <div className={styles.videoArea}>
            <video
              ref={videoRef}
              id="kata-video"
              className={styles.videoFeed}
              muted
              playsInline
              style={{ display: mode !== 'idle' ? 'block' : 'none' }}
            />
            {/* Skeleton canvas drawn over the video */}
            <canvas
              ref={canvasRef}
              style={{
                position:      'absolute',
                top: 0, left:  0,
                width:         '100%',
                height:        '100%',
                pointerEvents: 'none',
                display:       mode !== 'idle' ? 'block' : 'none',
              }}
            />
            {mode === 'idle' && (
              <div className={styles.placeholderOverlay}>
                <span>🥋</span>
                <p>Start camera or upload a kata video to begin real-time analysis</p>
              </div>
            )}
          </div>
        </div>

        {/* ────────── Dashboard panel ────────── */}
        <div className={styles.dashPanel}>
          <div className={styles.dashTitle}>⚡ Live Kata Analysis</div>

          {mode === 'idle' ? (
            <div className={styles.idleHint}>
              <h3>How it works</h3>
              <p>
                The AI maintains a <strong>30-frame sliding window</strong> over your
                pose landmarks, running inference every 3rd frame for a smooth,
                lag-free experience. The skeleton is drawn live on the video feed.
              </p>
              <p style={{ marginTop: '0.6rem', color: '#666' }}>
                Supported moves: Gedan Barai · Gyaku Zuki · Mae Geri
              </p>
            </div>
          ) : (
            <>
              {/* Buffer fill */}
              <div className={styles.bufferSection}>
                <div className={styles.bufferLabel}>
                  <span>Frame Buffer</span>
                  <span>{bufferFill} / 30</span>
                </div>
                <div className={styles.bufferTrack}>
                  <div className={styles.bufferFill} style={{ width: `${bufferPct}%` }} />
                </div>
              </div>

              {/* Model confidence cards */}
              <ModelCard title="🧠 Dual-Stem"  result={dualResult}  />
              <ModelCard title="⚡ Single V1"  result={sinv1Result} />

              {/* Consensus */}
              {(dualResult || sinv1Result) && (
                <div
                  className={`${styles.consensusCard} ${
                    consensus === 'Disagree' ? styles.disagree : ''
                  }`}
                >
                  <div className={styles.consensusLabel}>
                    {consensus === 'Disagree' ? '⚠️ Models Disagree' : '✅ Consensus'}
                  </div>
                  <div className={styles.consensusMove}>
                    {consensus ? (MOVE_DISPLAY[consensus] ?? consensus) : '—'}
                  </div>
                </div>
              )}

              {/* Frame counter */}
              <div className={styles.frameCounter}>
                Frames processed: {frameCount}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
