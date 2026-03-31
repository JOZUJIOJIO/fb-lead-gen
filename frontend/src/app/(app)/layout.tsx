import Sidebar from '@/components/Sidebar';
import HealthIndicator from '@/components/HealthIndicator';

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Sidebar />
      <main className="ml-16 min-h-screen lg:ml-56">
        <div className="mx-auto max-w-6xl px-6 py-8">
          {/* Top bar with health indicator */}
          <div className="flex justify-end mb-4">
            <HealthIndicator />
          </div>
          {children}
        </div>
      </main>
    </>
  );
}
