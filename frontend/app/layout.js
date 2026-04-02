import './globals.css';
import { AuthProvider } from './context/AuthContext';
import ClientLayout from './ClientLayout';

export const metadata = {
  title: 'MartialAI — AI-Powered Martial Arts Trainer',
  description: 'Train smarter with real-time AI pose correction, move classification, and personalized coaching for martial arts.',
  keywords: 'martial arts, AI trainer, karate, pose estimation, move correction',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AuthProvider>
          <ClientLayout>{children}</ClientLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
