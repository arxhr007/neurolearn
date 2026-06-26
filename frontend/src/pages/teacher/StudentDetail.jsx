import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { MetricCard } from '../../components/Card';
import { api } from '../../api';

export default function StudentDetail() {
  const { id } = useParams();
  const [student, setStudent] = useState(null);
  const [mastery, setMastery] = useState([]);
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get(`/api/teacher/students/${id}`),
      api.get(`/api/teacher/students/${id}/mastery`),
      api.get(`/api/teacher/students/${id}/goals`),
    ]).then(([s, m, g]) => {
      setStudent(s?.student || s);
      setMastery(m?.events || []);
      setGoals(g?.goals || []);
      setLoading(false);
    });
  }, [id]);

  if (loading) return <AppShell title="Student"><p className="text-muted text-sm">Loading…</p></AppShell>;
  if (!student) return <AppShell title="Student"><p className="text-clay text-sm">Student not found.</p></AppShell>;

  const correct = mastery.filter(e => e.is_correct).length;

  return (
    <AppShell title={student.full_name || student.username}>
      <div className="flex items-center gap-2 -mt-2 mb-2">
        <Link to="/teacher/students" className="text-sm text-muted hover:text-ink">← Students</Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Mastery Events" value={mastery.length} icon="📊" />
        <MetricCard label="Correct" value={correct} icon="✅" />
        <MetricCard label="Goals" value={goals.length} icon="🎯" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Student Info">
          <dl className="flex flex-col gap-2 text-sm">
            {[['Student ID', student.student_id], ['Username', student.username], ['Age', student.age], ['Reading Age', student.reading_age], ['Learning Style', student.learning_style], ['Neuro Profile', (student.neuro_profile || []).join(', ') || '—']].map(([k, v]) => (
              <div key={k} className="flex justify-between py-1.5 border-b border-greige-border last:border-0">
                <span className="text-muted font-medium">{k}</span>
                <span className="text-ink">{v || '—'}</span>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Goals">
          {goals.length === 0 ? <p className="text-sm text-muted">No goals set.</p> : goals.map((g, i) => (
            <div key={i} className="py-2 border-b border-greige-border last:border-0 flex items-start gap-2">
              <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${g.is_active ? 'bg-sage' : 'bg-greige-border'}`} />
              <p className="text-sm text-ink">{g.goal_text}</p>
            </div>
          ))}
        </Card>
      </div>

      <Card title="Recent Mastery Events">
        {mastery.slice(0, 10).map((e, i) => (
          <div key={i} className="flex items-center justify-between py-2.5 border-b border-greige-border last:border-0">
            <span className="text-xs font-mono text-ink">{e.concept_key}</span>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${e.is_correct ? 'bg-sage-soft text-sage-dark' : 'bg-clay-soft text-clay'}`}>
              {e.is_correct ? 'Correct' : 'Incorrect'}
            </span>
          </div>
        ))}
        {mastery.length === 0 && <p className="text-sm text-muted">No mastery events yet.</p>}
      </Card>
    </AppShell>
  );
}
