import { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';
import { goalsFromResponse } from '../../constants';

export default function TeacherGoals() {
  const [students, setStudents] = useState([]);
  const [goals, setGoals] = useState([]);
  const [form, setForm] = useState({ student_id: '', goal_text: '' });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api.get('/api/teacher/students')
      .then(d => setStudents(d?.students || []))
      .catch(() => setStudents([]));
  }, []);

  const loadGoals = (studentId) => {
    if (!studentId) return;
    api.get(`/api/teacher/students/${studentId}/goals`)
      .then(d => setGoals(goalsFromResponse(d)))
      .catch(() => setGoals([]));
  };

  const setStudentId = (id) => { setForm(f => ({ ...f, student_id: id })); loadGoals(id); };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.student_id || !form.goal_text.trim()) return;
    setSaving(true); setMsg('');
    try {
      const res = await api.post(`/api/students/${form.student_id}/goals`, { goal_text: form.goal_text });
      if (res?.goal_id || res?.goal_text) {
        setMsg('Goal created!');
        setForm(f => ({ ...f, goal_text: '' }));
        loadGoals(form.student_id);
      } else {
        setMsg('Failed to create goal.');
      }
    } catch (err) {
      setMsg(err.message || 'Failed to create goal.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell title="Goals">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Set Learning Goal">
          {msg && <p className="text-sm text-sage-dark bg-sage-soft px-3 py-2 rounded-lg mb-4">{msg}</p>}
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Student</label>
              <select value={form.student_id} onChange={e => setStudentId(e.target.value)} required
                className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage">
                <option value="">Select student…</option>
                {students.map(s => <option key={s.id} value={s.student_id}>{s.username} ({s.student_id})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Goal</label>
              <textarea value={form.goal_text} onChange={e => setForm(f => ({ ...f, goal_text: e.target.value }))} required rows={3}
                placeholder="e.g. Learn the steps of handwashing"
                className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage resize-none" />
            </div>
            <p className="text-xs text-muted -mt-1">
              A student has one active goal at a time. Setting a new goal replaces the
              current one, which is kept as history. The tutor uses the active goal to
              steer students back on topic.
            </p>
            <button type="submit" disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark disabled:opacity-50 self-start">
              {saving ? 'Saving…' : 'Set Goal'}
            </button>
          </form>
        </Card>

        <Card title="Student Goals">
          {!form.student_id ? (
            <p className="text-sm text-muted">Select a student to see their goals.</p>
          ) : goals.length === 0 ? (
            <p className="text-sm text-muted">No goals for this student yet.</p>
          ) : goals.map((g, i) => (
            <div key={i} className="py-3 border-b border-greige-border last:border-0 flex items-start gap-2">
              <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${g.is_active ? 'bg-sage' : 'bg-greige-border'}`} />
              <div>
                <p className="text-sm text-ink">{g.goal_text}</p>
                <span className={`text-xs font-medium ${g.is_active ? 'text-sage-dark' : 'text-muted'}`}>{g.is_active ? 'Active' : 'Previous'}</span>
              </div>
            </div>
          ))}
        </Card>
      </div>
    </AppShell>
  );
}
