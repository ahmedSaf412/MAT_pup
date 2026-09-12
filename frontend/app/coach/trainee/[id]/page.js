'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '../../../context/AuthContext';
import { LineChart, RadarChart } from '../../../components/StatsChart';
import CorrectionPanel from '../../../components/CorrectionPanel';
import styles from '../../coach.module.css';

import api from '../../../services/api';

// ── Tabs ──────────────────────────────────────────────────────────────────────
const TABS = ['Overview', 'Video Archive'];

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatDuration(seconds) {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function statusBadge(status) {
  const map = {
    done:       { color: '#22c55e', label: '✅ Processed' },
    processing: { color: '#f59e0b', label: '⏳ Processing' },
    uploaded:   { color: '#60a5fa', label: '📤 Uploaded' },
    completed:  { color: '#22c55e', label: '✅ Completed' },
    error:      { color: '#ef4444', label: '❌ Error' },
  };
  const s = map[status] ?? { color: '#888', label: status };
  return (
    <span style={{
      fontSize: '0.72rem', fontWeight: 600, padding: '2px 8px',
      borderRadius: '999px', background: `${s.color}22`, color: s.color,
      border: `1px solid ${s.color}55`,
    }}>
      {s.label}
    </span>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function TraineeDetailPage() {
  const { isAuthenticated, isCoach } = useAuth();
  const router   = useRouter();
  const params   = useParams();
  const traineeId = params.id;

  const [activeTab,  setActiveTab]  = useState('Overview');
  const [notes,      setNotes]      = useState('');
  const [trainee,    setTrainee]    = useState(null);
  const [recordings, setRecordings] = useState([]);
  const [recLoading, setRecLoading] = useState(false);
  const [activeVideo, setActiveVideo] = useState(null);   // currently playing rec
  const [loading,    setLoading]    = useState(true);
  const [feedbackText, setFeedbackText] = useState('');

  useEffect(() => {
    if (!isAuthenticated) { router.push('/login'); return; }
    if (isAuthenticated && !isCoach) { router.push('/dashboard'); return; }

    if (isAuthenticated && isCoach) {
      api.get(`/api/coach/trainees/${traineeId}`)
        .then(res => { setTrainee(res.data); setLoading(false); })
        .catch(err => { console.error(err); setLoading(false); });
    }
  }, [isAuthenticated, isCoach, router, traineeId]);

  const handleSubmitFeedback = async () => {
    if (!activeVideo || !feedbackText.trim()) return;
    try {
      const formData = new FormData();
      formData.append('message', feedbackText);
      await api.post(`/api/recordings/${activeVideo.id}/feedback`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert('Feedback saved successfully! The trainee will be able to see it.');
      setFeedbackText('');
    } catch (e) {
      console.error(e);
      alert('Failed to save feedback');
    }
  };

  // Lazy-load recordings only when the tab is opened
  useEffect(() => {
    if (activeTab !== 'Video Archive' || recordings.length > 0) return;
    setRecLoading(true);
    api.get(`/api/coach/trainee/${traineeId}/recordings`)
      .then(res => setRecordings(res.data ?? []))
      .catch(err => console.error('[recordings]', err))
      .finally(() => setRecLoading(false));
  }, [activeTab, traineeId, recordings.length]);

  if (loading || !trainee) return (
    <div className="loading-container"><div className="spinner" /></div>
  );

  const BACKEND = 'http://localhost:8000';

  return (
    <div className={styles.detailPage}>
      <div className="container">
        <Link href="/coach" className={styles.backLink}>← Back to Dashboard</Link>

        {/* Header */}
        <div className={styles.detailHeader}>
          <div className={styles.detailAvatar}>{trainee.name.charAt(0)}</div>
          <div>
            <h1 className={styles.detailName}>{trainee.name}</h1>
            <div className={styles.detailMeta}>
              <span>📧 {trainee.email}</span>
              <span>🥋 {trainee.belt.charAt(0).toUpperCase() + trainee.belt.slice(1)} Belt</span>
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              id={`tab-${tab.toLowerCase().replace(' ', '-')}`}
              style={{
                padding: '0.6rem 1.2rem',
                borderRadius: '8px 8px 0 0',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.85rem',
                background: activeTab === tab ? 'rgba(0,212,255,0.12)' : 'transparent',
                color:      activeTab === tab ? 'var(--accent-cyan, #00d4ff)' : 'var(--text-secondary, #888)',
                borderBottom: activeTab === tab ? '2px solid var(--accent-cyan, #00d4ff)' : '2px solid transparent',
                transition: 'all 0.2s',
              }}
            >
              {tab === 'Video Archive' ? `🎬 ${tab}` : `📊 ${tab}`}
            </button>
          ))}
        </div>

        {/* ── Overview tab ─────────────────────────────────────────────────── */}
        {activeTab === 'Overview' && (
          <>
            {/* Charts */}
            <div className={styles.chartsGrid}>
              <div className="glass-card">
                <LineChart title="Score Progress" data={{ labels: trainee.progressLabels, scores: trainee.progressScores }} />
              </div>
              <div className="glass-card">
                <RadarChart title="Move Accuracy" data={trainee.moveAccuracy} />
              </div>
            </div>

            {/* Correction Patterns */}
            <div className={`glass-card ${styles.correctionsCard}`}>
              <h2 className={styles.correctionsTitle}>📐 Correction Patterns</h2>
              {trainee.corrections && trainee.corrections.length > 0
                ? trainee.corrections.map((c, i) => (
                  <div key={i} className={styles.correctionItem}>
                    <span className={styles.correctionJoint}>{c.joint.replace(/_/g, ' ')}</span>
                    <div className={styles.correctionFreq}>
                      <div className={styles.freqBar}>
                        <div className={styles.freqFill} style={{ width: `${c.frequency}%`, background: c.color }} />
                      </div>
                    </div>
                    <span className={styles.correctionPercent} style={{ color: c.color }}>{c.frequency}%</span>
                  </div>
                ))
                : <p style={{ color: 'var(--text-secondary)' }}>No correction data yet.</p>
              }
            </div>

            {/* Session History */}
            <div className={`glass-card ${styles.sessionsCard}`}>
              <h2 className={styles.sessionsTitle}>📋 Session History</h2>
              {trainee.sessions && trainee.sessions.length > 0
                ? trainee.sessions.map((s, i) => (
                  <div key={i} className={styles.sessionRow}>
                    <span className={styles.sessionDate}>📅 {s.date}</span>
                    <span className={styles.sessionDuration}>{s.duration}</span>
                    <div className={styles.sessionMoves}>
                      {s.moves && s.moves.map(m => <span key={m} className="badge badge-blue">{m}</span>)}
                    </div>
                    <span
                      className={styles.sessionScore}
                      style={{ color: s.score >= 80 ? 'var(--accent-green)' : s.score >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)' }}
                    >
                      {s.score}%
                    </span>
                  </div>
                ))
                : <p style={{ color: 'var(--text-secondary)' }}>No sessions recorded yet.</p>
              }
            </div>

            {/* Coach Notes */}
            <div className={`glass-card ${styles.notesSection}`}>
              <h2 className={styles.notesTitle}>📝 Coach Notes</h2>
              <textarea
                className={styles.notesTextarea}
                placeholder="Write notes about this trainee's progress, areas to focus on, training plan..."
                value={notes}
                onChange={e => setNotes(e.target.value)}
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
          </>
        )}

        {/* ── Video Archive tab ─────────────────────────────────────────────── */}
        {activeTab === 'Video Archive' && (
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h2 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 700 }}>
              🎬 Training Video Archive
            </h2>

            {recLoading && (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>
                <div className="spinner" style={{ margin: '0 auto 0.5rem' }} />
                Loading recordings…
              </div>
            )}

            {!recLoading && recordings.length === 0 && (
              <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>
                No recordings found for this trainee yet.
              </p>
            )}

            {!recLoading && recordings.length > 0 && (
              <>
                {/* Inline video player */}
                {activeVideo && (
                  <div style={{
                    marginBottom: '1.5rem',
                    background: '#000',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    position: 'relative',
                  }}>
                    <video
                      key={activeVideo.file_url}
                      controls
                      autoPlay
                      style={{ width: '100%', maxHeight: '400px', display: 'block' }}
                      src={`${BACKEND}${activeVideo.file_url}`}
                    />
                    <button
                      onClick={() => setActiveVideo(null)}
                      style={{
                        position: 'absolute', top: 8, right: 8,
                        background: 'rgba(0,0,0,0.7)', color: '#fff',
                        border: 'none', borderRadius: '6px',
                        padding: '4px 10px', cursor: 'pointer', fontSize: '0.8rem',
                      }}
                    >
                      ✕ Close
                    </button>
                    <div style={{ padding: '0.75rem 1rem', background: 'rgba(255,255,255,0.04)' }}>
                      <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                        Session #{activeVideo.session_id} · {formatDate(activeVideo.created_at)} ·{' '}
                        {formatDuration(activeVideo.duration_seconds)}
                      </span>
                    </div>
                    {/* Coach Feedback Section */}
                    <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.02)', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                      <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#00d4ff' }}>Leave Feedback</h3>
                      <textarea
                        value={feedbackText}
                        onChange={(e) => setFeedbackText(e.target.value)}
                        placeholder="Type your feedback, corrections, or advice for this recording..."
                        style={{
                          width: '100%', minHeight: '80px', padding: '0.75rem',
                          background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px', color: '#fff', fontSize: '0.85rem', resize: 'vertical'
                        }}
                      />
                      <button
                        onClick={handleSubmitFeedback}
                        disabled={!feedbackText.trim()}
                        style={{
                          marginTop: '0.5rem', padding: '0.5rem 1rem',
                          background: feedbackText.trim() ? '#00d4ff' : 'rgba(255,255,255,0.1)',
                          color: feedbackText.trim() ? '#000' : '#888',
                          border: 'none', borderRadius: '6px', fontWeight: 600,
                          cursor: feedbackText.trim() ? 'pointer' : 'not-allowed',
                          fontSize: '0.85rem'
                        }}
                      >
                        Submit Feedback
                      </button>
                    </div>
                  </div>
                )}

                {/* Recordings table */}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#888' }}>
                        <th style={{ textAlign: 'left',   padding: '0.5rem 0.75rem' }}>#</th>
                        <th style={{ textAlign: 'left',   padding: '0.5rem 0.75rem' }}>Date</th>
                        <th style={{ textAlign: 'left',   padding: '0.5rem 0.75rem' }}>Duration</th>
                        <th style={{ textAlign: 'left',   padding: '0.5rem 0.75rem' }}>Status</th>
                        <th style={{ textAlign: 'center', padding: '0.5rem 0.75rem' }}>Play</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recordings.map((rec, idx) => {
                        const isPlaying = activeVideo?.id === rec.id;
                        return (
                          <tr
                            key={rec.id}
                            style={{
                              borderBottom: '1px solid rgba(255,255,255,0.05)',
                              background: isPlaying ? 'rgba(0,212,255,0.07)' : 'transparent',
                              transition: 'background 0.2s',
                            }}
                          >
                            <td style={{ padding: '0.6rem 0.75rem', color: '#666' }}>
                              {recordings.length - idx}
                            </td>
                            <td style={{ padding: '0.6rem 0.75rem' }}>
                              {formatDate(rec.created_at)}
                            </td>
                            <td style={{ padding: '0.6rem 0.75rem' }}>
                              {formatDuration(rec.duration_seconds)}
                            </td>
                            <td style={{ padding: '0.6rem 0.75rem' }}>
                              {statusBadge(rec.status)}
                            </td>
                            <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center' }}>
                              <button
                                id={`play-rec-${rec.id}`}
                                onClick={() => setActiveVideo(isPlaying ? null : rec)}
                                style={{
                                  background: isPlaying ? 'rgba(0,212,255,0.2)' : 'rgba(255,255,255,0.06)',
                                  border: `1px solid ${isPlaying ? 'rgba(0,212,255,0.5)' : 'rgba(255,255,255,0.12)'}`,
                                  color: isPlaying ? '#00d4ff' : '#ccc',
                                  borderRadius: '6px',
                                  padding: '4px 14px',
                                  cursor: 'pointer',
                                  fontSize: '0.8rem',
                                  fontWeight: 600,
                                  transition: 'all 0.2s',
                                }}
                              >
                                {isPlaying ? '⏹ Close' : '▶ Play'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
