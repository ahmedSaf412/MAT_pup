'use client';

import styles from './CorrectionPanel.module.css';

const SEVERITY_CONFIG = {
  error: { icon: '🔴', label: 'Critical', color: 'var(--accent-red)' },
  warning: { icon: '🟡', label: 'Warning', color: 'var(--accent-yellow)' },
  info: { icon: '🟢', label: 'Good', color: 'var(--accent-green)' },
};

export default function CorrectionPanel({
  moveName = '',
  confidence = 0,
  corrections = [],
  isCoach = false,
  jointAngles = null,
}) {
  const confidencePercent = Math.round(confidence * 100);

  return (
    <div className={styles.panel}>
      {/* Move Classification */}
      <div className={styles.moveSection}>
        <div className={styles.sectionLabel}>Detected Move</div>
        <div className={styles.moveName}>
          {moveName || 'Waiting for pose...'}
        </div>
        {moveName && (
          <div className={styles.confidenceBar}>
            <div className={styles.confidenceLabel}>
              Confidence: <span className={styles.confidenceValue}>{confidencePercent}%</span>
            </div>
            <div className={styles.barTrack}>
              <div
                className={styles.barFill}
                style={{
                  width: `${confidencePercent}%`,
                  background:
                    confidencePercent >= 80
                      ? 'var(--accent-green)'
                      : confidencePercent >= 60
                      ? 'var(--accent-yellow)'
                      : 'var(--accent-red)',
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Corrections List */}
      <div className={styles.correctionsSection}>
        <div className={styles.sectionLabel}>
          {isCoach ? 'Detailed Analysis' : 'Corrections'}
        </div>
        {corrections.length === 0 ? (
          <div className={styles.noCorrections}>
            {moveName ? '✅ Perfect form! Keep it up!' : 'Start practicing to see feedback'}
          </div>
        ) : (
          <div className={styles.correctionsList}>
            {corrections.map((c, i) => {
              const config = SEVERITY_CONFIG[c.severity] || SEVERITY_CONFIG.info;
              return (
                <div key={i} className={styles.correctionItem}>
                  <div className={styles.correctionHeader}>
                    <span>{config.icon}</span>
                    <span className={styles.jointName}>
                      {c.joint?.replace('_', ' ')}
                    </span>
                    <span
                      className={styles.severityBadge}
                      style={{ color: config.color }}
                    >
                      {config.label}
                    </span>
                  </div>
                  <div className={styles.correctionMsg}>{c.message}</div>

                  {/* Coach-specific: show angle data */}
                  {isCoach && c.angle_current !== undefined && (
                    <div className={styles.angleData}>
                      <span>Current: {c.angle_current?.toFixed(1)}°</span>
                      <span>Target: {c.angle_target?.toFixed(1)}°</span>
                      <span className={styles.angleDiff}>
                        Δ {Math.abs(c.angle_current - c.angle_target).toFixed(1)}°
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Coach-specific: Joint Angles Table */}
      {isCoach && jointAngles && (
        <div className={styles.anglesSection}>
          <div className={styles.sectionLabel}>Joint Angles</div>
          <div className={styles.anglesGrid}>
            {Object.entries(jointAngles).map(([joint, angle]) => (
              <div key={joint} className={styles.angleItem}>
                <span className={styles.angleJoint}>{joint.replace('_', ' ')}</span>
                <span className={styles.angleValue}>{angle.toFixed(1)}°</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
