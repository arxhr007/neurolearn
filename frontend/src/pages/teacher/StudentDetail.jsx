import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { MetricCard } from '../../components/Card';
import { api } from '../../api';
import { LEARNING_STYLES, NEURO_PROFILES, csvToList, listToCsv } from '../../constants';

export default function StudentDetail() {
  const { id } = useParams();
  const [student, setStudent] = useState(null);
  const [mastery, setMastery] = useState([]);
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    Promise.all([
      api.get(`/api/teacher/students/${id}`),
      api.get(`/api/teacher/students/${id}/mastery`),
      api.get(`/api/teacher/students/${id}/goals`),
    ]).then(([s, m, g]) => {
      setStudent(s?.student || s);
      setMastery(m?.events || []);
      setGoals(g?.goals || []);
    }).catch(() => {
      setStudent(null);
    }).finally(() => setLoading(false));
  }, [id]);

  const startEdit = () => {
    setForm({
      full_name: student.full_name || '',
      age: student.age ?? '',
      reading_age: student.reading_age ?? '',
      learning_style: student.learning_style || 'step-by-step',
      interests: listToCsv(student.interests),
      neuro_profile: Array.isArray(student.neuro_profile) ? student.neuro_profile : [],
      is_active: student.is_active !== false,
    });
    setMsg('');
    setEditing(true);
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleProfile = (val) => {
    const arr = form.neuro_profile || [];
    set('neuro_profile', arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const save = async () => {
    setSaving(true); setMsg('');
    try {
      // Every field on StudentUpdateRequest is optional; send the whole form so
      // clearing a value works as expected.
      const updated = await api.put(`/api/teacher/students/${id}`, {
        full_name: form.full_name,
        age: Number(form.age) || 0,
        reading_age: Number(form.reading_age) || 0,
        learning_style: form.learning_style,
        interests: csvToList(form.interests),
        neuro_profile: form.neuro_profile,
        is_active: form.is_active,
      });
      setStudent(updated?.student || updated);
      setEditing(false);
      setMsg('Student updated.');
    } catch (err) {
      setMsg(err.message || 'Failed to update student.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <AppShell title="Student"><p className="text-muted text-sm">Loading…</p></AppShell>;
  if (!student) return <AppShell title="Student"><p className="text-clay text-sm">Student not found.</p></AppShell>;

  const correct = mastery.filter(e => e.is_correct).length;

  const field = (label, key, type = 'text') => (
    <div key={key}>
      <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
      <input
        type={type}
        value={form[key] ?? ''}
        onChange={e => set(key, e.target.value)}
        className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20"
      />
    </div>
  );

  return (
    <AppShell title={student.full_name || student.username}>
      <div className="flex items-center gap-2 -mt-2 mb-2">
        <Link to="/teacher/students" className="text-sm text-muted hover:text-ink">← Students</Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Mastery Events" value={mastery.length} />
        <MetricCard label="Correct" value={correct} />
        <MetricCard label="Goals" value={goals.length} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card
          title="Student Info"
          action={!editing && (
            <button onClick={startEdit} className="text-sm text-sage font-semibold hover:underline">Edit</button>
          )}
        >
          {msg && <p className="text-sm text-sage-dark bg-sage-soft px-3 py-2 rounded-lg mb-4">{msg}</p>}

          {!editing ? (
            <dl className="flex flex-col gap-2 text-sm">
              {[
                ['Student ID', student.student_id],
                ['Username', student.username],
                ['Full Name', student.full_name],
                ['Age', student.age],
                ['Reading Age', student.reading_age],
                ['Learning Style', student.learning_style],
                ['Interests', listToCsv(student.interests) || '—'],
                ['Neuro Profile', listToCsv(student.neuro_profile) || '—'],
                ['Status', student.is_active === false ? 'Inactive' : 'Active'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between py-1.5 border-b border-greige-border last:border-0">
                  <span className="text-muted font-medium">{k}</span>
                  <span className="text-ink">{v || '—'}</span>
                </div>
              ))}
            </dl>
          ) : (
            <div className="flex flex-col gap-4">
              {field('Full Name', 'full_name')}
              <div className="grid grid-cols-2 gap-4">
                {field('Age', 'age', 'number')}
                {field('Reading Age', 'reading_age', 'number')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Learning Style</label>
                <div className="flex flex-wrap gap-2">
                  {LEARNING_STYLES.map(s => (
                    <button
                      key={s} type="button" onClick={() => set('learning_style', s)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                        form.learning_style === s
                          ? 'bg-sage text-white'
                          : 'bg-greige-accent text-muted hover:text-ink'
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
                        (form.neuro_profile || []).includes(p)
                          ? 'bg-sage text-white'
                          : 'bg-greige-accent text-muted hover:text-ink'
                      }`}
                    >{p}</button>
                  ))}
                </div>
              </div>

              {field('Interests (comma separated)', 'interests')}

              <label className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={!!form.is_active}
                  onChange={e => set('is_active', e.target.checked)}
                  className="w-4 h-4 accent-sage"
                />
                Active — an inactive student cannot sign in
              </label>

              <div className="flex gap-3 mt-1">
                <button onClick={save} disabled={saving}
                  className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark disabled:opacity-50">
                  {saving ? 'Saving…' : 'Save Changes'}
                </button>
                <button type="button" onClick={() => { setEditing(false); setMsg(''); }}
                  className="px-4 py-2.5 rounded-xl border border-greige-border text-muted text-sm hover:bg-greige-accent">
                  Cancel
                </button>
              </div>
            </div>
          )}
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
