// frontend/app/page.js
'use client';

import Link from 'next/link';
import styles from './landing.module.css';

const FEATURES = [
  {
    icon: '🤖',
    title: 'AI Move Classification',
    desc: 'Real-time classification of martial arts moves using deep learning LSTM models trained on thousands of sequences.',
    color: 'var(--accent-blue)',
  },
  {
    icon: '📐',
    title: 'Pose Correction',
    desc: 'Instant feedback on your form — joint angles compared against ideal references with visual highlights.',
    color: 'var(--accent-orange)',
  },
  {
    icon: '📹',
    title: 'Webcam Skeleton Overlay',
    desc: 'See your pose skeleton in real-time with MediaPipe, highlighting joints that need correction in red.',
    color: 'var(--accent-green)',
  },
  {
    icon: '🏆',
    title: 'Coach Dashboard',
    desc: 'Coaches monitor trainees progress, view session history, analyze detailed correction patterns.',
    color: 'var(--accent-purple)',
  },
  {
    icon: '💬',
    title: 'AI Chatbot Assistant',
    desc: 'RAG-powered assistant answers technique questions, explains corrections, and suggests training plans.',
    color: 'var(--accent-yellow)',
  },
  {
    icon: '📊',
    title: 'Progress Tracking',
    desc: 'Charts and analytics track your improvement over time — scores, accuracy per move, and training streaks.',
    color: 'var(--accent-red)',
  },
];

const STEPS = [
  { num: '01', title: 'Stand in front of camera', desc: 'Position yourself so the webcam captures your full body' },
  { num: '02', title: 'Select a move to practice', desc: 'Choose from the move library or let AI classify freely' },
  { num: '03', title: 'Perform the move', desc: 'The AI detects your pose and classifies the move in real-time' },
  { num: '04', title: 'Get instant feedback', desc: 'See corrections, improve, and track your progress' },
];

export default function LandingPage() {
  return (
    <div className={styles.landing}>
      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.heroBadge}>
            <span className={styles.badgePulse} />
            AI-Powered Training
          </div>
          <h1 className={styles.heroTitle}>
            Master Martial Arts with{' '}
            <span className={styles.gradientText}>Artificial Intelligence</span>
          </h1>
          <p className={styles.heroSubtitle}>
            Real-time pose correction, AI move classification, and personalized coaching — 
            your virtual martial arts sensei powered by deep learning.
          </p>
          <div className={styles.heroCTA}>
            <Link href="/register" className="btn btn-primary btn-lg" id="hero-register-btn">
              🥋 Start Training Free
            </Link>
            <Link href="/login" className="btn btn-outline btn-lg" id="hero-login-btn">
              Login
            </Link>
          </div>
          <div className={styles.heroStats}>
            <div className={styles.heroStat}>
              <span className={styles.statNum}>33</span>
              <span className={styles.statLabel}>Body Landmarks</span>
            </div>
            <div className={styles.heroStat}>
              <span className={styles.statNum}>30+</span>
              <span className={styles.statLabel}>FPS Detection</span>
            </div>
            <div className={styles.heroStat}>
              <span className={styles.statNum}>97%</span>
              <span className={styles.statLabel}>Classification Accuracy</span>
            </div>
          </div>
        </div>

        {/* Hero Visual */}
        <div className={styles.heroVisual}>
          <div className={styles.heroCard}>
            <div className={styles.skeletonDemo}>
              <div className={styles.skeletonFigure}>
                {/* Stylized martial arts figure */}
                <svg viewBox="0 0 200 300" className={styles.skeletonSvg}>
                  {/* Head */}
                  <circle cx="100" cy="30" r="15" fill="none" stroke="#00D4FF" strokeWidth="2" />
                  {/* Torso */}
                  <line x1="100" y1="45" x2="100" y2="140" stroke="#00D4FF" strokeWidth="2" />
                  {/* Left arm (guard up) */}
                  <line x1="100" y1="65" x2="60" y2="85" stroke="#00D4FF" strokeWidth="2" />
                  <line x1="60" y1="85" x2="65" y2="50" stroke="#00D4FF" strokeWidth="2" />
                  {/* Right arm (punching) */}
                  <line x1="100" y1="65" x2="140" y2="75" stroke="#FF6B35" strokeWidth="2.5" />
                  <line x1="140" y1="75" x2="180" y2="65" stroke="#FF6B35" strokeWidth="2.5" />
                  {/* Right arm glow */}
                  <circle cx="180" cy="65" r="5" fill="#FF6B35" opacity="0.6">
                    <animate attributeName="r" values="5;8;5" dur="1.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0.2;0.6" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                  {/* Hips */}
                  <line x1="75" y1="140" x2="125" y2="140" stroke="#00D4FF" strokeWidth="2" />
                  {/* Left leg (stance) */}
                  <line x1="75" y1="140" x2="60" y2="210" stroke="#00D4FF" strokeWidth="2" />
                  <line x1="60" y1="210" x2="55" y2="280" stroke="#00D4FF" strokeWidth="2" />
                  {/* Right leg (kick) */}
                  <line x1="125" y1="140" x2="150" y2="190" stroke="#00E676" strokeWidth="2.5" />
                  <line x1="150" y1="190" x2="185" y2="175" stroke="#00E676" strokeWidth="2.5" />
                  {/* Joint dots */}
                  <circle cx="100" cy="65" r="4" fill="#00D4FF" />
                  <circle cx="60" cy="85" r="4" fill="#00D4FF" />
                  <circle cx="65" cy="50" r="4" fill="#00D4FF" />
                  <circle cx="140" cy="75" r="4" fill="#FF6B35" />
                  <circle cx="75" cy="140" r="4" fill="#00D4FF" />
                  <circle cx="125" cy="140" r="4" fill="#00D4FF" />
                  <circle cx="60" cy="210" r="4" fill="#00D4FF" />
                  <circle cx="150" cy="190" r="4" fill="#00E676" />
                </svg>
              </div>
              <div className={styles.correctionBubble}>
                <span className={styles.bubbleIcon}>⚡</span>
                <span>Front Kick — 92%</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className={styles.features} id="features">
        <div className="container">
          <h2 className={styles.sectionTitle}>
            Everything You Need to <span className={styles.gradientText}>Train Smarter</span>
          </h2>
          <p className={styles.sectionSubtitle}>
            Powered by MediaPipe, LSTM deep learning, and real-time WebSocket streaming
          </p>
          <div className={styles.featureGrid}>
            {FEATURES.map((f, i) => (
              <div key={i} className={`glass-card ${styles.featureCard} animate-fade-in-up delay-${i + 1}`}>
                <div className={styles.featureIcon} style={{ color: f.color }}>{f.icon}</div>
                <h3 className={styles.featureTitle}>{f.title}</h3>
                <p className={styles.featureDesc}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className={styles.howItWorks}>
        <div className="container">
          <h2 className={styles.sectionTitle}>
            How It <span className={styles.gradientText}>Works</span>
          </h2>
          <div className={styles.stepsGrid}>
            {STEPS.map((s, i) => (
              <div key={i} className={styles.stepCard}>
                <div className={styles.stepNum}>{s.num}</div>
                <h3 className={styles.stepTitle}>{s.title}</h3>
                <p className={styles.stepDesc}>{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className={styles.cta}>
        <div className="container">
          <div className={styles.ctaCard}>
            <h2 className={styles.ctaTitle}>Ready to Train Like Never Before?</h2>
            <p className={styles.ctaDesc}>
              Join as a trainer or coach. Get AI-powered real-time feedback on every move.
            </p>
            <div className={styles.ctaButtons}>
              <Link href="/register" className="btn btn-primary btn-lg" id="cta-register-btn">
                🥋 Start as Trainer
              </Link>
              <Link href="/register" className="btn btn-secondary btn-lg" id="cta-coach-btn">
                🏆 Join as Coach
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <div className={styles.footerContent}>
            <div className={styles.footerLogo}>
              <span>🥋</span> Martial<span className={styles.gradientText}>AI</span>
            </div>
            <p className={styles.footerText}>
              AI-Powered Martial Arts Training Platform — Built with Next.js, MediaPipe & LSTM
            </p>
            <p className={styles.footerCopy}>
              © 2026 MartialAI. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
