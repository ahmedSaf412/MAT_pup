'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '../context/AuthContext';
import styles from './Navbar.module.css';

export default function Navbar() {
  const { user, isAuthenticated, isCoach, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        {/* Logo */}
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>🥋</span>
          <span className={styles.logoText}>
            Martial<span className={styles.logoAccent}>AI</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <div className={styles.navLinks}>
          {isAuthenticated ? (
            <>
              {isCoach ? (
                <>
                  <Link href="/coach" className={styles.navLink}>
                    <span className={styles.navIcon}>📊</span> Dashboard
                  </Link>
                  <Link href="/coach" className={styles.navLink}>
                    <span className={styles.navIcon}>👥</span> Trainees
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/dashboard" className={styles.navLink}>
                    <span className={styles.navIcon}>📊</span> Dashboard
                  </Link>
                  <Link href="/train" className={styles.navLink}>
                    <span className={styles.navIcon}>🎯</span> Train
                  </Link>
                  <Link href="/moves" className={styles.navLink}>
                    <span className={styles.navIcon}>📚</span> Moves
                  </Link>
                </>
              )}

              {/* User Menu */}
              <div className={styles.userMenu}>
                <button
                  className={styles.userButton}
                  onClick={() => setMenuOpen(!menuOpen)}
                  id="user-menu-button"
                >
                  <div className={styles.avatar}>
                    {user?.full_name?.charAt(0) || '?'}
                  </div>
                  <span className={styles.userName}>{user?.full_name}</span>
                  <span className={styles.chevron}>▾</span>
                </button>

                {menuOpen && (
                  <div className={styles.dropdown}>
                    <div className={styles.dropdownHeader}>
                      <div className={styles.dropdownName}>{user?.full_name}</div>
                      <div className={styles.dropdownRole}>
                        {isCoach ? '🏆 Coach' : `🥋 ${user?.belt_level || 'White'} Belt`}
                      </div>
                    </div>
                    <div className={styles.dropdownDivider} />
                    <Link href="/profile" className={styles.dropdownItem} onClick={() => setMenuOpen(false)}>
                      ⚙️ Profile
                    </Link>
                    <button className={styles.dropdownItem} onClick={logout} id="logout-button">
                      🚪 Logout
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <Link href="/login" className={`btn btn-ghost ${styles.navBtn}`}>
                Login
              </Link>
              <Link href="/register" className={`btn btn-primary btn-sm ${styles.navBtn}`}>
                Get Started
              </Link>
            </>
          )}
        </div>

        {/* Mobile Hamburger */}
        <button
          className={styles.hamburger}
          onClick={() => setMenuOpen(!menuOpen)}
          id="mobile-menu-button"
          aria-label="Toggle menu"
        >
          <span className={`${styles.hamburgerLine} ${menuOpen ? styles.open : ''}`} />
          <span className={`${styles.hamburgerLine} ${menuOpen ? styles.open : ''}`} />
          <span className={`${styles.hamburgerLine} ${menuOpen ? styles.open : ''}`} />
        </button>
      </div>
    </nav>
  );
}
