import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Document Intelligence Platform',
  description: 'AI-powered document management',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
