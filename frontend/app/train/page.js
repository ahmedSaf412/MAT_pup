'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import PoseCanvas from '../components/PoseCanvas';
import CorrectionPanel from '../components/CorrectionPanel';
import styles from './train.module.css';

const AVAILABLE_MOVES = [
  { id: 'free', name: 'Free Practice (Auto Detect)' },
  { id: 'front_kick', name: 'Front Kick (Mae Geri)' },
  { id: 'roundhouse_kick', name: 'Roundhouse Kick (Mawashi Geri)' },
  { id: 'side_kick', name: 'Side Kick (Yoko Geri)' },
  { id: 'reverse_punch', name: 'Reverse Punch (Gyaku Zuki)' },
  { id: 'rising_block', name: 'Rising Block (Age Uke)' },
  { id: 'front_stance', name: 'Front Stance (Zenkutsu Dachi)' },
];

// Mock correction data that cycles for demo
const MOCK_CORRECTIONS_LIST = [
  {
    move: 'Front Kick',
    confidence: 0.92,
    corrections: [
      { joint: 'left_knee', message: 'Raise your left knee higher — aim for waist height', severity: 'warning' },
      { joint: 'right_hand', message: 'Keep your guard hand near your chin', severity: 'info' },
    ],
  },
  {
    move: 'Front Kick',
    confidence: 0.88,
    corrections: [
      { joint: 'left_knee', message: 'Good knee height! Keep it consistent', severity: 'info' },
    ],
  },
  {
    move: 'Roundhouse Kick',
    confidence: 0.85,
    corrections: [
      { joint: 'right_hip', message: 'Rotate your hips more through the kick', severity: 'warning' },
      { joint: 'left_ankle', message: 'Pivot your support foot — heel toward target', severity: 'error' },
      { joint: 'right_hand', message: 'Keep guard up during the kick', severity: 'warning' },
    ],
  },
  {
    move: 'Roundhouse Kick',
    confidence: 0.91,
    corrections: [
      { joint: 'right_hip', message: 'Better hip rotation! Almost perfect', severity: 'info' },
    ],
  },
];

export default function TrainPage() {
  const { user, isAuthenticated, isCoach } = useAuth();
  const router = useRouter();
  const videoRef = useRef(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [selectedMove, setSelectedMove] = useState('free');
  const [landmarks, setLandmarks] = useState(null);
  const [currentCorrection, setCurrentCorrection] = useState({
    move: '', confidence: 0, corrections: [],
  });
  const [timer, setTimer] = useState(0);
  const [score, setScore] = useState(0);
  const timerRef = useRef(null);
  const correctionIndexRef = useRef(0);
  const [cameraError, setCameraError] = useState('');

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
    if (isCoach) router.push('/coach');
  }, [isAuthenticated, isCoach, router]);

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      setCameraError('');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
      }
    } catch (err) {
      console.error('Camera error:', err);
      setCameraError('Could not access camera. Please allow camera permissions.');
    }
  }, []);

  // Stop camera
  const stopCamera = useCallback(() => {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  // Start training session
  const startTraining = useCallback(() => {
    setIsTraining(true);
    setTimer(0);
    setScore(0);
    correctionIndexRef.current = 0;

    // Timer
    timerRef.current = setInterval(() => {
      setTimer((t) => t + 1);
    }, 1000);

    // Simulate AI corrections every 3 seconds (demo)
    const correctionInterval = setInterval(() => {
      const idx = correctionIndexRef.current % MOCK_CORRECTIONS_LIST.length;
      setCurrentCorrection(MOCK_CORRECTIONS_LIST[idx]);
      setScore((s) => Math.min(100, s + Math.round(Math.random() * 5 + 2)));

      // Generate mock landmarks for skeleton display
      const mockLandmarks = Array.from({ length: 33 }, (_, i) => ({
        x: 0.3 + Math.random() * 0.4,
        y: 0.1 + (i / 33) * 0.8 + Math.random() * 0.05,
        z: Math.random() * 0.2 - 0.1,
        visibility: 0.8 + Math.random() * 0.2,
      }));
      setLandmarks(mockLandmarks);

      correctionIndexRef.current++;
    }, 3000);

    return () => clearInterval(correctionInterval);
  }, []);

  // Stop training session
  const stopTraining = useCallback(() => {
    setIsTraining(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  useEffect(() => {
    return () => {
      stopCamera();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [stopCamera]);

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  if (!user) return <div className="loading-container"><div className="spinner" /></div>;

  return (
    <div className={styles.trainPage}>
      <div className={styles.trainLayout}>
        {/* Left: Video + Canvas */}
        <div className={styles.videoSection}>
          <div className={styles.videoHeader}>
            <h1 className={styles.videoTitle}>🎯 Training Mode</h1>
            {isTraining && (
              <div className={styles.sessionInfo}>
                <span className={styles.timerBadge}>⏱️ {formatTime(timer)}</span>
                <span className={styles.scoreBadge}>⭐ {score}pts</span>
              </div>
            )}
          </div>

          <div className={styles.videoContainer}>
            <video
              ref={videoRef}
              className={styles.video}
              playsInline
              muted
            />
            {cameraActive && landmarks && (
              <PoseCanvas
                landmarks={landmarks}
                corrections={currentCorrection.corrections}
                width={640}
                height={480}
              />
            )}
            {!cameraActive && (
              <div className={styles.videoPlaceholder}>
                <div className={styles.placeholderIcon}>📹</div>
                <p>Click &quot;Start Camera&quot; to begin</p>
                {cameraError && <p className={styles.cameraError}>{cameraError}</p>}
              </div>
            )}
          </div>

          {/* Controls */}
          <div className={styles.controls}>
            <div className={styles.moveSelector}>
              <label htmlFor="move-select" className={styles.moveLabel}>Practice Move:</label>
              <select
                id="move-select"
                className={styles.moveSelect}
                value={selectedMove}
                onChange={(e) => setSelectedMove(e.target.value)}
              >
                {AVAILABLE_MOVES.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>

            <div className={styles.controlButtons}>
              {!cameraActive ? (
                <button className="btn btn-primary" onClick={startCamera} id="start-camera-btn">
                  📹 Start Camera
                </button>
              ) : (
                <button className="btn btn-ghost" onClick={stopCamera} id="stop-camera-btn">
                  ⏹ Stop Camera
                </button>
              )}

              {cameraActive && !isTraining && (
                <button className="btn btn-secondary" onClick={startTraining} id="start-train-btn">
                  ▶ Start Training
                </button>
              )}

              {isTraining && (
                <button className="btn btn-ghost" onClick={stopTraining} id="stop-train-btn"
                  style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)' }}>
                  ⏹ End Session
                </button>
              )}
            </div>
          </div>

          {/* Reference Video hint */}
          {selectedMove !== 'free' && (
            <div className={styles.referenceHint}>
              <span>📖</span>
              <span>
                Practicing: <strong>{AVAILABLE_MOVES.find((m) => m.id === selectedMove)?.name}</strong>
                — Watch the reference in the <a href="/moves">Move Library</a>
              </span>
            </div>
          )}
        </div>

        {/* Right: Correction Panel */}
        <div className={styles.panelSection}>
          <CorrectionPanel
            moveName={currentCorrection.move}
            confidence={currentCorrection.confidence}
            corrections={currentCorrection.corrections}
            isCoach={false}
          />
        </div>
      </div>
    </div>
  );
}
