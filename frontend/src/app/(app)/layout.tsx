import { Sidebar } from '@/components/layout/Sidebar';
import { AuthGuard } from '@/components/layout/AuthGuard';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden bg-[#0a0f1e]">
        <Sidebar />
        <main className="flex-1 overflow-y-auto scrollbar-thin mesh-bg">{children}</main>
      </div>
    </AuthGuard>
  );
}
