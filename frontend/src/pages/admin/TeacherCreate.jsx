import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';

export default function TeacherCreate() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '', full_name: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true); setError('');
    const res = await api.post('/api/admin/teachers', form);
    setSaving(false);
    if (res?.id || res?.username) {
      navigate('/admin/teachers');
    } else {
      setError(res?.detail || 'Failed to create teacher.');
    }
  };

  return (
    <AppShell title="Add Teacher">
      <div className="w-full">
        <Card title="New Teacher">
          {error && <p className="text-sm text-clay bg-clay-soft px-3 py-2 rounded-lg mb-4">{error}</p>}
          <form onSubmit={submit} className="flex flex-col gap-4">
            {[['Username', 'username', 'text'], ['Password', 'password', 'password'], ['Full Name', 'full_name', 'text']].map(([label, key, type]) => (
              <div key={key}>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
                <input type={type} value={form[key]} onChange={e => set(key, e.target.value)} required={key !== 'full_name'}
                  className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20" />
              </div>
            ))}
            <div className="flex gap-3 mt-2">
              <button type="submit" disabled={saving}
                className="px-6 py-2.5 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark disabled:opacity-50">
                {saving ? 'Creating…' : 'Create Teacher'}
              </button>
              <button type="button" onClick={() => navigate('/admin/teachers')}
                className="px-5 py-2.5 rounded-xl border border-greige-border text-muted text-sm hover:bg-greige-accent">
                Cancel
              </button>
            </div>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
