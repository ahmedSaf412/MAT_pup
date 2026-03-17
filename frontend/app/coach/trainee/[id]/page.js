'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '../../../context/AuthContext';
import { LineChart, RadarChart } from '../../../components/StatsChart';
import CorrectionPanel from '../../../components/CorrectionPanel';
import styles from '../../coach.module.css';

// Mock trainee data
const TRAINEES_DATA = {
  1: {
    name: 'Mohamed Ali', belt: 'yellow', email: 'mohamed@test.com',
    sessions: [
      { date: '2026-03-10', duration: '25m', score: 87, moves: ['Front Kick', 'Roundhouse'] },
      { date: '2026-03-08', duration: '18m', score: 74, moves: ['Side Kick'] },
      { date: '2026-03-06', duration: '32m', score: 82, moves: ['Front Kick', 'Punch'] },
      { date: '2026-03-04', duration: '20m', score: 68, moves: ['Roundhouse'] },
    ],
    corrections: [
      { joint: 'guard_hand', frequency: 78, color: 'var(--accent-red)' },
      { joint: 'hip_rotation', frequency: 65, color: 'var(--accent-orange)' },
      { joint: 'knee_height', frequency: 45, color: 'var(--accent-yellow)' },
      { joint: 'stance_width', frequency: 22, color: 'var(--accent-green)' },
    ],
    progressScores: [45, 55, 60, 68, 74, 82, 87],
    progressLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7'],
    moveAccuracy: { labels: ['Front Kick', 'Roundhouse', 'Side Kick', 'Punch', 'Block'], scores: [82, 68, 55, 78, 70] },
  },
  2: {
    name: 'Sara Ahmed', belt: 'green', email: 'sara@test.com',
    sessions: [
      { date: '2026-03-09', duration: '30m', score: 92, moves: ['Side Kick', 'Block', 'Punch'] },
      { date: '2026-03-07', duration: '22m', score: 88, moves: ['Roundhouse', 'Front Kick'] },
    ],
    corrections: [
      { joint: 'hip_rotation', frequency: 35, color: 'var(--accent-yellow)' },
      { joint: 'retraction_speed', frequency: 28, color: 'var(--accent-green)' },
    ],
    progressScores: [65, 72, 78, 82, 85, 88, 92],
    progressLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7'],
    moveAccuracy: { labels: ['Front Kick', 'Roundhouse', 'Side Kick', 'Punch', 'Block'], scores: [90, 85, 88, 82, 92] },
  },
};

// Default data for IDs not found
const DEFAULT_TRAINEE = {
  name: 'Trainee', belt: 'white', email: 'trainee@test.com',
  sessions: [
    { date: '2026-03-10', duration: '20m', score: 70, moves: ['Front Kick'] },
  ],
  corrections: [
    { joint: 'guard_hand', frequency: 50, color: 'var(--accent-yellow)' },
  ],
  progressScores: [40, 50, 55, 60, 65, 68, 70],
  progressLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7'],
  moveAccuracy: { labels: ['Front Kick', 'Roundhouse', 'Side Kick', 'Punch', 'Block'], scores: [70, 55, 50, 60, 65] },
};

export default function TraineeDetailPage() {
  const { isAuthenticated, isCoach } = useAuth();
  const router = useRouter();
  const params = useParams();
  const traineeId = params.id;
  const [notes, setNotes] = useState('');

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
    if (isAuthenticated && !isCoach) router.push('/dashboard');
  }, [isAuthenticated, isCoach, router]);

  const trainee = TRAINEES_DATA[traineeId] || DEFAULT_TRAINEE;

  return (
    <div className={styles.detailPage}>
      <div className="container">
        <Link href="/coach" className={styles.backLink}>
          ← Back to Dashboard
        </Link>

        {/* Header */}
        <div className={styles.detailHeader}>
          <div className={styles.detailAvatar}>
            {trainee.name.charAt(0)}
          </div>
          <div>
            <h1 className={styles.detailName}>{trainee.name}</h1>
            <div className={styles.detailMeta}>
              <span>📧 {trainee.email}</span>
              <span>🥋 {trainee.belt.charAt(0).toUpperCase() + trainee.belt.slice(1)} Belt</span>
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className={styles.chartsGrid}>
          <div className="glass-card">
            <LineChart
              title="Score Progress"
              data={{ labels: trainee.progressLabels, scores: trainee.progressScores }}
            />
          </div>
          <div className="glass-card">
            <RadarChart
              title="Move Accuracy"
              data={trainee.moveAccuracy}
            />
          </div>
        </div>

        {/* Correction Patterns (Coach Analysis) */}
        <div className={`glass-card ${styles.correctionsCard}`}>
          <h2 className={styles.correctionsTitle}>📐 Correction Patterns</h2>
          {trainee.corrections.map((c, i) => (
            <div key={i} className={styles.correctionItem}>
              <span className={styles.correctionJoint}>{c.joint.replace('_', ' ')}</span>
              <div className={styles.correctionFreq}>
                <div className={styles.freqBar}>
                  <div
                    className={styles.freqFill}
                    style={{ width: `${c.frequency}%`, background: c.color }}
                  />
                </div>
              </div>
              <span
                className={styles.correctionPercent}
                style={{ color: c.color }}
              >
                {c.frequency}%
              </span>
            </div>
          ))}
        </div>

        {/* Session History */}
        <div className={`glass-card ${styles.sessionsCard}`}>
          <h2 className={styles.sessionsTitle}>📋 Session History</h2>
          {trainee.sessions.map((s, i) => (
            <div key={i} className={styles.sessionRow}>
              <span className={styles.sessionDate}>📅 {s.date}</span>
              <span className={styles.sessionDuration}>{s.duration}</span>
              <div className={styles.sessionMoves}>
                {s.moves.map((m) => (
                  <span key={m} className="badge badge-blue">{m}</span>
                ))}
              </div>
              <span
                className={styles.sessionScore}
                style={{
                  color: s.score >= 80 ? 'var(--accent-green)' : s.score >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)',
                }}
              >
                {s.score}%
              </span>
            </div>
          ))}
        </div>

        {/* Coach Notes */}
        <div className={`glass-card ${styles.notesSection}`}>
          <h2 className={styles.notesTitle}>📝 Coach Notes</h2>
          <textarea
            className={styles.notesTextarea}
            placeholder="Write notes about this trainee's progress, areas to focus on, training plan..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            id="coach-notes"
          />
          <button
            className="btn btn-primary btn-sm"
            style={{ marginTop: 'var(--space-md)' }}
            onClick={() => alert('Notes saved (demo)')}
            id="save-notes-btn"
          >
            Save Notes
          </button>
        </div>
      </div>
    </div>
  );
}
