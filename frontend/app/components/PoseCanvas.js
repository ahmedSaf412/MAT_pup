'use client';

/**
 * PoseCanvas — unified colorful skeleton overlay.
 *
 * Props:
 *   landmarks   – MediaPipe poseLandmarks array (33 {x,y,z,visibility})
 *   corrections – array of { joint: string } correction objects
 *   videoRef    – RefObject<HTMLVideoElement> — canvas auto-sizes to video bounds
 *   mirrored    – boolean. Pass true for live-camera so skeleton matches mirrored video.
 */

import { useRef, useEffect, useCallback } from 'react';
import styles from './PoseCanvas.module.css';
import { drawSkeleton } from '../utils/skeletonDraw';

// Joint name → landmark index
const JOINT_MAP = {
  left_shoulder: 11, right_shoulder: 12,
  left_elbow:    13, right_elbow:    14,
  left_wrist:    15, right_wrist:    16,
  left_hip:      23, right_hip:      24,
  left_knee:     25, right_knee:     26,
  left_ankle:    27, right_ankle:    28,
  left_hand:     19, right_hand:     20,
  left_foot:     31, right_foot:     32,
  spine_lean:    23,
};

export default function PoseCanvas({
  landmarks,
  corrections = [],
  videoRef    = null,
  mirrored    = false,
}) {
  const canvasRef = useRef(null);

  // Build correction index set from correction joint names
  const correctionSet = new Set(
    corrections
      .map(c => JOINT_MAP[c.joint])
      .filter(idx => idx !== undefined)
  );

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !landmarks || landmarks.length === 0) return;

    // Auto-size canvas to the video's displayed bounds
    const video = videoRef?.current;
    if (video && video.clientWidth > 0) {
      if (canvas.width  !== video.clientWidth)  canvas.width  = video.clientWidth;
      if (canvas.height !== video.clientHeight) canvas.height = video.clientHeight;
    }

    const ctx = canvas.getContext('2d');
    drawSkeleton(ctx, canvas.width, canvas.height, landmarks, {
      correctionSet,
      mirrored,
    });
  }, [landmarks, correctionSet, videoRef, mirrored]);

  // Redraw on every landmark update
  useEffect(() => { render(); }, [render]);

  // Resize canvas whenever the video element resizes (responsive layouts)
  useEffect(() => {
    const video = videoRef?.current;
    if (!video) return;
    const ro = new ResizeObserver(() => render());
    ro.observe(video);
    return () => ro.disconnect();
  }, [videoRef, render]);

  return <canvas ref={canvasRef} className={styles.poseCanvas} />;
}
