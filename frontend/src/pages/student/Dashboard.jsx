import { useEffect, useState } from 'react';
import AppShell from '../../components/AppShell';
import { MetricCard } from '../../components/Card';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';

export default function StudentDashboard() {
  const { user } = useAuth();
  const [goals, setGoals] = useState([]);
  const [mastery, setMastery] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.student_id) return;
    Promise.all([
      api.get(`/api/students/${user.student_id}/goals`),
      api.get(`/api/students/${user.student_id}/mastery`),
    ]).then(([g, m]) => {
      setGoals(g?.goals || []);
      setMastery(m?.events || []);
      setLoading(false);
    });
  }, [user]);

  const activeGoal = goals.find(g => g.is_active);
  const correctCount = mastery.filter(e => e.is_correct).length;

  return (
    <AppShell title="Dashboard">
      <div>
        <h2 className="text-2xl font-bold text-ink mb-1">Welcome back, {user?.name?.split(' ')[0] || 'there'}</h2>
        <p className="text-muted text-sm">Here's your learning overview.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Active Goal" value={activeGoal ? 'Yes' : 'None'} />
        <MetricCard label="Mastery Events" value={loading ? '…' : mastery.length} />
        <MetricCard label="Correct Answers" value={loading ? '…' : correctCount} />
      </div>

      {activeGoal && (
        <Card title="Current Learning Goal">
          <p className="text-ink text-sm leading-relaxed">{activeGoal.goal_text}</p>
          <span className="inline-block mt-2 px-3 py-1 rounded-full bg-sage-soft text-sage-dark text-xs font-semibold">Active</span>
        </Card>
      )}

      <Card title="Recent Mastery Events">
        {loading ? (
          <p className="text-muted text-sm">Loading…</p>
        ) : mastery.length === 0 ? (
          <p className="text-muted text-sm">No mastery events yet. Start chatting with the tutor!</p>
        ) : (
          <div className="flex flex-col gap-2">
            {mastery.slice(0, 8).map((e, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-greige-border last:border-0">
                <span className="text-sm text-ink font-mono">{e.concept_key}</span>
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${e.is_correct ? 'bg-sage-soft text-sage-dark' : 'bg-clay-soft text-clay'}`}>
                  {e.is_correct ? 'Correct' : 'Needs work'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
