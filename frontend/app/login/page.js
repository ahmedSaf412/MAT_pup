'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import styles from './auth.module.css';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function LoginPage() {
  const router = useRouter();
  const { login, demoLogin } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // null = still checking, true = ready, false = not yet reachable
  const [backendReady, setBackendReady] = useState(null);

  // Poll /health every 2 s using plain fetch (no axios interceptors, no extra headers)
  useEffect(() => {
    let interval;
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch(`${BACKEND}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(3000),
        });
        if (res.ok && !cancelled) {
          setBackendReady(true);
          clearInterval(interval);
        } else if (!cancelled) {
          setBackendReady(false);
        }
      } catch {
        if (!cancelled) setBackendReady(false);
      }
    };

    check();
    interval = setInterval(check, 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await login(formData.email, formData.password);
    if (result.success) {
      router.push('/dashboard');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleDemo = (role) => {
    demoLogin(role);
    router.push(role === 'coach' ? '/coach' : '/dashboard');
  };

  return (
    <div className={styles.authPage}>
      <div className={styles.authCard}>
        <div className={styles.authHeader}>
          <span className={styles.authIcon}>🥋</span>
          <h1 className={styles.authTitle}>Welcome Back</h1>
          <p className={styles.authSubtitle}>Login to continue your training</p>
        </div>

        {/* Server status banner — purely informational, never blocks the Login button */}
        {backendReady === null && (
          <div style={{
            background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)',
            borderRadius: '8px', padding: '10px 14px', marginBottom: '1rem',
            fontSize: '0.85rem', color: '#00d4ff', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span>⏳</span> Checking server…
          </div>
        )}
        {backendReady === false && (
          <div style={{
            background: 'rgba(255,193,7,0.1)', border: '1px solid rgba(255,193,7,0.35)',
            borderRadius: '8px', padding: '10px 14px', marginBottom: '1rem',
            fontSize: '0.85rem', color: '#ffc107', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span>⚠️</span> Server is loading AI models — you can still try to login.
          </div>
        )}
        {backendReady === true && (
          <div style={{
            background: 'rgba(0,230,118,0.08)', border: '1px solid rgba(0,230,118,0.25)',
            borderRadius: '8px', padding: '8px 14px', marginBottom: '1rem',
            fontSize: '0.8rem', color: '#00e676', display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <span>✅</span> Server ready
          </div>
        )}

        {error && <div className={styles.errorMsg}>{error}</div>}

        <form onSubmit={handleSubmit} className={styles.authForm}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              className="form-input"
              placeholder="your@email.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
            />
          </div>

          <button
            type="submit"
            className={`btn btn-primary ${styles.authSubmit}`}
            disabled={loading}
            id="login-submit"
          >
            {loading ? 'Logging in…' : 'Login'}
          </button>
        </form>

        <div className={styles.divider}>
          <span>or try demo mode</span>
        </div>

        <div className={styles.demoButtons}>
          <button
            className={`btn btn-outline btn-sm ${styles.demoBtn}`}
            onClick={() => handleDemo('trainee')}
            id="demo-trainee"
          >
            🥋 Demo as Trainee
          </button>
          <button
            className={`btn btn-outline btn-sm ${styles.demoBtn}`}
            onClick={() => handleDemo('coach')}
            id="demo-coach"
          >
            🏆 Demo as Coach
          </button>
        </div>

        <p className={styles.authSwitch}>
          Don&apos;t have an account? <Link href="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}
