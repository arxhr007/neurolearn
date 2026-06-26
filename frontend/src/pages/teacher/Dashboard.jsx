import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import { MetricCard } from '../../components/Card';
import Card from '../../components/Card';
import { Link } from 'react-router-dom';
import { api } from '../../api';

export default function TeacherDashboard() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/teacher/students').then(d => {
      setStudents(d?.students || []);
      setLoading(false);
    });
  }, []);

  const active = students.filter(s => s.is_active);

  return (
    <AppShell title="Teacher Dashboard">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Total Students" value={loading ? '…' : students.length} />
        <MetricCard label="Active Students" value={loading ? '…' : active.length} />
        <MetricCard label="Goals Set" value={loading ? '…' : students.reduce((a, s) => a + (s.goal_count || 0), 0)} />
      </div>

      <Card title="Students" action={
        <Link to="/teacher/students/new" className="text-sm text-sage font-semibold hover:underline">+ Add Student</Link>
      }>
        {loading ? <p className="text-sm text-muted">Loading…</p> : students.length === 0 ? (
          <p className="text-sm text-muted">No students yet. <Link to="/teacher/students/new" className="text-sage underline">Add one</Link>.</p>
        ) : (
          <div className="flex flex-col gap-0">
            <div className="grid grid-cols-4 gap-4 px-2 py-2 text-xs font-semibold text-muted uppercase tracking-wider border-b border-greige-border">
              <span>Username</span><span>Student ID</span><span>Goals</span><span>Status</span>
            </div>
            {students.map(s => (
              <Link key={s.id} to={`/teacher/students/${s.student_id}`} className="grid grid-cols-4 gap-4 px-2 py-3 text-sm border-b border-greige-border last:border-0 hover:bg-greige-accent rounded-xl transition-colors">
                <span className="text-ink font-medium">{s.username}</span>
                <span className="text-muted font-mono text-xs">{s.student_id}</span>
                <span className="text-ink">{s.goal_count ?? '—'}</span>
                <span className={`text-xs font-semibold ${s.is_active ? 'text-sage-dark' : 'text-muted'}`}>
                  {s.is_active ? 'Active' : 'Inactive'}
                </span>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
