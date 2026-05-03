'use client';
import { createContext, useContext, useState } from 'react';

const PoseContext = createContext();

export function PoseProvider({ children }) {
  const [currentMoveId,        setCurrentMoveId]        = useState(null);
  const [currentLandmarks,     setCurrentLandmarks]     = useState(null);   // single frame (legacy)
  const [currentLandmarkFrames, setCurrentLandmarkFrames] = useState(null); // all 30 frames for DTW

  return (
    <PoseContext.Provider value={{
      currentMoveId,        setCurrentMoveId,
      currentLandmarks,     setCurrentLandmarks,
      currentLandmarkFrames, setCurrentLandmarkFrames,
    }}>
      {children}
    </PoseContext.Provider>
  );
}

export function usePose() {
  return useContext(PoseContext);
}
