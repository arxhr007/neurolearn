import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';
import { LEARNING_STYLES, NEURO_PROFILES, csvToList } from '../../constants';

export default function StudentCreate() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ student_id: '', username: '', password: '', full_name: '', age: '', reading_age: '', learning_style: 'step-by-step', interests: '', neuro_profile: [] });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleProfile = (val) => {
    const arr = form.neuro_profile || [];
    set('neuro_profile', arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const res = await api.post('/api/teacher/students', {
        ...form,
        age: Number(form.age),
        reading_age: Number(form.reading_age),
        interests: csvToList(form.interests),
      });
      if (res?.student_id || res?.id) {
        navigate('/teacher/students');
      } else {
        setError('Failed to create student.');
      }
    } catch (err) {
      setError(err.message || 'Failed to create student.');
    } finally {
      setSaving(false);
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

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Learning Style</label>
              <div className="flex flex-wrap gap-2">
                {LEARNING_STYLES.map(s => (
                  <button
                    key={s} type="button" onClick={() => set('learning_style', s)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      form.learning_style === s ? 'bg-sage text-white' : 'bg-greige-accent text-muted hover:text-ink'
                    }`}
                  >{s}</button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Neuro Profile</label>
              <div className="flex flex-wrap gap-2">
                {NEURO_PROFILES.map(p => (
                  <button
                    key={p} type="button" onClick={() => toggleProfile(p)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      (form.neuro_profile || []).includes(p) ? 'bg-sage text-white' : 'bg-greige-accent text-muted hover:text-ink'
                    }`}
                  >{p}</button>
                ))}
              </div>
              <p className="text-xs text-muted mt-1.5">Leave empty for a general profile.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Interests (comma separated)</label>
              <input
                type="text" value={form.interests} onChange={e => set('interests', e.target.value)}
                placeholder="football, animals, drawing"
                className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20"
              />
              <p className="text-xs text-muted mt-1.5">Used to personalise explanations and stories.</p>
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
