import { useState, useEffect, useRef } from 'react';
import AppShell from '../../components/AppShell';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';
import { streamTTS, speakText, PROFILE_MAP, ALLOWED_PLACEHOLDERS } from '../../utils/tts';

const SEL = "w-full px-3 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/15 transition-all";
const INPUT = "w-full px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/15 transition-all";

export default function Chapter() {
  const { user } = useAuth();

  // Curriculum cascade
  const [curricula, setCurricula] = useState([]);
  const [curriculumData, setCurriculumData] = useState(null);
  const [selectedC, setSelectedC] = useState('');
  const [selectedM, setSelectedM] = useState('');
  const [selectedA, setSelectedA] = useState('');

  // Student profile for placeholder pre-fill
  const [profile, setProfile] = useState({});

  // Placeholders
  const [placeholders, setPlaceholders] = useState([]); // [{key, label, value}]

  // Drill state
  const [step, setStep] = useState('select'); // select | placeholders | drill | done
  const [story, setStory] = useState('');
  const [questions, setQuestions] = useState([]);
  const [qIndex, setQIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Audio
  const [audioReady, setAudioReady] = useState(false);
  const [audioStatus, setAudioStatus] = useState('');
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

  const startDrill = async () => {
    setLoading(true); setError('');
    const placeholder_values = {};
    placeholders.forEach(p => { if (p.value) placeholder_values[p.key] = p.value; });
    const res = await api.post('/api/chapters/learn', {
      curriculum: selectedC,
      module_number: parseInt(selectedM),
      activity_id: selectedA,
      placeholder_values,
    });
    setLoading(false);
    if (res?.story) {
      setStory(res.story);
      setQuestions(res.questions || []);
      setQIndex(0); setFeedback(''); setAnswer('');
      setAudioReady(false); setAudioStatus('');
      latestUrlRef.current = '';
      if (audioRef.current) { audioRef.current.pause(); audioRef.current.removeAttribute('src'); }
      setStep('drill');
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
      setError(res?.detail || 'Failed to generate story. Check API/Groq key.');
    }
  };

  const submitAnswer = async () => {
    if (!answer.trim() || loading) return;
    const q = questions[qIndex];
    const expected = (q.expected_answer || '').toLowerCase().trim();
    const userAns = answer.trim().toLowerCase();
    const isCorrect = expected ? (userAns.includes(expected) || expected.includes(userAns)) : false;
    setLoading(true);
    await api.post('/api/chapters/answer', {
      curriculum: selectedC,
      module_number: parseInt(selectedM),
      activity_id: selectedA,
      question: q.question,
      answer: answer.trim(),
      expected_answer: q.expected_answer || '',
      is_correct: isCorrect,
      misconception: isCorrect ? '' : `Student said: ${answer.trim()}`,
    });
    setFeedback(isCorrect
      ? `Correct! Expected: ${q.expected_answer}`
      : `Not quite. Expected: ${q.expected_answer || '(see story)'}`);
    setAnswer('');
    setLoading(false);
  };

  const nextQuestion = () => {
    if (qIndex + 1 >= questions.length) { setStep('done'); return; }
    setQIndex(i => i + 1);
    setFeedback('');
  };

  const reset = () => {
    setStep('select'); setStory(''); setQuestions([]); setQIndex(0);
    setFeedback(''); setAnswer(''); setError('');
    setAudioReady(false); setAudioStatus('');
    latestUrlRef.current = '';
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.removeAttribute('src'); }
    setSelectedC(''); setSelectedM(''); setSelectedA(''); setCurriculumData(null);
  };

  return (
    <AppShell title="Chapter Mode">

      {/* STEP: select */}
      {step === 'select' && (
        <div className="flex flex-col gap-4 w-full">
          <p className="text-sm text-muted">Select a curriculum, module, and activity to begin.</p>
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
          {error && <p className="text-sm text-clay bg-clay-soft px-4 py-3 rounded-xl">{error}</p>}
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
              <button onClick={startDrill} disabled={loading}
                className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-[13px] hover:bg-sage-dark disabled:opacity-50">
                {loading ? 'Generating story…' : 'Generate Story'}
              </button>
              <button onClick={() => setStep('select')}
                className="px-4 py-2.5 rounded-xl border border-greige-border text-muted text-[13px] hover:bg-greige-accent">
                Back
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* STEP: drill */}
      {step === 'drill' && (
        <div className="flex flex-col gap-4 w-full">
          {story && (
            <Card title="Story">
              <p className="text-ink leading-relaxed text-sm whitespace-pre-wrap">{story}</p>
              {/* Audio player */}
              <div className="mt-4">
                {audioStatus && (
                  <p className="text-xs text-muted mb-2">{audioStatus}</p>
                )}
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
            </Card>
          )}

          {questions.length > 0 && (
            <Card title={`Question ${qIndex + 1} of ${questions.length}`}>
              <div className="flex items-start gap-3 mb-4">
                <p className="text-ink leading-relaxed flex-1">{questions[qIndex]?.question}</p>
                <button
                  onClick={() => speakText(questions[qIndex]?.question)}
                  className="shrink-0 px-3 py-1.5 rounded-lg border border-greige-border text-[12px] text-muted hover:bg-greige-accent"
                  title="Read question aloud"
                >
                  Read aloud
                </button>
              </div>

              {feedback && (
                <div className={`mb-4 px-4 py-3 rounded-xl text-sm ${
                  feedback.startsWith('Correct')
                    ? 'bg-sage-soft border border-sage/20 text-sage-dark'
                    : 'bg-clay-soft border border-clay/20 text-clay'
                }`}>
                  {feedback}
                </div>
              )}

              {!feedback ? (
                <div className="flex gap-3">
                  <input value={answer} onChange={e => setAnswer(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && submitAnswer()}
                    placeholder="Type your answer…"
                    className="flex-1 px-4 py-2.5 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/15 transition-all" />
                  <button onClick={submitAnswer} disabled={loading || !answer.trim()}
                    className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-[13px] hover:bg-sage-dark disabled:opacity-50">
                    {loading ? '…' : 'Submit'}
                  </button>
                </div>
              ) : (
                <div className="flex gap-3">
                  <button onClick={nextQuestion}
                    className="px-5 py-2.5 rounded-xl bg-sage text-white font-semibold text-[13px] hover:bg-sage-dark">
                    {qIndex + 1 >= questions.length ? 'Finish' : 'Next Question'}
                  </button>
                  <button onClick={reset} className="px-4 py-2.5 rounded-xl border border-greige-border text-muted text-[13px] hover:bg-greige-accent">
                    Restart
                  </button>
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {/* STEP: done */}
      {step === 'done' && (
        <Card title="Chapter Complete">
          <p className="text-sm text-ink mb-4">All {questions.length} questions answered.</p>
          <button onClick={reset} className="px-5 py-2.5 rounded-xl bg-sage text-white text-[13px] font-semibold hover:bg-sage-dark">
            Try Another
          </button>
        </Card>
      )}
    </AppShell>
  );
}
