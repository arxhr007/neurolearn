import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import AppShell from '../../components/AppShell';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api';

let msgId = 0;
const uid = () => `${Date.now()}-${++msgId}`;
const newConvId = () => `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s);
  return isNaN(d) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function Chat() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [convId, setConvId] = useState(() => newConvId());
  const [messages, setMessages] = useState([
    { id: uid(), role: 'tutor', text: 'Hello! What would you like to learn today?' }
  ]);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState('question');
  const [loading, setLoading] = useState(false);
  const [lastTurnId, setLastTurnId] = useState(null);
  const [lastHint, setLastHint] = useState(null);
  const [checkQ, setCheckQ] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const loadConversations = useCallback(() => {
    if (!user?.student_id) return;
    api.get(`/api/conversations/${user.student_id}`).then(d => {
      setConversations(d?.conversations || []);
    });
  }, [user]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  const loadConversation = async (id) => {
    const data = await api.get(`/api/conversations/${user.student_id}/${id}`);
    const msgs = data?.messages || data?.turns || [];
    if (msgs.length === 0) return;
    setMessages(msgs.map(m => ({
      id: uid(),
      role: m.role === 'student' ? 'student' : 'tutor',
      text: m.content || m.text || '',
    })));
    setConvId(id);
    setMode('question');
    setCheckQ(null);
  };

  const startNewConv = () => {
    setConvId(newConvId());
    setMessages([{ id: uid(), role: 'tutor', text: 'Hello! What would you like to learn today?' }]);
    setMode('question');
    setCheckQ(null);
    setInput('');
  };

  const deleteConv = async (id, e) => {
    e.stopPropagation();
    await api.delete(`/api/conversations/${id}`);
    setConversations(cs => cs.filter(c => (c.id || c.conversation_id) !== id));
    if (convId === id) startNewConv();
  };

  const addMsg = (role, text) => setMessages(prev => [...prev, { id: uid(), role, text }]);

  const sendQuestion = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim(); setInput('');
    addMsg('student', q);
    setLoading(true); setCheckQ(null);
    const res = await api.post('/api/tutor/question', {
      student_id: user.student_id,
      conversation_id: convId,
      question: q,
      context: {},
    });
    if (res?.answer) {
      addMsg('tutor', res.answer);
      if (res.check_question) {
        setCheckQ(res.check_question);
        setLastTurnId(res.turn_id);
        setLastHint(res.check_answer_hint);
        setMode('answer');
      }
    } else {
      addMsg('tutor', res?.detail || 'Sorry, I had trouble answering that.');
    }
    setLoading(false);
    loadConversations();
  };

  const sendAnswer = async () => {
    if (!input.trim() || loading) return;
    const ans = input.trim(); setInput('');
    addMsg('student', ans);
    setLoading(true); setCheckQ(null);
    const res = await api.post('/api/tutor/answer', {
      student_id: user.student_id,
      conversation_id: convId,
      turn_id: lastTurnId,
      student_answer: ans,
      check_answer_hint: lastHint,
    });
    if (res?.feedback) addMsg('tutor', res.feedback);
    setMode('question');
    setLoading(false);
  };

  const handleSend = () => mode === 'question' ? sendQuestion() : sendAnswer();

  return (
    <AppShell title="Chat with Tutor">
      <div className="flex gap-4 flex-1" style={{ minHeight: 0 }}>

        {/* Conversation sidebar */}
        <aside className="w-52 shrink-0 flex flex-col gap-2">
          <button onClick={startNewConv}
            className="w-full px-3 py-2 rounded-xl bg-sage text-white text-[13px] font-semibold hover:bg-sage-dark transition-colors">
            New conversation
          </button>
          <div className="flex flex-col gap-1 overflow-y-auto" style={{ maxHeight: 460 }}>
            {conversations.length === 0 ? (
              <p className="text-xs text-muted px-1 mt-2">No past conversations yet.</p>
            ) : conversations.map(c => {
              const id = c.id || c.conversation_id;
              const active = convId === id;
              return (
                <div key={id} onClick={() => loadConversation(id)}
                  className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer text-[13px] transition-colors ${active ? 'bg-sage/10 text-ink' : 'hover:bg-greige-accent text-muted hover:text-ink'}`}>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium truncate text-[12px]">Conversation</p>
                    <p className="text-[11px] text-muted/70">{fmtDate(c.created_at)}{c.message_count ? ` · ${c.message_count} msgs` : ''}</p>
                  </div>
                  <button onClick={e => deleteConv(id, e)}
                    className="ml-1 opacity-0 group-hover:opacity-100 text-[11px] text-clay hover:text-clay px-1 py-0.5 transition-opacity shrink-0">
                    Del
                  </button>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Chat area */}
        <div className="flex flex-col gap-3 flex-1 min-w-0">
          <div className="flex-1 bg-greige-panel rounded-2xl border border-greige-border p-4 flex flex-col gap-3 overflow-y-auto" style={{ minHeight: 320, maxHeight: 460 }}>
            {messages.map(m => (
              <div key={m.id} className={`flex ${m.role === 'student' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'student'
                    ? 'bg-sage text-white rounded-br-sm'
                    : 'bg-greige-accent text-ink rounded-bl-sm'
                }`}>
                  {m.role === 'tutor' ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        em: ({ children }) => <em className="italic">{children}</em>,
                        ul: ({ children }) => <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        h1: ({ children }) => <p className="font-bold text-base mb-1">{children}</p>,
                        h2: ({ children }) => <p className="font-bold mb-1">{children}</p>,
                        h3: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
                        code: ({ children }) => <code className="bg-black/10 rounded px-1 font-mono text-xs">{children}</code>,
                        blockquote: ({ children }) => <blockquote className="border-l-2 border-sage/40 pl-2 italic opacity-80">{children}</blockquote>,
                      }}
                    >
                      {m.text}
                    </ReactMarkdown>
                  ) : m.text}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-greige-accent text-muted px-4 py-3 rounded-2xl rounded-bl-sm text-sm animate-pulse">Thinking…</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {checkQ && (
            <div className="bg-sage-soft border border-sage/20 rounded-xl px-4 py-3">
              <p className="text-xs font-semibold text-sage-dark uppercase tracking-wider mb-1">Check question</p>
              <p className="text-sm text-ink">{checkQ}</p>
            </div>
          )}

          <div className="flex gap-3">
            <input
              value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder={mode === 'answer' ? 'Type your answer…' : 'Ask a question…'}
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-xl border border-greige-border bg-white text-ink text-sm focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20 transition-all disabled:opacity-60"
            />
            <button onClick={handleSend} disabled={loading || !input.trim()}
              className="px-5 py-3 rounded-xl bg-sage text-white font-semibold text-sm hover:bg-sage-dark transition-colors disabled:opacity-50">
              {mode === 'answer' ? 'Answer' : 'Send'}
            </button>
            {mode === 'answer' && (
              <button onClick={() => { setMode('question'); setCheckQ(null); }}
                className="px-4 py-3 rounded-xl border border-greige-border text-muted text-sm hover:bg-greige-accent transition-colors">
                Skip
              </button>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
