'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useAuth } from '../context/AuthContext';
import { drawSkeleton } from '../utils/skeletonDraw';
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
  // Single flat result from the Dual-Stem model
  const [liveResult,  setLiveResult]  = useState(null);   // {move, confidence, all_probs}

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

  // ─── Draw skeleton using shared utility ─────────────────────────────────────
  const drawSkeletonOnCanvas = useCallback((landmarks) => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video) return;

    // Sync canvas size to actual video display size
    const W = video.clientWidth  || video.videoWidth;
    const H = video.clientHeight || video.videoHeight;
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width  = W;
      canvas.height = H;
    }

    const ctx = canvas.getContext('2d');
    drawSkeleton(ctx, W, H, landmarks, { mirrored: false });
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
        // Backend now sends flat keys: move, confidence, all_probs
        if (msg.status === 'live' && msg.move) {
          setLiveResult({
            move:       msg.move,
            confidence: msg.confidence ?? 0,
            all_probs:  msg.all_probs  ?? [],
          });
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
      drawSkeletonOnCanvas(lms);   // draw on canvas immediately
      sendFrame(lms);              // stream to backend
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
    setLiveResult(null);
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
                pose landmarks. The Dual-Stem model classifies your move in real-time
                as frames arrive — no buffering delay once the window is full.
              </p>
              <p style={{ marginTop: '0.6rem', color: '#666' }}>
                Supported moves: Gedan Barai · Gyaku Zuki · Mae Geri
              </p>
            </div>
          ) : (
            <>
              {/* Frame buffer progress */}
              <div className={styles.bufferSection}>
                <div className={styles.bufferLabel}>
                  <span>Frame Buffer</span>
                  <span>{bufferFill} / 30</span>
                </div>
                <div className={styles.bufferTrack}>
                  <div className={styles.bufferFill} style={{ width: `${bufferPct}%` }} />
                </div>
              </div>

              {/* Live result card — Dual-Stem only */}
              <div className={`${styles.modelCard} ${liveResult ? styles.active : ''}`}>
                <div className={styles.modelHeader}>
                  <span className={styles.modelName}>🧠 Dual-Stem AI</span>
                  {liveResult && (
                    <span className={`${styles.modelConf} ${styles[confClass(liveResult.confidence)]}`}>
                      {(liveResult.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className={`${styles.moveName} ${!liveResult ? styles.buffering : ''}`}>
                  {liveResult
                    ? (MOVE_DISPLAY[liveResult.move] ?? liveResult.move)
                    : '— Buffering —'}
                </div>
                {liveResult?.all_probs?.length > 0 && (
                  <div className={styles.probBars}>
                    {MOVE_NAMES.map((name, i) => {
                      const p   = liveResult.all_probs[i] ?? 0;
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
