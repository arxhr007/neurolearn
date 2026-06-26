import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import { MetricCard } from '../../components/Card';
import Card from '../../components/Card';
import { api } from '../../api';

export default function AdminAnalytics() {
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/admin/teachers').then(d => {
      setTeachers(d?.teachers || []);
      setLoading(false);
    });
  }, []);

  const totalStudents = teachers.reduce((a, t) => a + (t.student_count || 0), 0);

  return (
    <AppShell title="Analytics">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Teachers" value={loading ? '…' : teachers.length} />
        <MetricCard label="Students" value={loading ? '…' : totalStudents} />
        <MetricCard label="Avg Students / Teacher" value={loading || !teachers.length ? '…' : (totalStudents / teachers.length).toFixed(1)} />
      </div>
      <Card title="Teacher Breakdown">
        {loading ? <p className="text-sm text-muted">Loading…</p> : teachers.map(t => (
          <div key={t.id} className="flex items-center justify-between py-3 border-b border-greige-border last:border-0">
            <span className="text-sm text-ink font-medium">{t.username}</span>
            <div className="flex items-center gap-4">
              <div className="h-2 bg-sage-soft rounded-full overflow-hidden w-32">
                <div className="h-full bg-sage rounded-full" style={{ width: `${Math.min(100, ((t.student_count || 0) / Math.max(1, totalStudents)) * 100)}%` }} />
              </div>
              <span className="text-sm text-muted w-8 text-right">{t.student_count ?? 0}</span>
            </div>
          </div>
        ))}
      </Card>
    </AppShell>
  );
}
