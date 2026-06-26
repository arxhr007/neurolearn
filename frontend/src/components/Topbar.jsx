import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function Topbar({ title }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = (user?.name || user?.email || '?').slice(0, 2).toUpperCase();
  const displayName = user?.name || user?.email || '';

  return (
    <header className="h-14 bg-greige-panel border-b border-greige-border px-5 flex items-center justify-between shrink-0 sticky top-0 z-10">
      {/* Left: page title */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-muted/50 text-[13px] capitalize hidden sm:block">{user?.role}</span>
        <span className="text-muted/30 text-[13px] hidden sm:block">/</span>
        <h1 className="text-[14px] font-semibold text-ink tracking-tight truncate">{title}</h1>
      </div>

      {/* Right: user info */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[12px] text-muted hidden md:block">{displayName}</span>
        <div className="w-8 h-8 rounded-full bg-sage/20 border border-sage/25 flex items-center justify-center text-sage font-bold text-[11px]">
          {initials}
        </div>
        <button
          onClick={handleLogout}
          className="ml-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-greige-border text-[12px] text-muted hover:text-ink hover:bg-greige-accent transition-all"
        >
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
            <path d="M5 12H3a1 1 0 01-1-1V3a1 1 0 011-1h2M9 10l3-3-3-3M12 7H5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Sign out
        </button>
      </div>
    </header>
  );
}
