'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import PoseCanvas from '../components/PoseCanvas';
import CorrectionPanel from '../components/CorrectionPanel';
import api from '../services/api';
import { extract14Angles } from '../utils/angleCalculator';
import styles from './train.module.css';

// Constants
const AVAILABLE_MOVES = [
  { id: 'free', name: 'Free Practice (Auto Detect)' },
  { id: 'mae_geri', name: 'Front Kick (Mae Geri)' },
  { id: 'gyaku_zuki', name: 'Reverse Punch (Gyaku Zuki)' },
  { id: 'gedan_barai', name: 'Down Block (Gedan Barai)' },
];

// 🔥 Global singleton to prevent MediaPipe "File exists" crash in Next.js
let globalPoseInstance = null;

export default function TrainPage() {
  const { user } = useAuth();
  const router = useRouter();
  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  
  // State
  const [cameraActive, setCameraActive] = useState(false);
  const [isVideoUploaded, setIsVideoUploaded] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isRecordingRep, setIsRecordingRep] = useState(false);
  const [repCount, setRepCount] = useState(0);
  const [selectedMove, setSelectedMove] = useState('free');
  const [landmarks, setLandmarks] = useState(null);
  const [currentCorrection, setCurrentCorrection] = useState({ move: '', confidence: 0, corrections: [] });
  const [timer, setTimer] = useState(0);
  const [score, setScore] = useState(0);
  const [cameraError, setCameraError] = useState('');
  const [detectionHistory, setDetectionHistory] = useState([]);
  
  // Refs for callbacks (Prevents stale state in MediaPipe onResults)
  const timerRef = useRef(null);
  const frameBufferRef = useRef([]);
  const lastPredictionRef = useRef(null);
  const mediaPipeRef = useRef(null);
  const isRecordingRef = useRef(false); // 🔥 Crucial for MediaPipe loop
  const repCountRef = useRef(0);
  const isMediaPlayingRef = useRef(false); // 🔥 ADD THIS TO FIX THE LOOP

  // Sync state to refs for the MediaPipe callback
  useEffect(() => { isRecordingRef.current = isRecordingRep; }, [isRecordingRep]);
  useEffect(() => { repCountRef.current = repCount; }, [repCount]);

  // Initialize MediaPipe (Crash-Proof)
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

        // Always re-bind the onResults to get fresh scope, using Refs!
        globalPoseInstance.onResults((results) => {
          if (results.poseLandmarks) {
            const lmArray = Array.from(results.poseLandmarks);
            setLandmarks(lmArray);
            
            // Use the Ref here, NOT the state variable
            if (isRecordingRef.current && lmArray.length === 33) {
              const angles = extract14Angles(lmArray);
              frameBufferRef.current.push({ angles });
              
              if (frameBufferRef.current.length === 30) {
                setIsRecordingRep(false); // Stop recording UI
                isRecordingRef.current = false; // Stop recording Logic
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

  // Frame processing loop
  // 🔥 FIXED: Frame processing loop
  const processFrame = async () => {
    // If the ref says we are stopped, kill the loop immediately
    if (!isMediaPlayingRef.current) return;

    const video = videoRef.current;
    if (video && video.readyState >= 2 && mediaPipeRef.current && !video.paused) {
      try {
        await mediaPipeRef.current.send({ image: video });
      } catch (err) {
        console.warn("MediaPipe dropped a frame:", err);
      }
    }
    
    // Continuously loop as long as the ref is true
    requestAnimationFrame(processFrame);
  };

  // 📹 Start live camera
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
          deviceId: droidCam?.deviceId ? { exact: droidCam.deviceId } : undefined
        },
        audio: false,
      });
      
      video.srcObject = stream;
      await video.play();
      setCameraActive(true);
      // 🔥 Tell the loop to run, then start it
      isMediaPlayingRef.current = true; 
      requestAnimationFrame(processFrame);
    } catch (err) {
      console.error('Camera error:', err);
      setCameraError('Could not access camera.');
    }
  };

  // 📁 Handle Video Upload
  const handleVideoUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      stopCamera(); // Clear any existing stream
      const videoUrl = URL.createObjectURL(file);
      const video = videoRef.current;
      
      video.srcObject = null;
      video.src = videoUrl;
      video.loop = true; // Loop the video for easier practicing
      await video.play();
      
      setCameraActive(false);
      setIsVideoUploaded(true);
      setCameraError('');
      // 🔥 Tell the loop to run, then start it
      isMediaPlayingRef.current = true;
      
      requestAnimationFrame(processFrame);
    } catch (err) {
      console.error('Video upload error:', err);
      setCameraError('Failed to load video.');
    }
  };

  // Session Management
  const startTraining = useCallback(() => {
    setIsTraining(true);
    setTimer(0);
    setScore(0);
    setRepCount(0);
    setDetectionHistory([]);
    frameBufferRef.current = [];
    lastPredictionRef.current = null;
    timerRef.current = setInterval(() => setTimer(t => t + 1), 1000);
  }, []);

  const recordNextRep = () => {
    if (repCount >= 3) return;
    frameBufferRef.current = [];
    setIsRecordingRep(true); // Triggers MediaPipe to start saving 30 frames
  };

  const sendToClassifier = async (frames) => {
    try {
      const response = await api.post('/api/classify', {
        frames: frames,
        feature_set: 'angles14',
        model: 'Bi-LSTM'
      });
      
      const { move, confidence, inference_time_ms } = response.data;
      
      setCurrentCorrection({
        move: move,
        confidence: confidence,
        corrections: [
          { joint: 'system', message: `✅ ${move} (${(confidence*100).toFixed(1)}%)`, severity: confidence > 0.9 ? 'info' : 'warning' },
          { joint: 'performance', message: `⚡ ${inference_time_ms.toFixed(1)}ms`, severity: 'info' }
        ]
      });
      
      setScore(s => s + Math.round(confidence * 100));
      setDetectionHistory(prev => [{ move, confidence, timestamp: new Date().toLocaleTimeString() }, ...prev].slice(0, 10));
      
    } catch (error) {
      console.error('Classification error:', error);
      setCurrentCorrection({
        move: 'Error',
        confidence: 0,
        corrections: [{ joint: 'system', message: `Backend error: ${error.message}`, severity: 'error' }]
      });
    }
  };

  const stopTraining = useCallback(() => {
    setIsTraining(false);
    setIsRecordingRep(false);
    if (timerRef.current) clearInterval(timerRef.current);
    frameBufferRef.current = [];
  }, []);

  const stopCamera = useCallback(() => {
    isMediaPlayingRef.current = false; // 🔥 Instantly kill the frame loop
    if (videoRef.current) {
      if (videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
      videoRef.current.srcObject = null;
      videoRef.current.src = "";
    }
    setCameraActive(false);
    setIsVideoUploaded(false);
    stopTraining();
  }, [stopTraining]);

  // Cleanup
  useEffect(() => {
    return () => {
      stopCamera();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [stopCamera]);

  if (!user) return null;

  return (
    <div className={styles.trainPage}>
      <div className={styles.trainLayout}>
        <div className={styles.videoSection}>
          <div className={styles.videoHeader}>
            <h1 className={styles.videoTitle}>🎯 AI Training Mode</h1>
            {isTraining && (
              <div className={styles.sessionInfo}>
                <span className={styles.timerBadge}>⏱️ {Math.floor(timer/60)}:{(timer%60).toString().padStart(2,'0')}</span>
                <span className={styles.scoreBadge}>⭐ {score}pts</span>
              </div>
            )}
          </div>

          <div className={styles.videoContainer}>
            <video ref={videoRef} className={styles.video} playsInline muted={!isVideoUploaded} controls={isVideoUploaded} />
            {(cameraActive || isVideoUploaded) && landmarks && (
              <PoseCanvas landmarks={landmarks} corrections={currentCorrection.corrections} width={640} height={480} />
            )}
            {!cameraActive && !isVideoUploaded && (
              <div className={styles.videoPlaceholder}>
                <div className={styles.placeholderIcon}>📹</div>
                <p>Start Camera or Upload a Video to begin</p>
                {cameraError && <p className={styles.cameraError}>{cameraError}</p>}
              </div>
            )}
          </div>

          <div className={styles.controls}>
            <div className={styles.moveSelector}>
              <select className={styles.moveSelect} value={selectedMove} onChange={(e) => setSelectedMove(e.target.value)}>
                {AVAILABLE_MOVES.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            
            <div className={styles.controlButtons}>
              {/* Media Inputs */}
              {!cameraActive && !isVideoUploaded ? (
                <>
                  <button className="btn btn-primary" onClick={startCamera}>📹 Start Camera</button>
                  <input type="file" accept="video/mp4,video/webm,video/ogg" ref={fileInputRef} style={{ display: 'none' }} onChange={handleVideoUpload} />
                  <button className="btn btn-secondary" onClick={() => fileInputRef.current.click()}>📁 Upload Video</button>
                </>
              ) : (
                <button className="btn btn-ghost" onClick={stopCamera}>⏹ Stop Media</button>
              )}
              
              {/* Training Controls */}
              {(cameraActive || isVideoUploaded) && !isTraining && (
                <button className="btn btn-secondary" onClick={startTraining}>▶ Start Session</button>
              )}
              
              {isTraining && (
                <>
                  <button className="btn btn-primary" onClick={recordNextRep} disabled={isRecordingRep || repCount >= 3}>
                    {isRecordingRep ? "🔴 Recording 30 Frames..." : `🥋 Record Rep ${repCount + 1}/3`}
                  </button>
                  <button className="btn btn-ghost" onClick={stopTraining} style={{borderColor:'var(--accent-red)',color:'var(--accent-red)'}}>⏹ End Session</button>
                </>
              )}
            </div>
          </div>

          {/* History */}
          {detectionHistory.length > 0 && (
            <div className={styles.detectionHistory}>
              <h3>📊 Recent Detections</h3>
              <div className={styles.historyList}>
                {detectionHistory.map((det, idx) => (
                  <div key={idx} className={styles.historyItem}>
                    <span className={styles.historyMove}>{det.move}</span>
                    <span className={styles.historyConfidence}>{(det.confidence*100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className={styles.panelSection}>
          <CorrectionPanel moveName={currentCorrection.move} confidence={currentCorrection.confidence} corrections={currentCorrection.corrections} isCoach={false} />
        </div>
      </div>
    </div>
  );
}