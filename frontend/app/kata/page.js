'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useAuth } from '../context/AuthContext';
import { drawSkeleton } from '../utils/skeletonDraw';
import styles from './kata.module.css';

// ─── Constants ─────────────────────────────────────────────────────────────────
const WS_URL      = 'ws://localhost:8000/api/kata/ws';
const MOVE_NAMES  = ['GedanBarai', 'Gyakudzuki', 'MaeGeri'];
const FPS         = 30;
const FRAME_DT    = 1 / FPS;

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

// ─── Component ──────────────────────────────────────────────────────────────────
export default function KataPage() {
  useAuth();

  // ── Media / mode state
  const [mode,          setMode]          = useState('idle');      // idle | camera | analyzing | replaying
  const [cameraError,   setCameraError]   = useState('');

  // ── WebSocket / inference state
  const [wsStatus,      setWsStatus]      = useState('disconnected');  // disconnected | warming | connecting | live
  const [frameCount,    setFrameCount]    = useState(0);
  const [bufferFill,    setBufferFill]    = useState(0);
  const [liveResult,    setLiveResult]    = useState(null);
  const [xgbResult,     setXgbResult]     = useState(null);

  // ── Video analysis state
  const [analyzeProgress, setAnalyzeProgress] = useState(0);   // 0-100 during analysis pass
  const [analyzeTotal,    setAnalyzeTotal]    = useState(0);
  const [analyzeDone,     setAnalyzeDone]     = useState(0);

  // ── Refs
  const videoRef       = useRef(null);
  const canvasRef      = useRef(null);
  const fileInputRef   = useRef(null);
  const wsRef          = useRef(null);
  const poseRef        = useRef(null);
  const streamRef      = useRef(null);
  const rafRef         = useRef(null);
  const lastVideoTime  = useRef(-1);
  const sendingRef     = useRef(false);
  const landmarksRef   = useRef(null);

  // ── For offline replay: store (timestamp → result) map
  const replayMapRef   = useRef(null);   // Map<frameIndex, resultObj>
  const replayRafRef   = useRef(null);

  // ─── Cleanup on unmount ──────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      sendingRef.current = false;
      if (rafRef.current)      cancelAnimationFrame(rafRef.current);
      if (replayRafRef.current) cancelAnimationFrame(replayRafRef.current);
      if (wsRef.current)       wsRef.current.close();
      if (streamRef.current)   streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // ─── Draw skeleton ────────────────────────────────────────────────────────────
  const drawSkeletonOnCanvas = useCallback((landmarks) => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video) return;
    const W = video.clientWidth  || video.videoWidth;
    const H = video.clientHeight || video.videoHeight;
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width  = W;
      canvas.height = H;
    }
    const ctx = canvas.getContext('2d');
    drawSkeleton(ctx, W, H, landmarks, { mirrored: false });
  }, []);

  // ─── Open WebSocket ───────────────────────────────────────────────────────────
  const openWS = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    setWsStatus('connecting');

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onerror = () => setWsStatus('disconnected');
    ws.onclose = () => setWsStatus('disconnected');
    ws.onopen  = () => setWsStatus('connecting');   // will become 'warming' or 'live' via message

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);

        // Handle warming status — model still loading
        if (msg.status === 'warming') {
          setWsStatus('warming');
          return;
        }

        setFrameCount(msg.frame_count ?? 0);
        setBufferFill(msg.buffer_fill ?? 0);

        if (msg.status === 'live' && msg.move) {
          setWsStatus('live');
          setLiveResult({
            move:       msg.move,
            confidence: msg.confidence ?? 0,
            all_probs:  msg.all_probs  ?? [],
          });
          if (msg.xgb_move) {
            setXgbResult({
              move:       msg.xgb_move,
              confidence: msg.xgb_confidence ?? 0,
              all_probs:  msg.xgb_probs  ?? [],
            });
          }
        } else if (msg.status === 'buffering') {
          setWsStatus('live');   // connected & running, just buffering
        }
      } catch (_) {}
    };

    return ws;
  }, []);

  // ─── Send one landmark frame to WS ────────────────────────────────────────────
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

  // ─── Initialize MediaPipe ──────────────────────────────────────────────────────
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
    poseRef.current = globalPose;
  }, []);

  // ─── Frame pump (Camera Only) ─────────────────────────────────────────────────
  const pumpFrames = useCallback(() => {
    const pump = async () => {
      if (!sendingRef.current) return;
      if (videoRef.current && poseRef.current && !videoRef.current.paused) {
        const currentTime = videoRef.current.currentTime;
        if (currentTime !== lastVideoTime.current) {
          lastVideoTime.current = currentTime;
          // Set result callback for camera mode
          poseRef.current.onResults((results) => {
            if (!results.poseLandmarks) return;
            const lms = Array.from(results.poseLandmarks);
            landmarksRef.current = lms;
            drawSkeletonOnCanvas(lms);
            sendFrame(lms);
          });
          await poseRef.current.send({ image: videoRef.current });
        }
      }
      rafRef.current = requestAnimationFrame(pump);
    };
    pump();
  }, [drawSkeletonOnCanvas, sendFrame]);

  // ─── Two-Pass Video Analysis ─────────────────────────────────────────────────
  // Pass 1: Seek frame-by-frame, collect (frameIndex → {landmarks, wsResult}) headlessly
  // Pass 2: Play the video at normal speed, overlay the stored results in sync
  const processVideoTwoPass = useCallback(async () => {
    const video = videoRef.current;
    const pose  = poseRef.current;
    const ws    = wsRef.current;
    if (!video || !pose || !ws) return;

    // ── PASS 1: Analysis (video hidden, seeking frame by frame) ─────────────
    video.pause();
    // Seek to start
    await new Promise(resolve => {
      const h = () => { video.removeEventListener('seeked', h); resolve(); };
      video.addEventListener('seeked', h);
      video.currentTime = 0;
      if (video.currentTime === 0) h();
    });

    const duration   = video.duration;
    const totalFrames = Math.ceil(duration * FPS);
    setAnalyzeTotal(totalFrames);
    setAnalyzeDone(0);

    // Map of frameIndex → {landmarks, result}
    const frameStore = new Map();   // frameIndex → { landmarks }

    // Collect WS results keyed to frame send order
    const pendingResults = [];  // queue of {resolve} promises waiting for a WS result
    const resultQueue    = [];  // WS results received but not yet matched

    const originalOnMessage = ws.onmessage;
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.status === 'warming') { setWsStatus('warming'); return; }
        if (msg.status === 'live' && msg.move) {
          const result = { 
            move: msg.move, confidence: msg.confidence ?? 0, all_probs: msg.all_probs ?? [],
            xgb: msg.xgb_move ? { move: msg.xgb_move, confidence: msg.xgb_confidence ?? 0, all_probs: msg.xgb_probs ?? [] } : null
          };
          if (pendingResults.length > 0) {
            pendingResults.shift()(result);
          } else {
            resultQueue.push(result);
          }
        } else if (msg.status === 'buffering' || msg.status === 'live') {
          // No result yet — resolve with null so frame keeps moving
          if (pendingResults.length > 0) pendingResults.shift()(null);
        }
      } catch (_) {}
    };

    // Wait for model to be ready before starting pass 1
    if (wsStatus === 'warming') {
      await new Promise(resolve => {
        const check = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN && wsStatus !== 'warming') {
            clearInterval(check); resolve();
          }
        }, 500);
      });
    }

    let frameIdx = 0;
    while (sendingRef.current && video.currentTime < duration) {
      // Seek to this frame's timestamp
      const targetTime = frameIdx * FRAME_DT;
      if (targetTime > duration) break;

      await new Promise(resolve => {
        const h = () => { video.removeEventListener('seeked', h); resolve(); };
        video.addEventListener('seeked', h);
        if (Math.abs(video.currentTime - targetTime) < 0.001) { h(); return; }
        video.currentTime = targetTime;
      });

      // Extract landmarks from this frame
      let frameLandmarks = null;
      await new Promise(resolve => {
        pose.onResults((results) => {
          if (results.poseLandmarks) {
            frameLandmarks = Array.from(results.poseLandmarks);
          }
          resolve();
        });
        pose.send({ image: video });
      });

      if (frameLandmarks) {
        // Send to WS and wait for a result
        const resultPromise = new Promise(resolve => {
          if (resultQueue.length > 0) {
            resolve(resultQueue.shift());
          } else {
            pendingResults.push(resolve);
          }
        });

        sendFrame(frameLandmarks);
        // Wait at most 2s for a WS response
        const wsResult = await Promise.race([
          resultPromise,
          new Promise(resolve => setTimeout(() => resolve(null), 2000)),
        ]);

        frameStore.set(frameIdx, { landmarks: frameLandmarks, result: wsResult });
      }

      frameIdx++;
      setAnalyzeDone(frameIdx);
      setAnalyzeProgress(Math.round((frameIdx / totalFrames) * 100));
    }

    // Restore WS message handler
    ws.onmessage = originalOnMessage;

    if (!sendingRef.current) return;   // user stopped

    // ── PASS 2: Replay — play video normally, overlay stored results ──────────
    replayMapRef.current = frameStore;
    setMode('replaying');
    setAnalyzeProgress(100);

    video.currentTime = 0;
    await new Promise(resolve => {
      const h = () => { video.removeEventListener('seeked', h); resolve(); };
      video.addEventListener('seeked', h);
    });
    video.play();

    const replayLoop = () => {
      if (!sendingRef.current) return;
      const currentFrame = Math.round(video.currentTime * FPS);
      const stored = frameStore.get(currentFrame);
      if (stored) {
        if (stored.landmarks) drawSkeletonOnCanvas(stored.landmarks);
        if (stored.result) {
          setLiveResult(stored.result);
          if (stored.result.xgb) setXgbResult(stored.result.xgb);
        }
      }
      setFrameCount(currentFrame);
      setBufferFill(30);  // window always "full" in replay
      replayRafRef.current = requestAnimationFrame(replayLoop);
    };
    replayRafRef.current = requestAnimationFrame(replayLoop);

    // Stop replay when video ends
    video.onended = () => {
      cancelAnimationFrame(replayRafRef.current);
      sendingRef.current = false;
    };
  }, [drawSkeletonOnCanvas, sendFrame, wsStatus]);

  // ─── Start Camera ──────────────────────────────────────────────────────────────
  const startCamera = useCallback(async () => {
    setCameraError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setMode('camera');
      await initMediaPipe();

      // Set camera pose result handler
      poseRef.current.onResults((results) => {
        if (!results.poseLandmarks) return;
        const lms = Array.from(results.poseLandmarks);
        landmarksRef.current = lms;
        drawSkeletonOnCanvas(lms);
        sendFrame(lms);
      });

      openWS();
      sendingRef.current = true;
      pumpFrames();
    } catch (_) {
      setCameraError('Camera access denied or not available.');
    }
  }, [initMediaPipe, openWS, pumpFrames, drawSkeletonOnCanvas, sendFrame]);

  // ─── Start Video ───────────────────────────────────────────────────────────────
  const handleFileChange = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setMode('analyzing');
    setAnalyzeProgress(0);
    setLiveResult(null);
    setFrameCount(0);
    setBufferFill(0);

    const url = URL.createObjectURL(file);
    videoRef.current.src = url;
    await new Promise(r => {
      videoRef.current.onloadedmetadata = r;
      videoRef.current.load();
    });

    await initMediaPipe();
    openWS();
    sendingRef.current = true;

    // Wait briefly for WS to open
    await new Promise(r => setTimeout(r, 300));
    processVideoTwoPass();
  }, [initMediaPipe, openWS, processVideoTwoPass]);

  // ─── Stop ──────────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    sendingRef.current = false;
    if (rafRef.current)       cancelAnimationFrame(rafRef.current);
    if (replayRafRef.current) cancelAnimationFrame(replayRafRef.current);
    if (wsRef.current)        wsRef.current.close();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.onended = null;
      videoRef.current.srcObject = null;
      videoRef.current.src = '';
    }
    const canvas = canvasRef.current;
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    replayMapRef.current  = null;
    landmarksRef.current  = null;
    setMode('idle');
    setWsStatus('disconnected');
    setLiveResult(null);
    setFrameCount(0);
    setBufferFill(0);
    setAnalyzeProgress(0);
  }, []);

  const bufferPct = Math.round((bufferFill / 30) * 100);

  // ─── Status label helper ────────────────────────────────────────────────────
  const statusLabel = () => {
    if (wsStatus === 'warming')      return '⏳ AI Loading…';
    if (wsStatus === 'connecting')   return 'Connecting…';
    if (wsStatus === 'live')         return '🟢 Live';
    return 'Offline';
  };

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
        <div className={`${styles.statusBadge} ${styles[wsStatus] ?? styles.disconnected}`}>
          <div className={styles.statusDot} />
          {statusLabel()}
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

            {/* Analysis progress overlay (shown during pass 1) */}
            {mode === 'analyzing' && (
              <div style={{
                position: 'absolute', inset: 0, zIndex: 10,
                background: 'rgba(0,0,0,0.75)',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: '1rem', color: '#fff',
              }}>
                <div style={{ fontSize: '2rem' }}>🧠</div>
                <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>Analyzing video…</div>
                <div style={{ fontSize: '0.85rem', opacity: 0.7 }}>
                  Frame {analyzeDone} / {analyzeTotal}
                </div>
                <div style={{ width: '60%', height: 8, background: 'rgba(255,255,255,0.15)', borderRadius: 4 }}>
                  <div style={{
                    width: `${analyzeProgress}%`, height: '100%',
                    background: 'linear-gradient(90deg, #6c63ff, #00d2ff)',
                    borderRadius: 4, transition: 'width 0.2s',
                  }} />
                </div>
                <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                  Video will replay with results when done
                </div>
              </div>
            )}

            {/* Warming overlay */}
            {wsStatus === 'warming' && mode !== 'analyzing' && (
              <div style={{
                position: 'absolute', inset: 0, zIndex: 10,
                background: 'rgba(0,0,0,0.6)',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: '0.75rem', color: '#fff', borderRadius: 12,
              }}>
                <div style={{ fontSize: '2rem' }}>⏳</div>
                <div style={{ fontWeight: 600 }}>AI Model Loading…</div>
                <div style={{ fontSize: '0.8rem', opacity: 0.6 }}>This only happens once after server start</div>
              </div>
            )}

            <video
              ref={videoRef}
              id="kata-video"
              className={styles.videoFeed}
              muted
              playsInline
              style={{ display: mode !== 'idle' ? 'block' : 'none' }}
            />
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
              <p style={{ marginTop: '0.6rem' }}>
                <strong>📁 Video mode:</strong> Frames are analyzed offline first, then
                replayed with results in perfect sync — no lag.
              </p>
              <p style={{ marginTop: '0.4rem', color: '#666' }}>
                Supported moves: Gedan Barai · Gyaku Zuki · Mae Geri
              </p>
            </div>
          ) : (
            <>
              {/* Frame buffer progress */}
              <div className={styles.bufferSection}>
                <div className={styles.bufferLabel}>
                  <span>
                    {mode === 'analyzing' ? '🔍 Analyzing' : 'Frame Buffer'}
                  </span>
                  <span>
                    {mode === 'analyzing'
                      ? `${analyzeProgress}%`
                      : `${bufferFill} / 30`}
                  </span>
                </div>
                <div className={styles.bufferTrack}>
                  <div
                    className={styles.bufferFill}
                    style={{ width: mode === 'analyzing' ? `${analyzeProgress}%` : `${bufferPct}%` }}
                  />
                </div>
              </div>

              {/* Live result card */}
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
                  {wsStatus === 'warming'
                    ? '⏳ Loading AI…'
                    : liveResult
                      ? (MOVE_DISPLAY[liveResult.move] ?? liveResult.move)
                      : mode === 'analyzing' ? '— Analyzing… —' : '— Buffering —'}
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

              {/* XGBoost result card */}
              <div className={`${styles.modelCard} ${xgbResult ? styles.active : ''}`}>
                <div className={styles.modelHeader}>
                  <span className={styles.modelName}>🌲 XGBoost AI</span>
                  {xgbResult && (
                    <span className={`${styles.modelConf} ${styles[confClass(xgbResult.confidence)]}`}>
                      {(xgbResult.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className={`${styles.moveName} ${!xgbResult ? styles.buffering : ''}`}>
                  {wsStatus === 'warming'
                    ? '⏳ Loading AI…'
                    : xgbResult
                      ? (MOVE_DISPLAY[xgbResult.move] ?? xgbResult.move)
                      : mode === 'analyzing' ? '— Analyzing… —' : '— Buffering —'}
                </div>
                {xgbResult?.all_probs?.length > 0 && (
                  <div className={styles.probBars}>
                    {MOVE_NAMES.map((name, i) => {
                      const p   = xgbResult.all_probs[i] ?? 0;
                      const bar = confClass(p);
                      return (
                        <div key={`xgb-${name}`} className={styles.probRow}>
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
                {mode === 'replaying' ? 'Replaying: ' : 'Frames processed: '}{frameCount}
                {mode === 'replaying' && ' 🎬'}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
