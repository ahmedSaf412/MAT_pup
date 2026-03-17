'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import { LineChart, RadarChart } from '../components/StatsChart';
import styles from './dashboard.module.css';

// Mock data for demo
const MOCK_SESSIONS = [
  { id: 1, date: '2026-03-10', duration: '25 min', score: 87, moves: ['Front Kick', 'Roundhouse Kick'] },
  { id: 2, date: '2026-03-08', duration: '18 min', score: 74, moves: ['Side Kick', 'Block'] },
  { id: 3, date: '2026-03-06', duration: '32 min', score: 82, moves: ['Front Kick', 'Punch', 'Stance'] },
  { id: 4, date: '2026-03-04', duration: '20 min', score: 68, moves: ['Roundhouse Kick'] },
  { id: 5, date: '2026-03-02', duration: '28 min', score: 91, moves: ['Punch', 'Block', 'Front Kick'] },
];

export default function DashboardPage() {
  const { user, isAuthenticated, isCoach } = useAuth();
  const router = useRouter();
  const [sessions] = useState(MOCK_SESSIONS);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
    if (isCoach) router.push('/coach');
  }, [isAuthenticated, isCoach, router]);

  if (!user) return <div className="loading-container"><div className="spinner" /></div>;

  const totalSessions = sessions.length;
  const avgScore = Math.round(sessions.reduce((s, se) => s + se.score, 0) / totalSessions);
  const totalTime = sessions.reduce((t, se) => t + parseInt(se.duration), 0);

  return (
    <div className={styles.dashboard}>
      <div className="container">
        {/* Welcome */}
        <div className={styles.welcome}>
          <div>
            <h1 className={styles.welcomeTitle}>
              Welcome back, <span className={styles.nameAccent}>{user.full_name}</span>
            </h1>
            <p className={styles.welcomeSub}>
              🥋 {(user.belt_level || 'White').charAt(0).toUpperCase() + (user.belt_level || 'white').slice(1)} Belt • Keep pushing your limits!
            </p>
          </div>
          <Link href="/train" className="btn btn-primary" id="start-training-btn">
            🎯 Start Training
          </Link>
        </div>

        {/* Stats Cards */}
        <div className={styles.statsGrid}>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>🏋️</div>
            <div className={styles.statValue}>{totalSessions}</div>
            <div className={styles.statLabel}>Total Sessions</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>⭐</div>
            <div className={styles.statValue}>{avgScore}%</div>
            <div className={styles.statLabel}>Average Score</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>⏱️</div>
            <div className={styles.statValue}>{totalTime}m</div>
            <div className={styles.statLabel}>Total Training</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>🔥</div>
            <div className={styles.statValue}>5</div>
            <div className={styles.statLabel}>Day Streak</div>
          </div>
        </div>

        {/* Charts */}
        <div className={styles.chartsGrid}>
          <div className="glass-card">
            <LineChart title="Score Progress" />
          </div>
          <div className="glass-card">
            <RadarChart title="Move Accuracy" />
          </div>
        </div>

        {/* Recent Sessions */}
        <div className={`glass-card ${styles.sessionsCard}`}>
          <div className={styles.sessionsHeader}>
            <h2 className={styles.sessionsTitle}>Recent Sessions</h2>
          </div>
          <div className={styles.sessionsList}>
            {sessions.map((s) => (
              <div key={s.id} className={styles.sessionRow}>
                <div className={styles.sessionDate}>
                  <span className={styles.dateIcon}>📅</span>
                  {s.date}
                </div>
                <div className={styles.sessionDuration}>{s.duration}</div>
                <div className={styles.sessionMoves}>
                  {s.moves.map((m) => (
                    <span key={m} className="badge badge-blue">{m}</span>
                  ))}
                </div>
                <div
                  className={styles.sessionScore}
                  style={{
                    color: s.score >= 80 ? 'var(--accent-green)' : s.score >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)',
                  }}
                >
                  {s.score}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className={styles.quickActions}>
          <Link href="/train" className={`glass-card ${styles.actionCard}`} id="quick-train">
            <span className={styles.actionIcon}>🎯</span>
            <span className={styles.actionText}>Start Training</span>
          </Link>
          <Link href="/moves" className={`glass-card ${styles.actionCard}`} id="quick-moves">
            <span className={styles.actionIcon}>📚</span>
            <span className={styles.actionText}>Browse Moves</span>
          </Link>
          <Link href="/profile" className={`glass-card ${styles.actionCard}`} id="quick-profile">
            <span className={styles.actionIcon}>⚙️</span>
            <span className={styles.actionText}>Edit Profile</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
