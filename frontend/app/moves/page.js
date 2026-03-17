'use client';

import { useState } from 'react';
import styles from './moves.module.css';

const MOVES_DATA = [
  {
    id: 1, name: 'Front Kick', japanese: 'Mae Geri', art: 'Karate', belt: 'white',
    description: 'A fundamental kick executed by lifting the knee and snapping the foot forward. Strike with the ball of the foot.',
    tips: ['Chamber knee to waist height first', 'Strike with ball of foot', 'Retract quickly after extension', 'Keep guard hands up'],
    keyJoints: ['knee', 'hip', 'ankle'],
  },
  {
    id: 2, name: 'Roundhouse Kick', japanese: 'Mawashi Geri', art: 'Karate', belt: 'yellow',
    description: 'A circular kick that comes from the side. Pivot on the support foot and rotate hips fully through the kick.',
    tips: ['Pivot support foot — heel toward target', 'Rotate hips fully', 'Keep guard up throughout', 'Snap the kick, don\'t push'],
    keyJoints: ['hip', 'knee', 'ankle', 'support_foot'],
  },
  {
    id: 3, name: 'Side Kick', japanese: 'Yoko Geri', art: 'Karate', belt: 'yellow',
    description: 'A powerful linear kick to the side. Chamber the knee, then thrust the heel outward while leaning the body away.',
    tips: ['Chamber knee high', 'Strike with the heel or blade of foot', 'Lean torso away for balance', 'Lock the knee at full extension'],
    keyJoints: ['hip', 'knee', 'ankle'],
  },
  {
    id: 4, name: 'Reverse Punch', japanese: 'Gyaku Zuki', art: 'Karate', belt: 'white',
    description: 'The most powerful hand technique in karate. The rear hand punches forward while rotating the hip.',
    tips: ['Rotate hips into the punch', 'Rotate fist at the end (palm down)', 'Keep other hand in guard', 'Drive from the rear leg'],
    keyJoints: ['shoulder', 'elbow', 'wrist', 'hip'],
  },
  {
    id: 5, name: 'Rising Block', japanese: 'Age Uke', art: 'Karate', belt: 'white',
    description: 'An overhead defensive technique to block attacks coming downward. The forearm rises up to deflect.',
    tips: ['Start from opposite hip', 'Forearm ends above and in front of head', 'Rotate forearm outward', 'Keep other hand pulled to hip (hikite)'],
    keyJoints: ['shoulder', 'elbow', 'wrist'],
  },
  {
    id: 6, name: 'Front Stance', japanese: 'Zenkutsu Dachi', art: 'Karate', belt: 'white',
    description: 'The fundamental forward-weighted stance. Strong foundation for most karate techniques.',
    tips: ['Front knee bent over toes', 'Back leg straight', 'Feet shoulder-width apart', 'Weight 60% front, 40% back'],
    keyJoints: ['hip', 'knee', 'ankle'],
  },
  {
    id: 7, name: 'Knife Hand Strike', japanese: 'Shuto Uchi', art: 'Karate', belt: 'green',
    description: 'An open-hand strike using the edge of the hand (knife edge). Used for strikes to the neck, ribs, or collarbone.',
    tips: ['Keep fingers tight together', 'Strike with the meaty edge of hand', 'Pull other hand to ear level', 'Rotate hips into strike'],
    keyJoints: ['shoulder', 'elbow', 'wrist'],
  },
  {
    id: 8, name: 'Back Kick', japanese: 'Ushiro Geri', art: 'Karate', belt: 'blue',
    description: 'A powerful rear kick. Turn and look over your shoulder, then thrust the heel backward at the target.',
    tips: ['Look before you kick', 'Thrust heel straight back', 'Keep body tight and compact', 'Retract immediately after'],
    keyJoints: ['hip', 'knee', 'ankle'],
  },
];

const BELT_COLORS = {
  white: '#FFFFFF', yellow: '#FFD740', orange: '#FF9100',
  green: '#00E676', blue: '#448AFF', brown: '#8D6E63', black: '#424242',
};

export default function MovesPage() {
  const [selectedMove, setSelectedMove] = useState(null);
  const [filterArt, setFilterArt] = useState('all');
  const [filterBelt, setFilterBelt] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredMoves = MOVES_DATA.filter((m) => {
    if (filterArt !== 'all' && m.art.toLowerCase() !== filterArt) return false;
    if (filterBelt !== 'all' && m.belt !== filterBelt) return false;
    if (searchTerm && !m.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  return (
    <div className={styles.movesPage}>
      <div className="container">
        <div className={styles.header}>
          <h1 className={styles.title}>📚 Move Library</h1>
          <p className={styles.subtitle}>Browse techniques, learn proper form, and practice with AI feedback</p>
        </div>

        {/* Filters */}
        <div className={styles.filters}>
          <input
            type="text"
            className="form-input"
            placeholder="Search moves..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            id="move-search"
            style={{ maxWidth: 260 }}
          />
          <select
            className={styles.filterSelect}
            value={filterBelt}
            onChange={(e) => setFilterBelt(e.target.value)}
            id="belt-filter"
          >
            <option value="all">All Belts</option>
            <option value="white">White Belt</option>
            <option value="yellow">Yellow Belt</option>
            <option value="green">Green Belt</option>
            <option value="blue">Blue Belt</option>
          </select>
        </div>

        {/* Moves Grid */}
        <div className={styles.movesGrid}>
          {filteredMoves.map((move) => (
            <div
              key={move.id}
              className={`glass-card ${styles.moveCard}`}
              onClick={() => setSelectedMove(move)}
              id={`move-card-${move.id}`}
            >
              <div className={styles.moveCardHeader}>
                <div className={styles.moveEmoji}>🥋</div>
                <span
                  className={styles.beltDot}
                  style={{ background: BELT_COLORS[move.belt] }}
                  title={`${move.belt} belt`}
                />
              </div>
              <h3 className={styles.moveCardName}>{move.name}</h3>
              <p className={styles.moveCardJapanese}>{move.japanese}</p>
              <p className={styles.moveCardDesc}>{move.description.slice(0, 80)}...</p>
              <div className={styles.moveCardFooter}>
                <span className="badge badge-blue">{move.art}</span>
                <span className={styles.moveCardLink}>View Details →</span>
              </div>
            </div>
          ))}
        </div>

        {/* Move Detail Modal */}
        {selectedMove && (
          <div className={styles.modalOverlay} onClick={() => setSelectedMove(null)}>
            <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
              <button className={styles.modalClose} onClick={() => setSelectedMove(null)} id="close-move-modal">✕</button>

              <div className={styles.modalHeader}>
                <div>
                  <h2 className={styles.modalTitle}>{selectedMove.name}</h2>
                  <p className={styles.modalJapanese}>{selectedMove.japanese}</p>
                </div>
                <div className={styles.modalBadges}>
                  <span className="badge badge-blue">{selectedMove.art}</span>
                  <span
                    className="badge"
                    style={{
                      background: `${BELT_COLORS[selectedMove.belt]}22`,
                      color: BELT_COLORS[selectedMove.belt],
                    }}
                  >
                    {selectedMove.belt} belt
                  </span>
                </div>
              </div>

              {/* Video placeholder */}
              <div className={styles.videoPreview}>
                <div className={styles.videoPlaceholder}>
                  <span className={styles.playIcon}>▶</span>
                  <p>Reference Video</p>
                  <p className={styles.videoHint}>Connect to move catalog API for video playback</p>
                </div>
              </div>

              <div className={styles.modalBody}>
                <div className={styles.modalSection}>
                  <h3>Description</h3>
                  <p>{selectedMove.description}</p>
                </div>

                <div className={styles.modalSection}>
                  <h3>Key Tips</h3>
                  <ul className={styles.tipsList}>
                    {selectedMove.tips.map((tip, i) => (
                      <li key={i}>
                        <span className={styles.tipIcon}>💡</span>
                        {tip}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.modalSection}>
                  <h3>Key Joints Analyzed</h3>
                  <div className={styles.jointTags}>
                    {selectedMove.keyJoints.map((j) => (
                      <span key={j} className="badge badge-orange">{j}</span>
                    ))}
                  </div>
                </div>
              </div>

              <div className={styles.modalFooter}>
                <a href="/train" className="btn btn-primary" id="practice-move-btn">
                  🎯 Practice This Move
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
