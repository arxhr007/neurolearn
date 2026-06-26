import { useState, useEffect, useRef } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { api } from '../../api';

export default function Memories() {
  const [memories, setMemories] = useState([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const audioRef = useRef(null);

  const load = () => {
    setLoading(true);
    api.get('/api/story/memories').then(d => {
      setMemories(d?.memories || d || []);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, []);

  const saveText = async () => {
    if (!text.trim()) return;
    setSaving(true); setError(''); setSuccess('');
    const fd = new FormData();
    fd.append('text', text.trim());
    const res = await api.postForm('/api/memories', fd);
    setSaving(false);
    if (res?.id || res?.memory_id || res?.text) {
      setText(''); setSuccess('Memory saved!'); load();
    } else {
      setError(res?.detail || 'Failed to save memory.');
    }
  };

  const saveAudio = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSaving(true); setError(''); setSuccess('');
    const fd = new FormData();
    fd.append('audio', file);
    const res = await api.postForm('/api/memories', fd);
    setSaving(false);
    if (res?.id || res?.memory_id || res?.text) {
      setSuccess('Audio memory saved!'); load();
    } else {
      setError(res?.detail || 'Failed to save audio memory.');
    }
    e.target.value = '';
  };

  return (
    <AppShell title="Memories">
      <div className="flex flex-col gap-6 w-full">
        <div>
          <h2 className="text-xl font-bold text-ink mb-1">My Memories</h2>
          <p className="text-sm text-muted">Share personal memories to help the tutor personalize stories for you.</p>
        </div>

        <Card title="Add a Memory">
          {error && <p className="text-sm text-clay bg-clay-soft px-3 py-2 rounded-lg mb-3">{error}</p>}
          {success && <p className="text-sm text-sage-dark bg-sage-soft px-3 py-2 rounded-lg mb-3">{success}</p>}
          <textarea
            value={text} onChange={e => setText(e.target.value)}
            placeholder="Write a memory… (e.g. I love playing football with my friends on Sundays.)"
            rows={4}
            className="w-full px-4 py-3 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20 resize-none"
          />
          <div className="flex gap-3 mt-3 flex-wrap">
            <button onClick={saveText} disabled={saving || !text.trim()}
              className="px-5 py-2.5 rounded-xl bg-sage text-white text-sm font-semibold hover:bg-sage-dark disabled:opacity-50">
              {saving ? 'Saving…' : 'Save Memory'}
            </button>
            <label className="px-5 py-2.5 rounded-xl border border-greige-border text-muted text-sm font-medium hover:bg-greige-accent cursor-pointer">
              🎤 Upload Audio
              <input type="file" accept="audio/*" className="hidden" onChange={saveAudio} ref={audioRef} />
            </label>
          </div>
        </Card>

        <Card title={`Memories (${memories.length})`}>
          {loading ? (
            <p className="text-sm text-muted">Loading memories…</p>
          ) : memories.length === 0 ? (
            <p className="text-sm text-muted">No memories yet. Add your first one above!</p>
          ) : (
            <div className="flex flex-col gap-3">
              {memories.map((m, i) => (
                <div key={i} className="p-4 rounded-xl bg-greige-bg border border-greige-border">
                  <div className="flex items-center gap-2 mb-2">
                    {m.category && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sage-soft text-sage-dark">
                        {m.category}
                      </span>
                    )}
                    {m.title && <span className="text-xs text-muted font-medium">{m.title}</span>}
                  </div>
                  <p className="text-sm text-ink leading-relaxed">{m.text || m.summary}</p>
                  {m.tags && <p className="text-xs text-muted mt-1">{m.tags}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
