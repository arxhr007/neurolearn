import { useState } from 'react';
import Navbar from './Navbar';
import HistoryPanel from './HistoryPanel';

export default function AppShell({ title, children }) {
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <div className="min-h-screen bg-greige-bg font-sans">
      <Navbar onToggleHistory={() => setHistoryOpen(o => !o)} />
      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} />
      <main
        className="flex flex-col gap-5"
        style={{ paddingTop: 76, paddingLeft: 24, paddingRight: 24, paddingBottom: 32, minHeight: '100vh' }}
      >
        {/* Page title */}
        <div className="flex items-center gap-2">
          <h1 className="text-[20px] font-bold text-ink tracking-tight">{title}</h1>
        </div>
        {children}
      </main>
    </div>
  );
}
