'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import styles from '../login/auth.module.css';

const BELT_LEVELS = ['white', 'yellow', 'orange', 'green', 'blue', 'brown', 'black'];

export default function RegisterPage() {
  const router = useRouter();
  const { register, demoLogin } = useAuth();
  const [role, setRole] = useState('trainee');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    belt_level: 'white',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await register({ ...formData, role });
    if (result.success) {
      router.push(role === 'coach' ? '/coach' : '/dashboard');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleDemo = (demoRole) => {
    demoLogin(demoRole);
    router.push(demoRole === 'coach' ? '/coach' : '/dashboard');
  };

  return (
    <div className={styles.authPage}>
      <div className={styles.authCard}>
        <div className={styles.authHeader}>
          <span className={styles.authIcon}>🥋</span>
          <h1 className={styles.authTitle}>Create Account</h1>
          <p className={styles.authSubtitle}>Join MartialAI and start training</p>
        </div>

        {error && <div className={styles.errorMsg}>{error}</div>}

        {/* Role Selector */}
        <div className={styles.roleSelector}>
          <div
            className={`${styles.roleCard} ${role === 'trainee' ? styles.active : ''}`}
            onClick={() => setRole('trainee')}
            id="role-trainee"
          >
            <span className={styles.roleCardIcon}>🥋</span>
            <div className={styles.roleCardTitle}>Trainee</div>
            <div className={styles.roleCardDesc}>Practice & get AI feedback</div>
          </div>
          <div
            className={`${styles.roleCard} ${role === 'coach' ? styles.active : ''}`}
            onClick={() => setRole('coach')}
            id="role-coach"
          >
            <span className={styles.roleCardIcon}>🏆</span>
            <div className={styles.roleCardTitle}>Coach</div>
            <div className={styles.roleCardDesc}>Monitor & guide trainees</div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className={styles.authForm}>
          <div className="form-group">
            <label className="form-label" htmlFor="reg-name">Full Name</label>
            <input
              id="reg-name"
              type="text"
              className="form-input"
              placeholder="Mohamed Ahmed"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-email">Email</label>
            <input
              id="reg-email"
              type="email"
              className="form-input"
              placeholder="your@email.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-password">Password</label>
            <input
              id="reg-password"
              type="password"
              className="form-input"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
              minLength={6}
            />
          </div>

          {role === 'trainee' && (
            <div className="form-group">
              <label className="form-label" htmlFor="reg-belt">Belt Level</label>
              <select
                id="reg-belt"
                className={styles.beltSelect}
                value={formData.belt_level}
                onChange={(e) => setFormData({ ...formData, belt_level: e.target.value })}
              >
                {BELT_LEVELS.map((b) => (
                  <option key={b} value={b}>
                    {b.charAt(0).toUpperCase() + b.slice(1)} Belt
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="submit"
            className={`btn btn-primary ${styles.authSubmit}`}
            disabled={loading}
            id="register-submit"
          >
            {loading ? 'Creating account...' : `Register as ${role === 'coach' ? 'Coach' : 'Trainee'}`}
          </button>
        </form>

        <div className={styles.divider}>
          <span>or try demo mode</span>
        </div>

        <div className={styles.demoButtons}>
          <button
            className={`btn btn-outline btn-sm ${styles.demoBtn}`}
            onClick={() => handleDemo('trainee')}
            id="demo-trainee-reg"
          >
            🥋 Demo as Trainee
          </button>
          <button
            className={`btn btn-outline btn-sm ${styles.demoBtn}`}
            onClick={() => handleDemo('coach')}
            id="demo-coach-reg"
          >
            🏆 Demo as Coach
          </button>
        </div>

        <p className={styles.authSwitch}>
          Already have an account? <Link href="/login">Login</Link>
        </p>
      </div>
    </div>
  );
}
