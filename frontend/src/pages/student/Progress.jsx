import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { MetricCard } from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';

export default function Progress() {
  const { user } = useAuth();
  const [mastery, setMastery] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.student_id) return;
    Promise.all([
      api.get(`/api/students/${user.student_id}/mastery`),
      api.get(`/api/students/${user.student_id}/mastery/stats`),
    ]).then(([m, s]) => {
      setMastery(m?.events || []);
      setStats(s);
      setLoading(false);
    });
  }, [user]);

  const correct = mastery.filter(e => e.is_correct).length;
  const total = mastery.length;

  return (
    <AppShell title="Progress">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Total Events" value={loading ? '…' : total} />
        <MetricCard label="Correct" value={loading ? '…' : correct} />
        <MetricCard label="Accuracy" value={loading || !total ? '…' : `${Math.round((correct / total) * 100)}%`} />
      </div>

      <Card title="Mastery History">
        {loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : mastery.length === 0 ? (
          <p className="text-sm text-muted">No mastery events yet. Start chatting to build your progress!</p>
        ) : (
          <div className="flex flex-col gap-0">
            <div className="grid grid-cols-3 gap-4 px-2 py-2 text-xs font-semibold text-muted uppercase tracking-wider border-b border-greige-border">
              <span>Concept</span><span>Source</span><span>Result</span>
            </div>
            {mastery.map((e, i) => (
              <div key={i} className={`grid grid-cols-3 gap-4 px-2 py-3 text-sm border-b border-greige-border last:border-0 ${i % 2 === 0 ? '' : 'bg-greige-bg/40'}`}>
                <span className="font-mono text-ink text-xs">{e.concept_key}</span>
                <span className="text-muted text-xs truncate">{e.source_doc || '—'}</span>
                <span className={`text-xs font-semibold ${e.is_correct ? 'text-sage-dark' : 'text-clay'}`}>
                  {e.is_correct ? '✓ Correct' : '✗ Incorrect'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
