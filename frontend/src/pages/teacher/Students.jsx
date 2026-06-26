import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';

export default function Students() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/teacher/students').then(d => {
      setStudents(d?.students || []);
      setLoading(false);
    });
  }, []);

  return (
    <AppShell title="Students">
      <Card title={`Students (${students.length})`} action={
        <Link to="/teacher/students/new" className="px-4 py-2 rounded-xl bg-sage text-white text-xs font-semibold hover:bg-sage-dark">+ Add Student</Link>
      }>
        {loading ? <p className="text-sm text-muted">Loading…</p> : students.length === 0 ? (
          <p className="text-sm text-muted">No students yet.</p>
        ) : (
          <div>
            <div className="grid grid-cols-4 gap-4 px-2 py-2 text-xs font-semibold text-muted uppercase tracking-wider border-b border-greige-border">
              <span>Username</span><span>Student ID</span><span>Goals</span><span>Status</span>
            </div>
            {students.map(s => (
              <Link key={s.id} to={`/teacher/students/${s.student_id}`}
                className="grid grid-cols-4 gap-4 px-2 py-3 text-sm border-b border-greige-border last:border-0 hover:bg-greige-accent rounded-xl transition-colors">
                <span className="text-ink font-medium">{s.username}</span>
                <span className="text-muted font-mono text-xs">{s.student_id}</span>
                <span>{s.goal_count ?? '—'}</span>
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
