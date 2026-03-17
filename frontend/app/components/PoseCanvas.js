'use client';

import { useRef, useEffect, useCallback } from 'react';
import styles from './PoseCanvas.module.css';

// MediaPipe Pose connections (pairs of landmark indices)
const POSE_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 7],
  [0, 4], [4, 5], [5, 6], [6, 8],
  [9, 10],
  [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27],
  [24, 26], [26, 28],
  [27, 29], [29, 31],
  [28, 30], [30, 32],
  [15, 17], [15, 19], [15, 21],
  [16, 18], [16, 20], [16, 22],
];

// Joint names for correction highlighting
const JOINT_MAP = {
  'left_shoulder': 11, 'right_shoulder': 12,
  'left_elbow': 13, 'right_elbow': 14,
  'left_wrist': 15, 'right_wrist': 16,
  'left_hip': 23, 'right_hip': 24,
  'left_knee': 25, 'right_knee': 26,
  'left_ankle': 27, 'right_ankle': 28,
  'left_hand': 19, 'right_hand': 20,
  'left_foot': 31, 'right_foot': 32,
};

export default function PoseCanvas({ landmarks, corrections = [], width = 640, height = 480 }) {
  const canvasRef = useRef(null);

  // Get indices of joints needing correction
  const correctionIndices = new Set();
  corrections.forEach(c => {
    const idx = JOINT_MAP[c.joint];
    if (idx !== undefined) correctionIndices.add(idx);
  });

  const drawSkeleton = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !landmarks || landmarks.length === 0) return;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw connections
    POSE_CONNECTIONS.forEach(([a, b]) => {
      const lmA = landmarks[a];
      const lmB = landmarks[b];
      if (!lmA || !lmB) return;
      if (lmA.visibility < 0.5 || lmB.visibility < 0.5) return;

      const needsCorrection =
        correctionIndices.has(a) || correctionIndices.has(b);

      ctx.beginPath();
      ctx.moveTo(lmA.x * canvas.width, lmA.y * canvas.height);
      ctx.lineTo(lmB.x * canvas.width, lmB.y * canvas.height);
      ctx.strokeStyle = needsCorrection ? '#FF5252' : '#00D4FF';
      ctx.lineWidth = needsCorrection ? 4 : 3;
      ctx.shadowColor = needsCorrection ? '#FF5252' : '#00D4FF';
      ctx.shadowBlur = needsCorrection ? 12 : 6;
      ctx.stroke();
      ctx.shadowBlur = 0;
    });

    // Draw landmarks
    landmarks.forEach((lm, i) => {
      if (lm.visibility < 0.5) return;

      const x = lm.x * canvas.width;
      const y = lm.y * canvas.height;
      const needsCorrection = correctionIndices.has(i);
      const radius = needsCorrection ? 7 : 5;

      // Glow
      ctx.beginPath();
      ctx.arc(x, y, radius + 4, 0, 2 * Math.PI);
      ctx.fillStyle = needsCorrection
        ? 'rgba(255, 82, 82, 0.3)'
        : 'rgba(0, 212, 255, 0.2)';
      ctx.fill();

      // Point
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = needsCorrection ? '#FF5252' : '#00D4FF';
      ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }, [landmarks, correctionIndices]);

  useEffect(() => {
    drawSkeleton();
  }, [drawSkeleton]);

  return (
    <canvas
      ref={canvasRef}
      className={styles.poseCanvas}
      width={width}
      height={height}
    />
  );
}
