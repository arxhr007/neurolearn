import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';

export default function Teachers() {
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/admin/teachers').then(d => {
      setTeachers(d?.teachers || []);
      setLoading(false);
    });
  }, []);

  return (
    <AppShell title="Teachers">
      <Card title={`Teachers (${teachers.length})`} action={
        <Link to="/admin/teachers/new" className="px-4 py-2 rounded-xl bg-sage text-white text-xs font-semibold hover:bg-sage-dark">+ Add Teacher</Link>
      }>
        {loading ? <p className="text-sm text-muted">Loading…</p> : teachers.length === 0 ? (
          <p className="text-sm text-muted">No teachers yet.</p>
        ) : (
          <div>
            <div className="grid grid-cols-3 gap-4 px-2 py-2 text-xs font-semibold text-muted uppercase tracking-wider border-b border-greige-border">
              <span>Username</span><span>Students</span><span>Status</span>
            </div>
            {teachers.map(t => (
              <div key={t.id} className="grid grid-cols-3 gap-4 px-2 py-3 border-b border-greige-border last:border-0 text-sm">
                <span className="text-ink font-medium">{t.username}</span>
                <span>{t.student_count ?? 0}</span>
                <span className={`text-xs font-semibold ${t.is_active ? 'text-sage-dark' : 'text-muted'}`}>{t.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}
