'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import styles from './coach.module.css';

const MOCK_TRAINEES = [
  {
    id: 1, name: 'Mohamed Ali', belt: 'yellow', email: 'mohamed@test.com',
    lastSession: '2026-03-10', lastScore: 87, totalSessions: 24, avgScore: 78,
    recentMoves: ['Front Kick', 'Roundhouse'],
  },
  {
    id: 2, name: 'Sara Ahmed', belt: 'green', email: 'sara@test.com',
    lastSession: '2026-03-09', lastScore: 92, totalSessions: 38, avgScore: 85,
    recentMoves: ['Side Kick', 'Block', 'Punch'],
  },
  {
    id: 3, name: 'Omar Hassan', belt: 'white', email: 'omar@test.com',
    lastSession: '2026-03-08', lastScore: 64, totalSessions: 8, avgScore: 61,
    recentMoves: ['Front Kick'],
  },
  {
    id: 4, name: 'Fatima Nour', belt: 'blue', email: 'fatima@test.com',
    lastSession: '2026-03-10', lastScore: 95, totalSessions: 52, avgScore: 89,
    recentMoves: ['Roundhouse', 'Back Kick', 'Knife Hand'],
  },
  {
    id: 5, name: 'Ahmed Khaled', belt: 'orange', email: 'ahmed@test.com',
    lastSession: '2026-03-07', lastScore: 73, totalSessions: 15, avgScore: 70,
    recentMoves: ['Front Kick', 'Stance'],
  },
];

const BELT_COLORS = {
  white: '#FFFFFF', yellow: '#FFD740', orange: '#FF9100',
  green: '#00E676', blue: '#448AFF', brown: '#8D6E63', black: '#424242',
};

export default function CoachDashboardPage() {
  const { user, isAuthenticated, isCoach } = useAuth();
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [trainees] = useState(MOCK_TRAINEES);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
    if (isAuthenticated && !isCoach) router.push('/dashboard');
  }, [isAuthenticated, isCoach, router]);

  if (!user) return <div className="loading-container"><div className="spinner" /></div>;

  const filtered = trainees.filter((t) =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalTrainees = trainees.length;
  const overallAvg = Math.round(trainees.reduce((s, t) => s + t.avgScore, 0) / totalTrainees);
  const totalSessionsAll = trainees.reduce((s, t) => s + t.totalSessions, 0);

  return (
    <div className={styles.coachPage}>
      <div className="container">
        {/* Welcome */}
        <div className={styles.welcome}>
          <div>
            <h1 className={styles.welcomeTitle}>
              Coach <span className={styles.nameAccent}>{user.full_name}</span>
            </h1>
            <p className={styles.welcomeSub}>🏆 Monitor and guide your trainees</p>
          </div>
        </div>

        {/* Stats */}
        <div className={styles.statsGrid}>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>👥</div>
            <div className={styles.statValue}>{totalTrainees}</div>
            <div className={styles.statLabel}>Total Trainees</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>⭐</div>
            <div className={styles.statValue}>{overallAvg}%</div>
            <div className={styles.statLabel}>Avg Score</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>🏋️</div>
            <div className={styles.statValue}>{totalSessionsAll}</div>
            <div className={styles.statLabel}>Total Sessions</div>
          </div>
          <div className={`glass-card ${styles.statCard}`}>
            <div className={styles.statIcon}>📈</div>
            <div className={styles.statValue}>+12%</div>
            <div className={styles.statLabel}>Week Progress</div>
          </div>
        </div>

        {/* Search */}
        <div className={styles.searchBar}>
          <input
            type="text"
            className="form-input"
            placeholder="Search trainees..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            id="trainee-search"
            style={{ maxWidth: 400 }}
          />
        </div>

        {/* Trainees List */}
        <div className={styles.traineesGrid}>
          {filtered.map((t) => (
            <Link
              key={t.id}
              href={`/coach/trainee/${t.id}`}
              className={`glass-card ${styles.traineeCard}`}
              id={`trainee-card-${t.id}`}
            >
              <div className={styles.traineeHeader}>
                <div className={styles.traineeAvatar}>
                  {t.name.charAt(0)}
                </div>
                <div>
                  <div className={styles.traineeName}>{t.name}</div>
                  <div className={styles.traineeEmail}>{t.email}</div>
                </div>
                <span
                  className={styles.beltBadge}
                  style={{
                    background: `${BELT_COLORS[t.belt]}22`,
                    color: BELT_COLORS[t.belt],
                    border: `1px solid ${BELT_COLORS[t.belt]}44`,
                  }}
                >
                  {t.belt} belt
                </span>
              </div>

              <div className={styles.traineeStats}>
                <div className={styles.tStat}>
                  <span className={styles.tStatLabel}>Last Score</span>
                  <span
                    className={styles.tStatValue}
                    style={{
                      color: t.lastScore >= 80 ? 'var(--accent-green)' : t.lastScore >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)',
                    }}
                  >
                    {t.lastScore}%
                  </span>
                </div>
                <div className={styles.tStat}>
                  <span className={styles.tStatLabel}>Avg Score</span>
                  <span className={styles.tStatValue}>{t.avgScore}%</span>
                </div>
                <div className={styles.tStat}>
                  <span className={styles.tStatLabel}>Sessions</span>
                  <span className={styles.tStatValue}>{t.totalSessions}</span>
                </div>
              </div>

              <div className={styles.traineeFooter}>
                <div className={styles.recentMoves}>
                  {t.recentMoves.map((m) => (
                    <span key={m} className="badge badge-blue">{m}</span>
                  ))}
                </div>
                <span className={styles.lastActive}>Last: {t.lastSession}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
