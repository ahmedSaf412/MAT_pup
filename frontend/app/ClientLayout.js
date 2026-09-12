'use client';

import Navbar from './components/Navbar';
import ChatBot from './components/ChatBot';
import { useAuth } from './context/AuthContext';
import { PoseProvider } from './context/PoseContext';

export default function ClientLayout({ children }) {
  const { isAuthenticated } = useAuth();

  return (
    <PoseProvider>
      <Navbar />
      <main style={{ paddingTop: 'var(--navbar-height)' }}>
        {children}
      </main>
      {isAuthenticated && <ChatBot />}
    </PoseProvider>
  );
}

