import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import { MetricCard } from '../../components/Card';
import Card from '../../components/Card';
import { api } from '../../api';

export default function TeacherAnalytics() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/teacher/students').then(d => {
      setStudents(d?.students || []);
      setLoading(false);
    });
  }, []);

  return (
    <AppShell title="Analytics">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Total Students" value={loading ? '…' : students.length} icon="👥" />
        <MetricCard label="Active" value={loading ? '…' : students.filter(s => s.is_active).length} icon="✅" />
        <MetricCard label="Total Goals" value={loading ? '…' : students.reduce((a, s) => a + (s.goal_count || 0), 0)} icon="🎯" />
      </div>

      <Card title="Class Overview">
        {loading ? <p className="text-sm text-muted">Loading…</p> : students.length === 0 ? (
          <p className="text-sm text-muted">No students yet.</p>
        ) : (
          <div>
            <div className="grid grid-cols-3 gap-4 px-2 py-2 text-xs font-semibold text-muted uppercase tracking-wider border-b border-greige-border">
              <span>Student</span><span>Goals</span><span>Status</span>
            </div>
            {students.map(s => (
              <div key={s.id} className="grid grid-cols-3 gap-4 px-2 py-3 border-b border-greige-border last:border-0 text-sm">
                <span className="text-ink font-medium">{s.username}</span>
                <span>{s.goal_count ?? 0}</span>
                <span className={`text-xs font-semibold ${s.is_active ? 'text-sage-dark' : 'text-muted'}`}>{s.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
