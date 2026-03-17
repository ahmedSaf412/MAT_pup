'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import styles from './auth.module.css';

export default function LoginPage() {
  const router = useRouter();
  const { login, demoLogin } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className={styles.divider}>
          <span>or try demo mode</span>
        </div>

        <div className={styles.demoButtons}>
          <button
            className={`btn btn-outline btn-sm ${styles.demoBtn}`}
            onClick={() => handleDemo('trainer')}
            id="demo-trainer"
          >
            🥋 Demo as Trainer
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
