import { useState, useEffect, useRef } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';
import { streamTTS, PROFILE_MAP, ALLOWED_PLACEHOLDERS } from '../../utils/tts';

const SEL = "w-full px-3 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/15 transition-all";
const INPUT = "w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/15 transition-all";

export default function Story() {
  const { user } = useAuth();

  const [curricula, setCurricula] = useState([]);
  const [curriculumData, setCurriculumData] = useState(null);
  const [selectedC, setSelectedC] = useState('');
  const [selectedM, setSelectedM] = useState('');
  const [selectedA, setSelectedA] = useState('');
  const [profile, setProfile] = useState({});
  const [placeholders, setPlaceholders] = useState([]);

  const [step, setStep] = useState('select'); // select | placeholders | result
  const [result, setResult] = useState(null);
  const [audioReady, setAudioReady] = useState(false);
  const [audioStatus, setAudioStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const audioRef = useRef(null);
  const latestUrlRef = useRef('');

  useEffect(() => {
    api.get('/api/story/curricula').then(d => setCurricula(d?.curricula || []));
  }, []);

  useEffect(() => {
    if (!user?.student_id) return;
    api.get(`/api/students/${user.student_id}`).then(d => setProfile(d || {}));
  }, [user]);

  const handleCurriculumChange = async (name) => {
    setSelectedC(name); setSelectedM(''); setSelectedA(''); setCurriculumData(null);
    if (!name) return;
    const data = await api.get(`/api/story/curricula/${name}`);
    setCurriculumData(data);
  };

  const modules = curriculumData?.modules || [];
  const selectedModule = modules.find(m => String(m.module_number) === selectedM);
  const activities = selectedModule?.activities || [];
  const selectedActivity = activities.find(a => a.activity_id === selectedA);

  const goToPlaceholders = () => {
    if (!selectedA) return;
    const map = PROFILE_MAP(profile);
    setPlaceholders(ALLOWED_PLACEHOLDERS.map(({ key, label }) => ({
      key,
      label,
      value: map[key] || '',
    })));
    setError('');
    setStep('placeholders');
  };

  const setPhValue = (key, val) => {
    setPlaceholders(ps => ps.map(p => p.key === key ? { ...p, value: val } : p));
  };

  const generate = async () => {
    setLoading(true); setError('');
    const placeholder_values = {};
    placeholders.forEach(p => { if (p.value) placeholder_values[p.key] = p.value; });
    const res = await api.post('/api/story/generate', {
      curriculum: selectedC,
      module_number: parseInt(selectedM),
      activity_id: selectedA,
      placeholder_values,
    });
    setLoading(false);
    if (res?.story) {
      setResult(res);
      setAudioReady(false); setAudioStatus('');
      latestUrlRef.current = '';
      if (audioRef.current) { audioRef.current.pause(); audioRef.current.removeAttribute('src'); }
      setStep('result');
      streamTTS(res.story, (url, status) => {
        setAudioStatus(status);
        if (url) {
          latestUrlRef.current = url;
          const el = audioRef.current;
          if (el) {
            const isPlaying = !el.paused && !el.ended && el.readyState > 0;
            if (!isPlaying) {
              el.src = url;
              el.play().catch(() => {});
              setAudioReady(true);
            }
          }
        }
      });
    } else {
      setError(res?.detail || 'Story generation failed. Check API keys.');
    }
  };

  const reset = () => {
    setStep('select'); setResult(null); setAudioReady(false); setAudioStatus('');
    latestUrlRef.current = '';
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.removeAttribute('src'); }
    setSelectedC(''); setSelectedM(''); setSelectedA(''); setCurriculumData(null);
    setError('');
  };

  return (
    <AppShell title="Story Mode">

      {/* STEP: select */}
      {step === 'select' && (
        <div className="flex flex-col gap-4 w-full">
          <p className="text-sm text-muted">Select a curriculum, module, and activity to generate a personalised story.</p>
          <Card title="Curriculum">
            <select value={selectedC} onChange={e => handleCurriculumChange(e.target.value)} className={SEL}>
              <option value="">Select curriculum…</option>
              {curricula.map(c => <option key={c.name} value={c.name}>{c.title || c.name}</option>)}
            </select>
          </Card>
          {selectedC && (
            <Card title="Module">
              <select value={selectedM} onChange={e => { setSelectedM(e.target.value); setSelectedA(''); }} className={SEL}>
                <option value="">Select module…</option>
                {modules.map(m => <option key={m.module_number} value={m.module_number}>{m.module_title || `Module ${m.module_number}`}</option>)}
              </select>
            </Card>
          )}
          {selectedM && (
            <Card title="Activity">
              <select value={selectedA} onChange={e => setSelectedA(e.target.value)} className={SEL}>
                <option value="">Select activity…</option>
                {activities.map(a => <option key={a.activity_id} value={a.activity_id}>{a.activity_name || a.activity_id}</option>)}
              </select>
            </Card>
          )}
          <button onClick={goToPlaceholders} disabled={!selectedA}
            className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-[13px] hover:bg-sage-dark disabled:opacity-50 self-start">
            Continue
          </button>
        </div>
      )}

      {/* STEP: placeholders */}
      {step === 'placeholders' && (
        <div className="flex flex-col gap-4 w-full">
          <Card title={`Fill in details — ${selectedActivity?.activity_name || selectedA}`}>
            {placeholders.length === 0 ? (
              <p className="text-sm text-muted mb-4">No personalisation fields for this activity.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                {placeholders.map(p => (
                  <div key={p.key}>
                    <label className="flex items-center gap-1.5 text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                      {p.label}
                      {p.optional && <span className="text-[10px] font-normal normal-case tracking-normal text-muted/60">(optional)</span>}
                    </label>
                    <input value={p.value} onChange={e => setPhValue(p.key, e.target.value)} className={INPUT} placeholder={`Enter ${p.label.toLowerCase()}`} />
                  </div>
                ))}
              </div>
            )}
            {error && <p className="text-sm text-clay bg-clay-soft px-4 py-3 rounded-xl mb-3">{error}</p>}
            <div className="flex gap-3">
              <button onClick={generate} disabled={loading}
                className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-[13px] hover:bg-sage-dark disabled:opacity-50">
                {loading ? 'Generating…' : 'Generate Story'}
              </button>
              <button onClick={() => setStep('select')}
                className="px-4 py-2.5 rounded-xl border border-greige-border text-muted text-[13px] hover:bg-greige-accent">
                Back
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* STEP: result */}
      {step === 'result' && result && (
        <div className="flex flex-col gap-4 w-full">
          <Card title={result.activity?.name || selectedActivity?.activity_name || 'Story'}>
            {result.activity?.theme && (
              <p className="text-xs text-muted mb-3">Theme: {result.activity.theme}</p>
            )}
            <p className="text-ink leading-relaxed text-sm whitespace-pre-wrap">{result.story}</p>

            <div className="mt-4">
              {audioStatus && <p className="text-xs text-muted mb-2">{audioStatus}</p>}
              {audioReady && (
                <audio
                  ref={audioRef}
                  controls
                  className="w-full rounded-lg"
                  onEnded={() => {
                    if (latestUrlRef.current && audioRef.current) {
                      audioRef.current.src = latestUrlRef.current;
                    }
                  }}
                />
              )}
            </div>

            {result.activity?.moral && (
              <div className="mt-4 px-4 py-3 rounded-xl bg-sage-soft border border-sage/20">
                <p className="text-xs font-semibold text-sage uppercase tracking-wider mb-1">Moral</p>
                <p className="text-sm text-ink">{result.activity.moral}</p>
              </div>
            )}

            <button onClick={reset}
              className="mt-4 px-4 py-2.5 rounded-xl border border-greige-border text-muted text-[13px] hover:bg-greige-accent">
              Generate Another
            </button>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
