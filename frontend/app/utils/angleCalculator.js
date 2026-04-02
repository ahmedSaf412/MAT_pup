// frontend/app/utils/angleCalculator.js
const calculateAngle = (a, b, c) => {
  const ba = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
  const bc = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };
  const dot = ba.x*bc.x + ba.y*bc.y + ba.z*bc.z;
  const magBA = Math.sqrt(ba.x**2 + ba.y**2 + ba.z**2);
  const magBC = Math.sqrt(bc.x**2 + bc.y**2 + bc.z**2);
  if (magBA * magBC === 0) return 0;
  let angle = Math.acos(dot / (magBA * magBC)) * (180 / Math.PI);
  return Math.max(0, Math.min(1, angle / 180));
};

export const extract14Angles = (landmarks) => {
  if (!landmarks || landmarks.length < 33) return Array(14).fill(0);
  return [
    calculateAngle(landmarks[11], landmarks[13], landmarks[15]), // R elbow
    calculateAngle(landmarks[12], landmarks[14], landmarks[16]), // L elbow
    calculateAngle(landmarks[23], landmarks[25], landmarks[27]), // R knee
    calculateAngle(landmarks[24], landmarks[26], landmarks[28]), // L knee
    calculateAngle(landmarks[11], landmarks[23], landmarks[25]), // R hip
    calculateAngle(landmarks[12], landmarks[24], landmarks[26]), // L hip
    calculateAngle(landmarks[23], landmarks[11], landmarks[13]), // R shoulder
    calculateAngle(landmarks[24], landmarks[12], landmarks[14]), // L shoulder
    calculateAngle(landmarks[0], landmarks[11], landmarks[12]),  // Shoulder align
    calculateAngle(landmarks[11], landmarks[12], landmarks[24]), // Torso twist
    calculateAngle(landmarks[25], landmarks[27], landmarks[31]), // R ankle
    calculateAngle(landmarks[26], landmarks[28], landmarks[32]), // L ankle
    calculateAngle(landmarks[13], landmarks[15], landmarks[17]), // R wrist
    calculateAngle(landmarks[14], landmarks[16], landmarks[18]), // L wrist
  ].map(a => Math.max(0, Math.min(1, a)));
};