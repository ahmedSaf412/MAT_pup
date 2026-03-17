'use client';

import Navbar from './components/Navbar';
import ChatBot from './components/ChatBot';
import { useAuth } from './context/AuthContext';

export default function ClientLayout({ children }) {
  const { isAuthenticated } = useAuth();

  return (
    <>
      <Navbar />
      <main style={{ paddingTop: 'var(--navbar-height)' }}>
        {children}
      </main>
      {isAuthenticated && <ChatBot />}
    </>
  );
}
