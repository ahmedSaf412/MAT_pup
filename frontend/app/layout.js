import './globals.css';
import { Inter, Outfit, JetBrains_Mono } from 'next/font/google';
import { AuthProvider } from './context/AuthContext';
import ClientLayout from './ClientLayout';

// ── Fonts loaded at build time (no network round-trip on first compile) ──────
const inter = Inter({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '900'],
  variable: '--font-inter',
  display: 'swap',
});

const outfit = Outfit({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-outfit',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '600'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata = {
  title: 'MartialAI — AI-Powered Martial Arts Trainer',
  description: 'Train smarter with real-time AI pose correction, move classification, and personalized coaching for martial arts.',
  keywords: 'martial arts, AI trainer, karate, pose estimation, move correction',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${outfit.variable} ${jetbrainsMono.variable}`}>
        <AuthProvider>
          <ClientLayout>{children}</ClientLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
