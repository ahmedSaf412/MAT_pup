'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import PoseCanvas from '../components/PoseCanvas';
import CorrectionPanel from '../components/CorrectionPanel';
import MoveSkeletonPreview from '../components/MoveSkeletonPreview';
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

const TOTAL_FRAMES = 30;

// 🔥 Global singleton to prevent MediaPipe "File exists" crash in Next.js
let globalPoseInstance = null;

// ─── Component ────────────────────────────────────────────────────────────────
export default function TrainPage() {
  const { user } = useAuth();
  const router    = useRouter();
  const videoRef  = useRef(null);
  const fileInputRef = useRef(null);

  // ── Media state
  const [cameraActive,    setCameraActive]    = useState(false);
  const [isVideoUploaded, setIsVideoUploaded] = useState(false);
  const [cameraError,     setCameraError]     = useState('');

  // ── Session state
  const [isTraining,       setIsTraining]       = useState(false);
  const [isRecordingRep,   setIsRecordingRep]   = useState(false);
  const [repCount,         setRepCount]         = useState(0);
  const [framesRecorded,   setFramesRecorded]   = useState(0);
  const [selectedMove,     setSelectedMove]     = useState('free');
  const [timer,            setTimer]            = useState(0);
  const [score,            setScore]            = useState(0);

  // ── Pose & feedback state
  const [landmarks,         setLandmarks]         = useState(null);
  const [currentCorrection, setCurrentCorrection] = useState({ move: '', confidence: 0, corrections: [] });
  const [detectionHistory,  setDetectionHistory]  = useState([]);
  const [lastResult,        setLastResult]         = useState(null);   // {move, confidence, allProbs}

  // ── Refs (prevent stale closures in MediaPipe callbacks)
  const timerRef           = useRef(null);
  const frameBufferRef     = useRef([]);
  const mediaPipeRef       = useRef(null);
  const isRecordingRef     = useRef(false);
  const repCountRef        = useRef(0);
  const isMediaPlayingRef  = useRef(false);

  // Sync state → refs
  useEffect(() => { isRecordingRef.current = isRecordingRep; }, [isRecordingRep]);
  useEffect(() => { repCountRef.current    = repCount; },       [repCount]);

  // ── Initialize MediaPipe (crash-proof singleton) ──────────────────────────
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
          if (results.poseLandmarks) {
            const lmArray = Array.from(results.poseLandmarks);
            setLandmarks(lmArray);

            if (isRecordingRef.current && lmArray.length === 33) {
              const angles = extract14Angles(lmArray);
              frameBufferRef.current.push({ angles });

              // Update live frame counter
              setFramesRecorded(frameBufferRef.current.length);

              if (frameBufferRef.current.length === TOTAL_FRAMES) {
                // Stop recording
                setIsRecordingRep(false);
                isRecordingRef.current = false;
                setFramesRecorded(0);
                sendToClassifier([...frameBufferRef.current]);
                setRepCount(prev => prev + 1);
              }
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
      catch (err) { console.warn('MediaPipe dropped a frame:', err); }
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

      const devices = await navigator.mediaDevices.enumerateDevices();
      const droidCam = devices.find(d => d.kind === 'videoinput' && d.label.toLowerCase().includes('droidcam'));

      const stream = await navigator.mediaDevices.getUserMedia({
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
      const videoUrl = URL.createObjectURL(file);
      const video = videoRef.current;
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
    frameBufferRef.current  = [];
    timerRef.current = setInterval(() => setTimer(t => t + 1), 1000);
  }, []);

  const recordNextRep = () => {
    frameBufferRef.current = [];
    setFramesRecorded(0);
    setIsRecordingRep(true);
  };

  // ── Classifier call ───────────────────────────────────────────────────────
  const sendToClassifier = async (frames) => {
    try {
      const response = await api.post('/api/classify', {
        frames,
        feature_set: 'angles14',
        model: 'Bi-LSTM',
      });

      const { move, confidence, inference_time_ms, all_probabilities } = response.data;
      const CLASS_NAMES = ['Mae Geri', 'Gyaku Zuki', 'Gedan Barai'];

      setLastResult({ move, confidence, allProbs: all_probabilities, inferenceMs: inference_time_ms });
      setCurrentCorrection({
        move,
        confidence,
        corrections: [
          { joint: 'result',  message: `✅ ${move} detected`,                        severity: confidence > 0.85 ? 'info' : 'warning' },
          { joint: 'conf',    message: `Confidence: ${(confidence * 100).toFixed(1)}%`, severity: 'info' },
          { joint: 'speed',   message: `Inference: ${inference_time_ms.toFixed(1)} ms`, severity: 'info' },
        ],
      });

      setScore(s => s + Math.round(confidence * 100));
      setDetectionHistory(prev =>
        [{ move, confidence, timestamp: new Date().toLocaleTimeString() }, ...prev].slice(0, 10)
      );
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
    setIsRecordingRep(false);
    setFramesRecorded(0);
    if (timerRef.current) clearInterval(timerRef.current);
    frameBufferRef.current = [];
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
  const progressPct      = isRecordingRep ? Math.round((framesRecorded / TOTAL_FRAMES) * 100) : 0;
  const CLASS_NAMES      = ['Mae Geri', 'Gyaku Zuki', 'Gedan Barai'];

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.trainPage}>
      <div className={styles.trainLayout}>

        {/* ── Video section ── */}
        <div className={styles.videoSection}>
          <div className={styles.videoHeader}>
            <h1 className={styles.videoTitle}>🎯 AI Training Mode</h1>
            {isTraining && (
              <div className={styles.sessionInfo}>
                <span className={styles.timerBadge}>
                  ⏱️ {Math.floor(timer / 60)}:{(timer % 60).toString().padStart(2, '0')}
                </span>
                <span className={styles.scoreBadge}>⭐ {score} pts</span>
                {isRecordingRep && (
                  <span className={styles.bufferBadge}>🔴 {framesRecorded}/{TOTAL_FRAMES}</span>
                )}
              </div>
            )}
          </div>

          {/* Move reference card — shown when a specific move is selected */}
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

            {/* Recording progress overlay */}
            {isRecordingRep && (
              <div className={styles.recordingOverlay}>
                <div className={styles.recordingPulse} />
                <span className={styles.recordingLabel}>Recording…</span>
                <div className={styles.progressBarWrap}>
                  <div className={styles.progressBar} style={{ width: `${progressPct}%` }} />
                </div>
                <span className={styles.progressText}>{framesRecorded} / {TOTAL_FRAMES} frames</span>
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
              {/* Media controls */}
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

              {/* Session controls */}
              {(cameraActive || isVideoUploaded) && !isTraining && (
                <button className="btn btn-secondary" onClick={startTraining}>▶ Start Session</button>
              )}

              {isTraining && (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={recordNextRep}
                    disabled={isRecordingRep}
                  >
                    {isRecordingRep
                      ? `🔴 Recording… (${progressPct}%)`
                      : `🥋 Record Rep ${repCount + 1}`}
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
        </div>{/* end videoSection */}

        {/* ── Right panel: Preview + Results ── */}
        <div className={styles.panelSection}>
          {/* Skeleton preview — always visible */}
          <div className={styles.skeletonPreviewWrap}>
            <MoveSkeletonPreview
              move={selectedMove !== 'free' ? selectedMoveData : null}
              defaultTab="skeleton"
            />
          </div>

          {/* Last result confidence gauge */}
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

          {/* Correction feedback */}
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
        </div>
      </div>
    </div>
  );
}