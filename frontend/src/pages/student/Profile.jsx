import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';

const STYLES = ['analogy-heavy', 'visual', 'story-based', 'step-by-step', 'repetition'];
const PROFILES = ['adhd', 'dyslexia', 'autism', 'dyscalculia'];

export default function Profile() {
  const { user } = useAuth();
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (!user?.student_id) return;
    api.get(`/api/students/${user.student_id}`).then(d => {
      setForm(d || {});
      setLoading(false);
    });
  }, [user]);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleArr = (k, val) => {
    const arr = Array.isArray(form[k]) ? form[k] : [];
    set(k, arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const save = async () => {
    setSaving(true); setMsg('');
    const res = await api.put(`/api/students/${user.student_id}`, form);
    setSaving(false);
    setMsg(res?.detail || (res?.student_id ? 'Profile saved!' : 'Saved!'));
  };

  const field = (label, key, type = 'text', placeholder = '') => (
    <div key={key}>
      <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
      <input
        type={type} value={form[key] || ''} onChange={e => set(key, type === 'number' ? Number(e.target.value) : e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20"
      />
    </div>
  );

  if (loading) return <AppShell title="Profile"><p className="text-muted text-sm">Loading…</p></AppShell>;

  return (
    <AppShell title="Profile">
      <div className="flex flex-col gap-6 w-full">
        {msg && <p className="text-sm text-sage-dark bg-sage-soft px-4 py-3 rounded-xl">{msg}</p>}

        <Card title="Basic Info">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {field('Full Name', 'full_name', 'text', 'Your name')}
            {field('Age', 'age', 'number', '10')}
            {field('Reading Age', 'reading_age', 'number', '10')}
          </div>
        </Card>

        <Card title="Learning Style">
          <div className="flex flex-wrap gap-2">
            {STYLES.map(s => (
              <button key={s} type="button" onClick={() => set('learning_style', s)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${form.learning_style === s ? 'bg-sage text-white' : 'bg-greige-accent text-muted hover:bg-greige-border'}`}>
                {s}
              </button>
            ))}
          </div>
        </Card>

        <Card title="Neuro Profile">
          <div className="flex flex-wrap gap-2">
            {PROFILES.map(p => {
              const arr = Array.isArray(form.neuro_profile) ? form.neuro_profile : [];
              return (
                <button key={p} type="button" onClick={() => toggleArr('neuro_profile', p)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${arr.includes(p) ? 'bg-sage text-white' : 'bg-greige-accent text-muted hover:bg-greige-border'}`}>
                  {p}
                </button>
              );
            })}
          </div>
        </Card>

        <Card title="Personal Details">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {field("Father's Name", 'father_name')}
            {field("Mother's Name", 'mother_name')}
            {field("Grandfather's Name", 'grandfather_name')}
            {field("Grandmother's Name", 'grandmother_name')}
            {field('Favorite Color', 'favorite_color')}
            {field("Teacher's Name", 'teacher_name')}
            {field('Place', 'place')}
            {field('Friends', 'friends', 'text', 'comma separated')}
            {field('Favorite Food', 'favorite_food')}
            {field('Favorite Animal', 'favorite_animal')}
            {field('Favorite Interest', 'favorite_interest')}
          </div>
        </Card>

        <div className="flex gap-3">
          <button onClick={save} disabled={saving}
            className="px-6 py-3 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark disabled:opacity-50">
            {saving ? 'Saving…' : 'Save Profile'}
          </button>
        </div>

        <p className="text-xs text-muted">Note: Profile save requires a PUT /api/students/:id endpoint. If not yet available, changes will show an error but local state updates.</p>
      </div>
    </AppShell>
  );
}
