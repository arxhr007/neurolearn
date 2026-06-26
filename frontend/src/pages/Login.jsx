import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ROLES = ['student', 'teacher', 'admin'];
const HOME = { student: '/student/dashboard', teacher: '/teacher/dashboard', admin: '/admin/dashboard' };

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [role, setRole] = useState('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const res = await login(email, password, role);
    setLoading(false);
    if (res.ok) {
      navigate(HOME[res.user.role] || '/');
    } else {
      setError(res.error);
    }
  };

  return (
    <div className="min-h-screen flex font-sans">
      {/* Left brand panel */}
      <aside className="hidden md:flex flex-col justify-between px-12 py-12 bg-sidebar text-white w-[42%] shrink-0">
        <div>
          {/* Logo */}
          <div className="bg-white rounded-2xl px-5 py-3 inline-block mb-10">
            <img src="/logo.png" alt="NeuroLearn" className="h-9 object-contain" />
          </div>

          <h1 className="text-3xl font-bold leading-tight mb-4 text-white/95">
            Adaptive AI tutoring for every learner
          </h1>
          <p className="text-white/55 text-[15px] leading-relaxed mb-10">
            Personalised stories and interactive lessons in Malayalam, designed for neurodivergent learners.
          </p>

          <ul className="space-y-4">
            {[
              'Personalised to each student profile',
              'Story-based learning in Malayalam',
              'Real-time mastery tracking',
              'Teacher and admin dashboards',
            ].map(f => (
              <li key={f} className="flex items-center gap-3 text-white/70 text-sm">
                <span className="w-5 h-5 rounded-full bg-sage/60 border border-sage flex items-center justify-center shrink-0">
                  <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                    <path d="M1 4l2.5 2.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </span>
                {f}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-white/20 text-xs">NeuroLearn — AI-powered inclusive education</p>
      </aside>

      {/* Right form panel */}
      <main className="flex-1 flex items-center justify-center bg-greige-bg p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="md:hidden mb-8 flex justify-center">
            <div className="bg-white rounded-2xl px-5 py-3 shadow-card">
              <img src="/logo.png" alt="NeuroLearn" className="h-8 object-contain" />
            </div>
          </div>

          {/* Role tabs */}
          <div className="flex gap-1 bg-greige-accent rounded-xl p-1 mb-5">
            {ROLES.map(r => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`flex-1 py-2 rounded-lg text-[13px] font-semibold capitalize transition-all ${
                  role === r ? 'bg-sage text-white shadow-sm' : 'text-muted hover:text-ink'
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Form card */}
          <div className="bg-greige-panel rounded-2xl border border-greige-border shadow-card p-7">
            <h2 className="text-[18px] font-bold text-ink mb-0.5">Welcome back</h2>
            <p className="text-sm text-muted mb-5">Sign in as <span className="font-medium text-ink capitalize">{role}</span></p>

            {error && (
              <div className="mb-4 px-4 py-3 rounded-xl bg-clay-soft text-clay text-sm">{error}</div>
            )}

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label className="block text-[11px] font-semibold text-muted uppercase tracking-wider mb-1.5">Username</label>
                <input
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder={role === 'student' ? 'e.g. student1' : role}
                  required
                  className="w-full px-4 py-3 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20 transition-all"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-muted uppercase tracking-wider mb-1.5">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full px-4 py-3 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20 transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark transition-colors disabled:opacity-60 mt-1"
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            <div className="mt-5 pt-4 border-t border-greige-border">
              <p className="text-[11px] text-muted/70 text-center leading-relaxed">
                Demo credentials<br />
                student1 / student123 &nbsp;·&nbsp; teacher1 / teacher123 &nbsp;·&nbsp; admin / admin
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
