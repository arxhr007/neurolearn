import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV = {
  student: [
    { to: '/student/dashboard', label: 'Dashboard' },
    { to: '/student/chat', label: 'Chat' },
    { to: '/student/chapter', label: 'Chapter' },
    { to: '/student/story', label: 'Story' },
    { to: '/student/memories', label: 'Memories' },
    { to: '/student/goals', label: 'Goals' },
    { to: '/student/progress', label: 'Progress' },
    { to: '/student/profile', label: 'Profile' },
  ],
  teacher: [
    { to: '/teacher/dashboard', label: 'Dashboard' },
    { to: '/teacher/students', label: 'Students' },
    { to: '/teacher/goals', label: 'Goals' },
    { to: '/teacher/analytics', label: 'Analytics' },
  ],
  admin: [
    { to: '/admin/dashboard', label: 'Dashboard' },
    { to: '/admin/teachers', label: 'Teachers' },
    { to: '/admin/analytics', label: 'Analytics' },
    { to: '/admin/settings', label: 'Settings' },
  ],
};

export default function Navbar({ onToggleHistory }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links = NAV[user?.role] || [];
  const initials = (user?.name || user?.email || '?').slice(0, 2).toUpperCase();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <nav
      className="fixed z-50 flex items-center shadow-glass"
      style={{
        top: 12,
        left: 16,
        right: 16,
        height: 54,
        background: 'rgba(249,248,246,0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(220,216,208,0.75)',
        borderRadius: '14px',
        padding: '0 14px',
      }}
    >
      {/* Left: history toggle */}
      <div className="flex items-center shrink-0" style={{ width: 140 }}>
        <button
          onClick={onToggleHistory}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-muted hover:text-ink hover:bg-greige-accent transition-colors text-[13px] font-medium"
          title="Toggle history"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
            <rect x="2" y="3.5" width="12" height="1.6" rx="0.8" fill="currentColor"/>
            <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" fill="currentColor"/>
            <rect x="2" y="10.9" width="10" height="1.6" rx="0.8" fill="currentColor"/>
          </svg>
          History
        </button>
      </div>

      {/* Center: nav links */}
      <div className="flex items-center justify-center gap-1 flex-1 overflow-x-auto scrollbar-none">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `shrink-0 px-3.5 py-2 rounded-lg text-[14px] font-medium transition-all duration-100 whitespace-nowrap ${
                isActive
                  ? 'bg-sage/12 text-sage-dark font-semibold'
                  : 'text-muted hover:text-ink hover:bg-greige-accent'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>

      {/* Right: user + sign out */}
      <div className="flex items-center gap-2 shrink-0 justify-end" style={{ width: 140 }}>
        <div className="w-7 h-7 rounded-full bg-sage/15 border border-sage/25 flex items-center justify-center text-sage font-bold text-[11px]">
          {initials}
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-greige-border text-[12px] text-muted hover:text-ink hover:bg-greige-accent transition-all"
        >
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
            <path d="M5 12H3a1 1 0 01-1-1V3a1 1 0 011-1h2M9 10l3-3-3-3M12 7H5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Sign out
        </button>
      </div>
    </nav>
  );
}
