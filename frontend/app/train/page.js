'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '../context/AuthContext';
import { usePose } from '../context/PoseContext';
import PoseCanvas from '../components/PoseCanvas';
import CorrectionPanel from '../components/CorrectionPanel';
import MoveSkeletonPreview from '../components/MoveSkeletonPreview';
import RepResultPanel from '../components/RepResultPanel';
import api from '../services/api';
import { extract14Angles } from '../utils/angleCalculator';
import styles from './train.module.css';

// ─── Constants ────────────────────────────────────────────────────────────────
const AVAILABLE_MOVES = [
  { id: 'free',        name: 'Free Practice (Auto Detect)', emoji: '🔍', description: 'AI will identify any of the 3 moves automatically.' },
  { id: 'mae_geri',   name: 'Front Kick (Mae Geri)',        emoji: '🦵', description: 'Snap the knee up, extend the leg forward, retract quickly. Keep hips square.' },
  { id: 'gyaku_zuki', name: 'Reverse Punch (Gyaku Zuki)',   emoji: '👊', description: 'Rotate the hip, drive the rear hand straight, pull the lead hand back.' },
  { id: 'gedan_barai', name: 'Down Block (Gedan Barai)',    emoji: '🛡️', description: 'Sweep the blocking arm diagonally downward, chamber the other hand at the hip.' },
];

const CLASS_NAMES   = ['Mae Geri', 'Gyaku Zuki', 'Gedan Barai'];
const WINDOW_SIZE         = 30;   // frames the Bi-LSTM expects
const POST_TRIGGER_FRAMES  = 45;   // frames to collect AFTER motion spike
const ROLLING_SIZE         = 150;  // circular buffer size (5 s @ ~30 fps)

// Motion energy auto-trigger settings
// Energy = sum(|angle[k] - prev_angle[k]|) across 14 joints per frame.
// angles are NORMALIZED (0–1, i.e. divided by 180°), so max possible = 14.0
// At rest the sum is ~0.01–0.05; a karate move spikes to ~0.3–0.8.
// ⚠️  BUG-FIX NOTE: the old value was 1.5 which was never reachable on 0-1 scale.
const ENERGY_THRESHOLD     = 0.35; // a noticeable movement (~60° across a few joints)
const SPIKE_CONFIRM_FRAMES = 2;    // consecutive high-energy frames to confirm motion

// 🔥 Global singleton — prevents MediaPipe "File exists" crash in Next.js dev
let globalPoseInstance = null;

// ─── Motion-peak window selector ─────────────────────────────────────────────
// Returns { angleWindow, landmarkWindow } — the 30 frames with the highest
// total joint-angle movement from the combined pre+post buffer.
// angleWindow   → sent to Bi-LSTM classifier (normalized 0-1)
// landmarkWindow → sent to DTW / RAG (raw xyz per frame)
function findBestWindow(frames, windowSize = WINDOW_SIZE) {
  if (frames.length <= windowSize) {
    return {
      angleWindow:    frames.map(f => ({ angles: f.angles })),
      landmarkWindow: frames.map(f => f.landmarks),
    };
  }

  let bestStart  = 0;
  let bestEnergy = -1;

  for (let i = 0; i <= frames.length - windowSize; i++) {
    let energy = 0;
    for (let j = i + 1; j < i + windowSize; j++) {
      const a = frames[j - 1].angles;
      const b = frames[j].angles;
      for (let k = 0; k < a.length; k++) {
        energy += Math.abs(b[k] - a[k]);
      }
    }
    if (energy > bestEnergy) {
      bestEnergy = energy;
      bestStart  = i;
    }
  }

  const slice = frames.slice(bestStart, bestStart + windowSize);
  return {
    angleWindow:    slice.map(f => ({ angles: f.angles })),
    landmarkWindow: slice.map(f => f.landmarks),
  };
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function TrainPage() {
  const { user }                          = useAuth();
  const { setCurrentMoveId, setCurrentLandmarks, setCurrentLandmarkFrames, currentLandmarkFrames } = usePose();
  const router                            = useRouter();
  const videoRef                          = useRef(null);
  const fileInputRef                      = useRef(null);

  // ── Media state
  const [cameraActive,    setCameraActive]    = useState(false);
  const [isVideoUploaded, setIsVideoUploaded] = useState(false);
  const [cameraError,     setCameraError]     = useState('');

  // ── Session state
  const [isTraining,     setIsTraining]     = useState(false);
  const [isArmed,        setIsArmed]        = useState(false);   // waiting for motion spike
  const [isRecordingRep, setIsRecordingRep] = useState(false);  // motion detected, capturing
  const [countdown,      setCountdown]      = useState(null);   // 3-2-1 before arming
  const [repCount,       setRepCount]       = useState(0);
  const [framesRecorded, setFramesRecorded] = useState(0);
  const [selectedMove,   setSelectedMove]   = useState('free');
  const [timer,          setTimer]          = useState(0);
  const [score,          setScore]          = useState(0);

  // ── Pose & feedback state
  const [landmarks,         setLandmarks]         = useState(null);
  const [refSkeletonFrames, setRefSkeletonFrames] = useState(null);
  const [significantErrors, setSignificantErrors] = useState([]);
  const [currentCorrection, setCurrentCorrection] = useState({ move: '', confidence: 0, corrections: [] });
  const [detectionHistory,  setDetectionHistory]  = useState([]);
  const [lastResult,        setLastResult]         = useState(null);
  const [ragFeedback,       setRagFeedback]        = useState('');   // AI coach text
  const [activeSessionId,   setActiveSessionId]    = useState(null);

  // ── Refs (prevent stale closures inside MediaPipe callbacks)
  const timerRef            = useRef(null);
  const activeSessionIdRef  = useRef(null);
  const armTimeoutRef       = useRef(null);   // auto-disarm after 10 s
  const countdownRef        = useRef(null);   // interval for 3-2-1 countdown
  const mediaPipeRef        = useRef(null);
  const isArmedRef          = useRef(false);  // armed, watching for motion
  const isRecordingRef      = useRef(false);  // motion triggered, capturing
  const repCountRef         = useRef(0);
  const isMediaPlayingRef   = useRef(false);
  const selectedMoveRef     = useRef('free');

  // Rolling circular buffer — always fills regardless of state
  // Each entry: { angles (0-1 ×14), landmarks ({x,y,z,vis}×33) }
  const rollingBufferRef    = useRef([]);   // max ROLLING_SIZE frames
  const postTriggerFrames   = useRef([]);   // frames collected AFTER motion spike
  const postCountRef        = useRef(0);
  const prevAnglesRef       = useRef(null); // previous frame — for energy calc
  const consecutiveSpikeRef = useRef(0);   // consecutive high-energy frame count

  // Sync state → refs
  useEffect(() => { isArmedRef.current    = isArmed; },       [isArmed]);
  useEffect(() => { repCountRef.current   = repCount; },      [repCount]);
  useEffect(() => { selectedMoveRef.current = selectedMove; },[selectedMove]);

  // ── Create Training Session on Mount ──────────────────────────────────────
  useEffect(() => {
    let sessionId = null;
    api.post('/api/sessions/start', { session_type: 'live' })
      .then(res => {
        setActiveSessionId(res.data.id);
        activeSessionIdRef.current = res.data.id;
        sessionId = res.data.id;
      })
      .catch(err => console.error("Could not start session:", err));
      
    return () => {
      if (sessionId) {
        api.post(`/api/sessions/${sessionId}/end`).catch(() => {});
      }
    };
  }, []);

  // ── Initialize MediaPipe singleton ────────────────────────────────────────
  useEffect(() => {
    const initMediaPipe = async () => {
      try {
        if (!globalPoseInstance) {
          const { Pose } = await import('@mediapipe/pose');
          globalPoseInstance = new Pose({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
          });
          globalPoseInstance.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            enableSegmentation: false,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
          });
        }

        globalPoseInstance.onResults((results) => {
          if (!results.poseLandmarks) return;
          const lmArray = Array.from(results.poseLandmarks);
          setLandmarks(lmArray);

          if (lmArray.length !== 33) return;
          const angles = extract14Angles(lmArray);

          // Build entry (stored in both circular buffer and post-trigger buffer)
          const entry = {
            angles,
            landmarks: lmArray.map(lm => ({
              x: lm.x, y: lm.y, z: lm.z ?? 0, visibility: lm.visibility ?? 1.0,
            })),
          };

          // ── Always update 5-second circular buffer ────────────────────────
          rollingBufferRef.current.push(entry);
          if (rollingBufferRef.current.length > ROLLING_SIZE) {
            rollingBufferRef.current.shift();
          }

          // ── Compute frame-to-frame motion energy ──────────────────────────
          let energy = 0;
          if (prevAnglesRef.current) {
            for (let k = 0; k < angles.length; k++) {
              energy += Math.abs(angles[k] - prevAnglesRef.current[k]);
            }
          }
          prevAnglesRef.current = angles;

          // ── ARMED: watching for motion spike ──────────────────────────────
          if (isArmedRef.current && !isRecordingRef.current) {
            // DEBUG: open browser DevTools console to see live energy values
            // Remove this log once threshold is confirmed working
            console.log(`[AutoTrigger] energy=${energy.toFixed(3)} threshold=${ENERGY_THRESHOLD} spike=${consecutiveSpikeRef.current}`);

            if (energy >= ENERGY_THRESHOLD) {
              consecutiveSpikeRef.current++;
            } else {
              consecutiveSpikeRef.current = 0;
            }

            // Enough consecutive high-energy frames → motion confirmed, start capture
            if (consecutiveSpikeRef.current >= SPIKE_CONFIRM_FRAMES) {
              isArmedRef.current   = false;
              isRecordingRef.current = true;
              setIsArmed(false);
              setIsRecordingRep(true);
              postTriggerFrames.current = [];
              postCountRef.current      = 0;
              consecutiveSpikeRef.current = 0;
              // Clear auto-disarm timeout
              if (armTimeoutRef.current) clearTimeout(armTimeoutRef.current);
            }
          }

          // ── RECORDING: collect POST_TRIGGER_FRAMES after spike ────────────
          if (isRecordingRef.current) {
            postTriggerFrames.current.push(entry);
            postCountRef.current++;
            setFramesRecorded(postCountRef.current);

            if (postCountRef.current >= POST_TRIGGER_FRAMES) {
              isRecordingRef.current = false;
              setIsRecordingRep(false);
              setFramesRecorded(0);

              // Use rolling buffer (history before spike) + post-trigger frames
              // findBestWindow selects the peak 30-frame window from all of it
              const allFrames = [
                ...rollingBufferRef.current,
                ...postTriggerFrames.current,
              ];
              const { angleWindow, landmarkWindow } = findBestWindow(allFrames, WINDOW_SIZE);
              setRepCount(prev => prev + 1);
              sendToClassifier(angleWindow, landmarkWindow, selectedMoveRef.current);
            }
          }
        });

        mediaPipeRef.current = globalPoseInstance;
      } catch (error) {
        console.error('MediaPipe init error:', error);
        setCameraError('Failed to load AI pose detection. Try refreshing.');
      }
    };

    initMediaPipe();
  }, []);

  // ── Frame processing loop ─────────────────────────────────────────────────
  const processFrame = async () => {
    if (!isMediaPlayingRef.current) return;
    const video = videoRef.current;
    if (video && video.readyState >= 2 && mediaPipeRef.current && !video.paused) {
      try { await mediaPipeRef.current.send({ image: video }); }
      catch (err) { console.warn('MediaPipe dropped frame:', err); }
    }
    requestAnimationFrame(processFrame);
  };

  // ── Start live camera ─────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      setCameraError('');
      setIsVideoUploaded(false);
      const video = videoRef.current;
      if (!video) return;

      const devices   = await navigator.mediaDevices.enumerateDevices();
      const droidCam  = devices.find(d => d.kind === 'videoinput' && d.label.toLowerCase().includes('droidcam'));
      const stream    = await navigator.mediaDevices.getUserMedia({
        video: {
          width: 640, height: 480, facingMode: 'user',
          deviceId: droidCam?.deviceId ? { exact: droidCam.deviceId } : undefined,
        },
        audio: false,
      });

      video.srcObject = stream;
      await video.play();
      setCameraActive(true);
      isMediaPlayingRef.current = true;
      requestAnimationFrame(processFrame);
    } catch (err) {
      console.error('Camera error:', err);
      setCameraError('Could not access camera. Please allow camera permissions.');
    }
  };

  // ── Handle video upload ───────────────────────────────────────────────────
  const handleVideoUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      stopCamera();
      const videoUrl  = URL.createObjectURL(file);
      const video     = videoRef.current;
      video.srcObject = null;
      video.src       = videoUrl;
      video.loop      = true;
      await video.play();
      setCameraActive(false);
      setIsVideoUploaded(true);
      setCameraError('');
      isMediaPlayingRef.current = true;
      requestAnimationFrame(processFrame);
    } catch (err) {
      console.error('Video upload error:', err);
      setCameraError('Failed to load video.');
    }
  };

  // ── Session management ────────────────────────────────────────────────────
  const startTraining = useCallback(() => {
    setIsTraining(true);
    setTimer(0);
    setScore(0);
    setRepCount(0);
    setFramesRecorded(0);
    setDetectionHistory([]);
    setLastResult(null);
    setRagFeedback('');
    rollingBufferRef.current = [];
    timerRef.current = setInterval(() => setTimer(t => t + 1), 1000);
  }, []);

  // ── Arm next rep — 3-second countdown, then auto-trigger on motion spike ─
  const armNextRep = () => {
    // Clear any existing countdown interval
    if (countdownRef.current) clearInterval(countdownRef.current);

    let counter = 3;
    setCountdown(counter);

    countdownRef.current = setInterval(() => {
      counter--;
      if (counter > 0) {
        setCountdown(counter);
      } else {
        // Countdown finished — actually arm the detector
        clearInterval(countdownRef.current);
        countdownRef.current = null;
        setCountdown(null);

        consecutiveSpikeRef.current = 0;
        postTriggerFrames.current   = [];
        postCountRef.current        = 0;
        prevAnglesRef.current       = null;
        isArmedRef.current          = true;
        setIsArmed(true);
        setIsRecordingRep(false);
        setFramesRecorded(0);

        // Auto-disarm after 10 seconds if no movement detected
        if (armTimeoutRef.current) clearTimeout(armTimeoutRef.current);
        armTimeoutRef.current = setTimeout(() => {
          if (isArmedRef.current) {
            isArmedRef.current = false;
            setIsArmed(false);
            console.warn('Auto-disarmed: no motion detected within 10 s');
          }
        }, 10_000);
      }
    }, 1000);
  };

  // ── Classifier + RAG pipeline ─────────────────────────────────────────────
  const sendToClassifier = async (frames, landmarkFrames, intendedMove) => {
    try {
      // Map both angles and full landmarks into the frame objects
      const payloadFrames = frames.map((f, i) => ({
        angles: f.angles,
        landmarks: landmarkFrames[i]
      }));

      const response = await api.post('/api/classify', {
        frames: payloadFrames,
        feature_set: 'landmarks',
        model: 'Bi-LSTM',
        session_id: activeSessionIdRef.current,
        input_mode: 'camera',
        frame_timestamp: Date.now() / 1000
      });

      const { move, confidence, inference_time_ms, all_probabilities, move_id, detection_id } = response.data;

      setLastResult({ move, confidence, allProbs: all_probabilities, inferenceMs: inference_time_ms });

      // Evaluate on INTENDED move if user selected one, not the classifier guess
      const finalMoveId = intendedMove !== 'free' ? intendedMove : move_id;

      // Update PoseContext for ChatBot awareness
      setCurrentMoveId(finalMoveId);
      setCurrentLandmarks(landmarkFrames?.[0] ?? null);         // single frame (legacy)
      setCurrentLandmarkFrames(landmarkFrames ?? null);         // all 30 frames for DTW

      setCurrentCorrection({
        move,
        confidence,
        corrections: [
          { joint: 'result', message: `✅ ${move} detected`,                          severity: confidence > 0.85 ? 'info' : 'warning' },
          { joint: 'conf',   message: `Confidence: ${(confidence * 100).toFixed(1)}%`, severity: 'info' },
          { joint: 'speed',  message: `Inference: ${inference_time_ms.toFixed(1)} ms`, severity: 'info' },
        ],
      });

      setScore(s => s + Math.round(confidence * 100));
      setDetectionHistory(prev =>
        [{ move, confidence, timestamp: new Date().toLocaleTimeString() }, ...prev].slice(0, 10)
      );

      // ── Non-blocking DTW RAG coaching feedback ──────────────────────────
      if (finalMoveId !== 'free' && landmarkFrames?.length >= 5) {
        setRagFeedback('🤔 Comparing your form to the master via DTW…');
        setRefSkeletonFrames(null);
        setSignificantErrors([]);

        api.get(`/api/video/${finalMoveId}/landmarks?view=front`)
          .then(skRes => {
            if (skRes.data?.frames) {
              setRefSkeletonFrames(skRes.data.frames);
            }
          })
          .catch(err => console.warn('Failed to load ref skeleton:', err));

        api.post('/api/rag/feedback', {
          move_id: finalMoveId,
          frames:  landmarkFrames,   // full sequence: [frames][33 landmarks]
          detection_id: detection_id, // link feedback to DB row
        })
          .then(ragResult => {
            const fb = ragResult.data?.feedback;
            const errs = ragResult.data?.errors || [];
            if (fb) {
              setRagFeedback(fb);
              setSignificantErrors(errs);
            }
          })
          .catch(err => {
            console.warn('RAG feedback failed:', err.message);
            setRagFeedback('');
          });
      }
    } catch (error) {
      console.error('Classification error:', error);
      setCurrentCorrection({
        move: 'Error',
        confidence: 0,
        corrections: [{ joint: 'system', message: `Backend error: ${error.message}`, severity: 'error' }],
      });
    }
  };

  const stopTraining = useCallback(() => {
    setIsTraining(false);
    setIsArmed(false);
    setIsRecordingRep(false);
    isArmedRef.current     = false;
    isRecordingRef.current = false;
    setFramesRecorded(0);
    if (timerRef.current)   clearInterval(timerRef.current);
    if (armTimeoutRef.current) clearTimeout(armTimeoutRef.current);
  }, []);

  const stopCamera = useCallback(() => {
    isMediaPlayingRef.current = false;
    if (videoRef.current) {
      if (videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
      videoRef.current.srcObject = null;
      videoRef.current.src       = '';
    }
    setCameraActive(false);
    setIsVideoUploaded(false);
    stopTraining();
  }, [stopTraining]);

  // ── Cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopCamera();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [stopCamera]);

  if (!user) return null;

  // ── Derived values ────────────────────────────────────────────────────────
  const selectedMoveData = AVAILABLE_MOVES.find(m => m.id === selectedMove);
  const progressPct      = isRecordingRep
    ? Math.round((framesRecorded / POST_TRIGGER_FRAMES) * 100)
    : 0;

  // ─── JSX ─────────────────────────────────────────────────────────────────
  return (
    <div className={styles.trainPage}>
      <div className={styles.trainLayout}>

        {/* ── Left: camera section (sticky, never pushed down) ── */}
        <div className={styles.videoSection}>
          <div className={styles.videoHeader}>
            <h1 className={styles.videoTitle}>🎯 AI Training Mode</h1>
            {isTraining && (
              <div className={styles.sessionInfo}>
                <span className={styles.timerBadge}>
                  ⏱️ {Math.floor(timer / 60)}:{(timer % 60).toString().padStart(2, '0')}
                </span>
                <span className={styles.scoreBadge}>⭐ {score} pts</span>
                {isArmed && !isRecordingRep && (
                  <span className={styles.bufferBadge} style={{ background: 'rgba(255,200,0,0.2)', color: '#ffc800' }}>
                    🟡 Armed
                  </span>
                )}
                {isRecordingRep && (
                  <span className={styles.bufferBadge}>🔴 {framesRecorded}/{POST_TRIGGER_FRAMES}</span>
                )}
              </div>
            )}
          </div>

          {/* Move reference card */}
          {selectedMove !== 'free' && selectedMoveData && (
            <div className={styles.moveReferenceCard}>
              <span className={styles.moveReferenceEmoji}>{selectedMoveData.emoji}</span>
              <div>
                <div className={styles.moveReferenceName}>{selectedMoveData.name}</div>
                <div className={styles.moveReferenceDesc}>{selectedMoveData.description}</div>
              </div>
            </div>
          )}

          {/* Video container */}
          <div className={styles.videoContainer}>
            <video
              ref={videoRef}
              className={styles.video}
              playsInline
              muted={!isVideoUploaded}
              controls={isVideoUploaded}
            />
            {(cameraActive || isVideoUploaded) && landmarks && (
              <PoseCanvas
                landmarks={landmarks}
                corrections={currentCorrection.corrections}
                width={640}
                height={480}
              />
            )}

            {/* Countdown overlay — 3-2-1 before arming */}
            {countdown !== null && (
              <div className={styles.recordingOverlay} style={{ background: 'rgba(0,212,255,0.12)', borderColor: 'rgba(0,212,255,0.4)' }}>
                <span style={{ fontSize: '3.5rem', fontWeight: 900, color: '#00d4ff', lineHeight: 1 }}>
                  {countdown}
                </span>
                <span className={styles.recordingLabel} style={{ color: '#00d4ff', marginTop: 6 }}>Get into position!</span>
                <span style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: 4 }}>
                  Auto-trigger will arm when countdown ends
                </span>
              </div>
            )}

            {/* Armed overlay — waiting for motion spike */}
            {isArmed && !isRecordingRep && (
              <div className={styles.recordingOverlay} style={{ background: 'rgba(255,200,0,0.15)', borderColor: 'rgba(255,200,0,0.4)' }}>
                <div className={styles.recordingPulse} style={{ background: '#ffc800' }} />
                <span className={styles.recordingLabel} style={{ color: '#ffc800' }}>🟡 Armed — just do the move!</span>
                <span style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: 4 }}>
                  Watching for movement… auto-detects when you start
                </span>
                <span style={{ fontSize: '0.65rem', opacity: 0.5 }}>
                  Will auto-cancel in 10 s if nothing detected
                </span>
              </div>
            )}

            {/* Recording overlay — motion detected, capturing */}
            {isRecordingRep && (
              <div className={styles.recordingOverlay}>
                <div className={styles.recordingPulse} />
                <span className={styles.recordingLabel}>🔴 Motion detected — capturing…</span>
                <div className={styles.progressBarWrap}>
                  <div className={styles.progressBar} style={{ width: `${progressPct}%` }} />
                </div>
                <span className={styles.progressText}>{framesRecorded} / {POST_TRIGGER_FRAMES} frames</span>
                <span style={{ fontSize: '0.65rem', opacity: 0.6, marginTop: 2 }}>
                  Best 30-frame window auto-selected from {ROLLING_SIZE}-frame history
                </span>
              </div>
            )}

            {!cameraActive && !isVideoUploaded && (
              <div className={styles.videoPlaceholder}>
                <div className={styles.placeholderIcon}>📹</div>
                <p>Start Camera or Upload a Video to begin</p>
                {cameraError && <p className={styles.cameraError}>{cameraError}</p>}
              </div>
            )}
          </div>

          {/* Controls */}
          <div className={styles.controls}>
            <div className={styles.moveSelector}>
              <span className={styles.moveLabel}>Move:</span>
              <select
                className={styles.moveSelect}
                value={selectedMove}
                onChange={(e) => setSelectedMove(e.target.value)}
              >
                {AVAILABLE_MOVES.map((m) => (
                  <option key={m.id} value={m.id}>{m.emoji} {m.name}</option>
                ))}
              </select>
            </div>

            <div className={styles.controlButtons}>
              {!cameraActive && !isVideoUploaded ? (
                <>
                  <button className="btn btn-primary" onClick={startCamera}>📹 Start Camera</button>
                  <input
                    type="file"
                    accept="video/mp4,video/webm,video/ogg"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleVideoUpload}
                  />
                  <button className="btn btn-secondary" onClick={() => fileInputRef.current.click()}>
                    📁 Upload Video
                  </button>
                </>
              ) : (
                <button className="btn btn-ghost" onClick={stopCamera}>⏹ Stop Media</button>
              )}

              {(cameraActive || isVideoUploaded) && !isTraining && (
                <button className="btn btn-secondary" onClick={startTraining}>▶ Start Session</button>
              )}

              {isTraining && (
                <>
                  <button
                    className={`btn ${isArmed ? 'btn-ghost' : 'btn-primary'}`}
                    onClick={armNextRep}
                    disabled={countdown !== null || isArmed || isRecordingRep}
                    style={isArmed ? { borderColor: '#ffc800', color: '#ffc800' } :
                           countdown !== null ? { borderColor: '#00d4ff', color: '#00d4ff' } : {}}
                  >
                    {countdown !== null
                      ? `⏳ Get Ready (${countdown})…`
                      : isRecordingRep
                        ? `🔴 Capturing… (${progressPct}%)`
                        : isArmed
                          ? '🟡 Armed — waiting for motion'
                          : `🥋 Arm Rep ${repCount + 1}`}
                  </button>
                  <button
                    className="btn btn-ghost"
                    onClick={stopTraining}
                    style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)' }}
                  >
                    ⏹ End Session
                  </button>
                </>
              )}
            </div>
          </div>

          {/* AI Sensei Analysis - Moved to bottom of left column */}
          {lastResult && (
            <div style={{ marginTop: '24px' }}>
              <RepResultPanel
                moveId={lastResult.move}
                moveName={lastResult.move}
                confidence={lastResult.confidence}
                inferenceMs={lastResult.inferenceMs}
                traineeFrames={currentLandmarkFrames}
                refFrames={refSkeletonFrames}
                aiFeedback={ragFeedback !== '🤔 Comparing your form to the master via DTW…' ? ragFeedback : null}
                errors={significantErrors}
              />
            </div>
          )}
        </div>{/* end videoSection */}

        {/* ── Right panel: Preview + Results (scrolls independently) ── */}
        <div className={styles.panelSection}>

          {/* Skeleton preview */}
          <div className={styles.skeletonPreviewWrap}>
            <MoveSkeletonPreview
              move={selectedMove !== 'free' ? selectedMoveData : null}
              defaultTab="skeleton"
            />
          </div>

          {/* Classification result gauge */}
          {lastResult && (
            <div className={styles.resultGauge}>
              <div className={styles.gaugeHeader}>
                <span className={styles.gaugeMove}>{lastResult.move}</span>
                <span className={styles.gaugeConf}>{(lastResult.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className={styles.gaugeBarWrap}>
                <div
                  className={styles.gaugeBar}
                  style={{
                    width: `${lastResult.confidence * 100}%`,
                    background: lastResult.confidence > 0.85
                      ? 'var(--accent-green)'
                      : lastResult.confidence > 0.6
                        ? 'var(--accent-yellow)'
                        : 'var(--accent-red)',
                  }}
                />
              </div>
              <div className={styles.probBars}>
                {CLASS_NAMES.map((name, i) => (
                  <div key={name} className={styles.probItem}>
                    <span className={styles.probLabel}>{name.split(' ')[0]}</span>
                    <div className={styles.probBarWrap}>
                      <div
                        className={styles.probBar}
                        style={{
                          width: `${(lastResult.allProbs[i] || 0) * 100}%`,
                          opacity: lastResult.move === name ? 1 : 0.4,
                        }}
                      />
                    </div>
                    <span className={styles.probVal}>
                      {((lastResult.allProbs[i] || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
              <div className={styles.inferenceTime}>⚡ {lastResult.inferenceMs?.toFixed(1)} ms inference</div>
            </div>
          )}

          {/* CorrectionPanel */}
          {isTraining && (
            <CorrectionPanel
              moveName={currentCorrection.move}
              confidence={currentCorrection.confidence}
              corrections={currentCorrection.corrections}
              isCoach={false}
            />
          )}

          {/* Detection history */}
          {detectionHistory.length > 0 && (
            <div className={styles.detectionHistory}>
              <h3>📊 Recent Detections</h3>
              <div className={styles.historyList}>
                {detectionHistory.map((det, idx) => (
                  <div key={idx} className={styles.historyItem}>
                    <span className={styles.historyMove}>{det.move}</span>
                    <span className={styles.historyConfidence}>{(det.confidence * 100).toFixed(1)}%</span>
                    <span className={styles.historyTime}>{det.timestamp}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pre-session hint */}
          {!isTraining && !lastResult && (
            <div className={styles.preSesionHint}>
              {selectedMove === 'free'
                ? '🔍 Select a specific move to see its skeleton preview'
                : '▶ Start a session when you\'re ready — the AI will classify your rep'}
            </div>
          )}

          {/* Full Kata Mode entry */}
          <Link
            href="/kata"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              background: 'linear-gradient(135deg, rgba(91,33,182,0.2), rgba(124,58,237,0.1))',
              border: '1px solid rgba(124,58,237,0.35)',
              borderRadius: '10px',
              color: '#c4b5fd',
              fontWeight: 600,
              fontSize: '0.85rem',
              textDecoration: 'none',
              transition: 'all 0.2s',
            }}
          >
            🥋 Full Kata Practice Mode →
          </Link>
        </div>
      </div>
    </div>
  );
}
