'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import styles from './profile.module.css';

const BELT_LEVELS = ['white', 'yellow', 'orange', 'green', 'blue', 'brown', 'black'];

export default function ProfilePage() {
  const { user, isAuthenticated, updateUser } = useAuth();
  const router = useRouter();
  const [formData, setFormData] = useState({ full_name: '', belt_level: 'white' });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (user) {
      setFormData({
        full_name: user.full_name || '',
        belt_level: user.belt_level || 'white',
      });
    }
  }, [user]);

  const handleSave = (e) => {
    e.preventDefault();
    updateUser(formData);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  if (!user) return <div className="loading-container"><div className="spinner" /></div>;

  return (
    <div className={styles.profilePage}>
      <div className="container">
        <h1 className={styles.title}>⚙️ Profile Settings</h1>

        <div className={styles.profileLayout}>
          {/* Profile Card */}
          <div className={`glass-card ${styles.profileCard}`}>
            <div className={styles.avatarLarge}>
              {user.full_name?.charAt(0) || '?'}
            </div>
            <h2 className={styles.profileName}>{user.full_name}</h2>
            <p className={styles.profileEmail}>{user.email}</p>
            <div className={styles.profileBadges}>
              <span className="badge badge-blue">
                {user.role === 'coach' ? '🏆 Coach' : '🥋 Trainer'}
              </span>
              {user.role !== 'coach' && (
                <span className="badge badge-orange">
                  {(user.belt_level || 'white').charAt(0).toUpperCase() + (user.belt_level || 'white').slice(1)} Belt
                </span>
              )}
            </div>
            <div className={styles.profileMeta}>
              <div className={styles.metaItem}>
                <span className={styles.metaLabel}>Member Since</span>
                <span className={styles.metaValue}>
                  {new Date(user.created_at || Date.now()).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>

          {/* Edit Form */}
          <div className={`glass-card ${styles.editCard}`}>
            <h2 className={styles.editTitle}>Edit Profile</h2>

            {saved && (
              <div className={styles.savedMsg}>✅ Profile updated successfully!</div>
            )}

            <form onSubmit={handleSave}>
              <div className="form-group">
                <label className="form-label" htmlFor="profile-name">Full Name</label>
                <input
                  id="profile-name"
                  type="text"
                  className="form-input"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  required
                />
              </div>

              {user.role !== 'coach' && (
                <div className="form-group">
                  <label className="form-label" htmlFor="profile-belt">Belt Level</label>
                  <select
                    id="profile-belt"
                    className="form-input"
                    value={formData.belt_level}
                    onChange={(e) => setFormData({ ...formData, belt_level: e.target.value })}
                    style={{ background: 'var(--bg-glass)' }}
                  >
                    {BELT_LEVELS.map((b) => (
                      <option key={b} value={b} style={{ background: 'var(--bg-secondary)' }}>
                        {b.charAt(0).toUpperCase() + b.slice(1)} Belt
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="form-group">
                <label className="form-label" htmlFor="profile-email">Email</label>
                <input
                  id="profile-email"
                  type="email"
                  className="form-input"
                  value={user.email}
                  disabled
                  style={{ opacity: 0.5 }}
                />
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} id="save-profile-btn">
                Save Changes
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
