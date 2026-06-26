import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';

export default function StudentCreate() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ student_id: '', username: '', password: '', full_name: '', age: '', reading_age: '', learning_style: 'step-by-step', neuro_profile: [] });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true); setError('');
    const res = await api.post('/api/teacher/students', {
      ...form,
      age: Number(form.age),
      reading_age: Number(form.reading_age),
    });
    setSaving(false);
    if (res?.student_id || res?.id) {
      navigate('/teacher/students');
    } else {
      setError(res?.detail || 'Failed to create student.');
    }
  };

  return (
    <AppShell title="Add Student">
      <div className="w-full">
        <Card title="New Student">
          {error && <p className="text-sm text-clay bg-clay-soft px-3 py-2 rounded-lg mb-4">{error}</p>}
          <form onSubmit={submit} className="flex flex-col gap-4">
            {[['Student ID', 'student_id', 'text', 's101'], ['Username', 'username', 'text', 'student2'], ['Password', 'password', 'password', ''], ['Full Name', 'full_name', 'text', '']].map(([label, key, type, ph]) => (
              <div key={key}>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
                <input type={type} value={form[key]} onChange={e => set(key, e.target.value)} placeholder={ph} required={key !== 'full_name'}
                  className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20" />
              </div>
            ))}
            <div className="grid grid-cols-2 gap-4">
              {[['Age', 'age'], ['Reading Age', 'reading_age']].map(([label, key]) => (
                <div key={key}>
                  <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
                  <input type="number" value={form[key]} onChange={e => set(key, e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage" />
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-2">
              <button type="submit" disabled={saving}
                className="px-6 py-2.5 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark disabled:opacity-50">
                {saving ? 'Creating…' : 'Create Student'}
              </button>
              <button type="button" onClick={() => navigate('/teacher/students')}
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
