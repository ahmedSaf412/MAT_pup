'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
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
  const [trainees, setTrainees] = useState([]);
  const [requests, setRequests] = useState([]);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
    if (isAuthenticated && !isCoach) router.push('/dashboard');
    
    if (isAuthenticated && isCoach) {
      api.get('/api/coach/trainees').then(res => setTrainees(res.data)).catch(() => {});
      api.get('/api/coach/requests').then(res => setRequests(res.data)).catch(() => {});
    }
  }, [isAuthenticated, isCoach, router]);

  const handleAcceptRequest = async (traineeId) => {
    try {
      await api.post(`/api/coach/requests/${traineeId}/accept`);
      setRequests(requests.filter(r => r.id !== traineeId));
      api.get('/api/coach/trainees').then(res => setTrainees(res.data)).catch(() => {});
    } catch (e) {
      alert("Failed to accept trainee.");
    }
  };

  if (!user) return <div className="loading-container"><div className="spinner" /></div>;

  const filtered = trainees.filter((t) =>
    (t.full_name || t.name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalTrainees = trainees.length;
  const overallAvg = 85; // Mocking average for now since DB might not have score history yet
  const totalSessionsAll = 120; // Mocking total sessions

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
                  {(t.full_name || t.name || '?').charAt(0)}
                </div>
                <div>
                  <div className={styles.traineeName}>{t.full_name || t.name}</div>
                  <div className={styles.traineeEmail}>{t.email}</div>
                </div>
                <span
                  className={styles.beltBadge}
                  style={{
                    background: `${BELT_COLORS[t.belt_level || t.belt]}22`,
                    color: BELT_COLORS[t.belt_level || t.belt],
                    border: `1px solid ${BELT_COLORS[t.belt_level || t.belt]}44`,
                  }}
                >
                  {t.belt_level || t.belt} belt
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
                  <span className="badge badge-blue">Mae Geri</span>
                </div>
                <span className={styles.lastActive}>Last: N/A</span>
              </div>
            </Link>
          ))}
        </div>
        
        {/* Requests List */}
        {requests.length > 0 && (
          <div style={{ marginTop: '40px' }}>
            <h2 className={styles.welcomeTitle} style={{ fontSize: '1.5rem', marginBottom: '15px' }}>Incoming Requests</h2>
            <div className={styles.traineesGrid}>
              {requests.map(r => (
                <div key={r.id} className={`glass-card ${styles.traineeCard}`}>
                  <div className={styles.traineeHeader}>
                    <div className={styles.traineeAvatar}>{(r.full_name || '?').charAt(0)}</div>
                    <div>
                      <div className={styles.traineeName}>{r.full_name}</div>
                      <div className={styles.traineeEmail}>{r.email}</div>
                    </div>
                  </div>
                  <button className="btn btn-primary" style={{ width: '100%', marginTop: '15px' }} onClick={() => handleAcceptRequest(r.id)}>
                    Accept Request
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
