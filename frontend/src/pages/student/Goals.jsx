import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';
import { goalsFromResponse } from '../../constants';

export default function Goals() {
  const { user } = useAuth();
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.student_id) return;
    api.get(`/api/students/${user.student_id}/goals`)
      .then(d => setGoals(goalsFromResponse(d)))
      .catch(() => setGoals([]))
      .finally(() => setLoading(false));
  }, [user]);

  return (
    <AppShell title="Goals">
      <Card title="Learning Goals">
        {loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : goals.length === 0 ? (
          <p className="text-sm text-muted">No goals set yet. Ask your teacher to add a goal.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-muted -mt-1">
              You work towards one goal at a time. Earlier goals are kept here as history.
            </p>
            {goals.map((g, i) => (
              <div key={i} className="flex items-start gap-3 py-3 border-b border-greige-border last:border-0">
                <span className={`mt-0.5 w-2.5 h-2.5 rounded-full shrink-0 ${g.is_active ? 'bg-sage' : 'bg-greige-border'}`} />
                <div>
                  <p className="text-sm text-ink">{g.goal_text}</p>
                  <span className={`text-xs font-semibold ${g.is_active ? 'text-sage-dark' : 'text-muted'}`}>
                    {g.is_active ? 'Active' : 'Previous'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
