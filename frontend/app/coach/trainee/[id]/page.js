'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '../../../context/AuthContext';
import { LineChart, RadarChart } from '../../../components/StatsChart';
import CorrectionPanel from '../../../components/CorrectionPanel';
import styles from '../../coach.module.css';

import api from '../../../services/api';

export default function TraineeDetailPage() {
  const { isAuthenticated, isCoach } = useAuth();
  const router = useRouter();
  const params = useParams();
  const traineeId = params.id;
  const [notes, setNotes] = useState('');
  const [trainee, setTrainee] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    if (isAuthenticated && !isCoach) {
      router.push('/dashboard');
      return;
    }
    
    if (isAuthenticated && isCoach) {
      api.get(`/api/coach/trainees/${traineeId}`)
        .then(res => {
          setTrainee(res.data);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }
  }, [isAuthenticated, isCoach, router, traineeId]);

  if (loading || !trainee) return <div className="loading-container"><div className="spinner" /></div>;

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
          {trainee.corrections && trainee.corrections.length > 0 ? trainee.corrections.map((c, i) => (
            <div key={i} className={styles.correctionItem}>
              <span className={styles.correctionJoint}>{c.joint.replace(/_/g, ' ')}</span>
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
          )) : (
            <p style={{ color: 'var(--text-secondary)' }}>No correction data yet.</p>
          )}
        </div>

        {/* Session History */}
        <div className={`glass-card ${styles.sessionsCard}`}>
          <h2 className={styles.sessionsTitle}>📋 Session History</h2>
          {trainee.sessions && trainee.sessions.length > 0 ? trainee.sessions.map((s, i) => (
            <div key={i} className={styles.sessionRow}>
              <span className={styles.sessionDate}>📅 {s.date}</span>
              <span className={styles.sessionDuration}>{s.duration}</span>
              <div className={styles.sessionMoves}>
                {s.moves && s.moves.map((m) => (
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
          )) : (
            <p style={{ color: 'var(--text-secondary)' }}>No sessions recorded yet.</p>
          )}
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
