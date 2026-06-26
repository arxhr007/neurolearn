import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api';

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d)) return '';
  const now = new Date();
  const diffMs = now - d;
  const diffH = diffMs / 3600000;
  if (diffH < 1) return 'just now';
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  if (diffH < 48) return 'yesterday';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function Section({ title, children }) {
  return (
    <div className="mb-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-white/35 px-4 mb-1.5">{title}</p>
      {children}
    </div>
  );
}

function Row({ label, sub, onClick, badge }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-start gap-2 px-4 py-2 hover:bg-white/6 transition-colors"
    >
      <div className="flex-1 min-w-0">
        <p className="text-[12px] text-white/75 truncate leading-tight">{label}</p>
        {sub && <p className="text-[10px] text-white/35 mt-0.5 truncate">{sub}</p>}
      </div>
      {badge && (
        <span className={`shrink-0 mt-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
          badge === 'ok' ? 'bg-sage/25 text-sage' : 'bg-clay/20 text-clay'
        }`}>
          {badge === 'ok' ? 'Correct' : 'Wrong'}
        </span>
      )}
    </button>
  );
}

function Skeleton() {
  return (
    <div className="px-4 flex flex-col gap-2">
      {[1,2,3].map(i => (
        <div key={i} className="h-8 rounded-lg bg-white/8 animate-pulse" />
      ))}
    </div>
  );
}

export default function HistoryPanel({ open, onClose }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState({ convs: [], memories: [], mastery: [] });
  const [loading, setLoading] = useState(false);
  const lastFetchRef = useRef(0);

  useEffect(() => {
    if (!open || user?.role !== 'student') return;
    const now = Date.now();
    if (now - lastFetchRef.current < 60000) return; // cache 60s
    lastFetchRef.current = now;
    setLoading(true);
    Promise.all([
      api.get(`/api/conversations/${user.student_id}?limit=8`),
      api.get('/api/story/memories'),
      api.get(`/api/students/${user.student_id}/mastery?limit=8`),
    ]).then(([c, m, ma]) => {
      setData({
        convs: c?.conversations || [],
        memories: m?.memories || [],
        mastery: ma?.events || [],
      });
      setLoading(false);
    });
  }, [open, user]);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/20"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className="fixed z-40 flex flex-col"
        style={{
          top: 76,
          left: 0,
          bottom: 0,
          width: 276,
          background: '#1e2328',
          borderRight: '1px solid rgba(255,255,255,0.07)',
          transform: open ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 0.22s cubic-bezier(0.4,0,0.2,1)',
          boxShadow: open ? '4px 0 24px rgba(0,0,0,0.18)' : 'none',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/8">
          <span className="text-[13px] font-semibold text-white/80">History</span>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded-md text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M1 1l8 8M9 1L1 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-3">
          {user?.role !== 'student' ? (
            <p className="text-[12px] text-white/30 px-4 mt-2">History is available for student accounts.</p>
          ) : loading ? (
            <Skeleton />
          ) : (
            <>
              <Section title="Recent Conversations">
                {data.convs.length === 0
                  ? <p className="text-[11px] text-white/25 px-4">No conversations yet.</p>
                  : data.convs.map(c => (
                    <Row
                      key={c.id || c.conversation_id}
                      label="Conversation"
                      sub={`${fmtDate(c.created_at)}${c.message_count ? ` · ${c.message_count} messages` : ''}`}
                      onClick={() => { onClose(); navigate('/student/chat'); }}
                    />
                  ))
                }
              </Section>

              <Section title="Memories">
                {data.memories.length === 0
                  ? <p className="text-[11px] text-white/25 px-4">No memories saved yet.</p>
                  : data.memories.slice(0, 6).map((m, i) => (
                    <Row
                      key={i}
                      label={m.text || m.summary || 'Memory'}
                      sub={m.category || m.tags || ''}
                      onClick={() => { onClose(); navigate('/student/memories'); }}
                    />
                  ))
                }
              </Section>

              <Section title="Recent Activity">
                {data.mastery.length === 0
                  ? <p className="text-[11px] text-white/25 px-4">No activity yet.</p>
                  : data.mastery.map((e, i) => (
                    <Row
                      key={i}
                      label={e.concept_key?.split('.').slice(-1)[0]?.replace(/_/g, ' ') || e.concept_key}
                      sub={fmtDate(e.created_at)}
                      badge={e.is_correct ? 'ok' : 'wrong'}
                      onClick={() => { onClose(); navigate('/student/progress'); }}
                    />
                  ))
                }
              </Section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
