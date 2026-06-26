import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV = {
  student: [
    { to: '/student/dashboard', label: 'Dashboard', abbr: 'Da' },
    { to: '/student/chat', label: 'Chat', abbr: 'Ch' },
    { to: '/student/chapter', label: 'Chapter', abbr: 'Cp' },
    { to: '/student/story', label: 'Story', abbr: 'St' },
    { to: '/student/memories', label: 'Memories', abbr: 'Me' },
    { to: '/student/goals', label: 'Goals', abbr: 'Go' },
    { to: '/student/progress', label: 'Progress', abbr: 'Pr' },
    { to: '/student/profile', label: 'Profile', abbr: 'Pf' },
  ],
  teacher: [
    { to: '/teacher/dashboard', label: 'Dashboard', abbr: 'Da' },
    { to: '/teacher/students', label: 'Students', abbr: 'St' },
    { to: '/teacher/goals', label: 'Goals', abbr: 'Go' },
    { to: '/teacher/analytics', label: 'Analytics', abbr: 'An' },
  ],
  admin: [
    { to: '/admin/dashboard', label: 'Dashboard', abbr: 'Da' },
    { to: '/admin/teachers', label: 'Teachers', abbr: 'Te' },
    { to: '/admin/analytics', label: 'Analytics', abbr: 'An' },
    { to: '/admin/settings', label: 'Settings', abbr: 'Se' },
  ],
};

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links = NAV[user?.role] || [];

  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar-collapsed') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', collapsed);
  }, [collapsed]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = (user?.name || user?.email || '?').slice(0, 2).toUpperCase();

  return (
    <aside
      className="bg-sidebar flex flex-col min-h-screen shrink-0 relative transition-all duration-200"
      style={{ width: collapsed ? 64 : 220 }}
    >
      {/* Toggle button */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="absolute -right-3 top-6 z-20 w-6 h-6 rounded-full bg-sidebar border border-white/15 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 transition-all shadow-md"
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          {collapsed
            ? <path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            : <path d="M7 2L3 5l4 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          }
        </svg>
      </button>

      {/* Brand / Logo */}
      <div className={`border-b border-white/8 overflow-hidden ${collapsed ? 'px-3 py-4' : 'px-5 py-5'}`}>
        {collapsed ? (
          <div className="w-9 h-9 rounded-xl bg-white overflow-hidden flex items-center justify-center mx-auto">
            <img src="/logo.png" alt="NeuroLearn" className="w-8 h-8 object-contain" />
          </div>
        ) : (
          <div>
            <div className="bg-white rounded-xl px-3 py-2 mb-3">
              <img src="/logo.png" alt="NeuroLearn" className="h-7 object-contain" />
            </div>
            <div className="text-[10px] uppercase tracking-widest text-white/35 font-semibold pl-0.5">
              {user?.role} portal
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className={`flex flex-col py-3 gap-0.5 flex-1 overflow-hidden ${collapsed ? 'px-2' : 'px-2.5'}`}>
        {links.map(({ to, label, abbr }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg text-[13px] font-medium transition-all duration-100 ${
                collapsed ? 'justify-center px-0 py-2.5' : 'px-3 py-2'
              } ${
                isActive
                  ? 'bg-white/12 text-white'
                  : 'text-white/50 hover:text-white/85 hover:bg-white/6'
              }`
            }
          >
            {collapsed ? (
              <span className="text-[11px] font-bold tracking-wide">{abbr}</span>
            ) : (
              <span>{label}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className={`border-t border-white/8 overflow-hidden ${collapsed ? 'px-2 py-3' : 'px-2.5 py-3'}`}>
        {collapsed ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-sage/30 border border-sage/40 flex items-center justify-center text-white/80 font-bold text-[11px]">
              {initials}
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="w-full flex items-center justify-center py-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/6 transition-all"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M5 12H3a1 1 0 01-1-1V3a1 1 0 011-1h2M9 10l3-3-3-3M12 7H5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-2.5 px-2.5 py-2 mb-1">
              <div className="w-7 h-7 rounded-full bg-sage/30 border border-sage/40 flex items-center justify-center text-white/80 font-bold text-[11px] shrink-0">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="text-[12px] font-semibold text-white/80 truncate leading-tight">{user?.name || user?.email}</p>
                <p className="text-[10px] text-white/30 capitalize">{user?.role}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full text-left px-2.5 py-2 rounded-lg text-[12px] text-white/35 hover:text-white/70 hover:bg-white/6 transition-all flex items-center gap-2"
            >
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <path d="M5 12H3a1 1 0 01-1-1V3a1 1 0 011-1h2M9 10l3-3-3-3M12 7H5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Sign out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
