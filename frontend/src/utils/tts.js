const BASE = 'http://localhost:8000';

function base64ToArrayBuffer(b64) {
  const chars = atob(b64);
  const buf = new Uint8Array(chars.length);
  for (let i = 0; i < chars.length; i++) buf[i] = chars.charCodeAt(i);
  return buf.buffer;
}

function concatWavs(buf1, buf2) {
  const pcm1 = new Uint8Array(buf1, 44);
  const pcm2 = new Uint8Array(buf2, 44);
  const combined = new Uint8Array(pcm1.length + pcm2.length);
  combined.set(pcm1, 0);
  combined.set(pcm2, pcm1.length);

  // Rebuild WAV header: 24000 Hz, 16-bit, mono
  const sr = 24000, bps = 16, ch = 1;
  const ds = combined.length;
  const h = new ArrayBuffer(44);
  const dv = new DataView(h);
  dv.setUint32(0, 0x52494646, false);  // RIFF
  dv.setUint32(4, 36 + ds, true);
  dv.setUint32(8, 0x57415645, false);  // WAVE
  dv.setUint32(12, 0x666d7420, false); // fmt
  dv.setUint32(16, 16, true);
  dv.setUint16(20, 1, true);           // PCM
  dv.setUint16(22, ch, true);
  dv.setUint32(24, sr, true);
  dv.setUint32(28, sr * ch * (bps / 8), true);
  dv.setUint16(32, ch * (bps / 8), true);
  dv.setUint16(34, bps, true);
  dv.setUint32(36, 0x64617461, false); // data
  dv.setUint32(40, ds, true);

  const out = new Uint8Array(44 + ds);
  out.set(new Uint8Array(h), 0);
  out.set(combined, 44);
  return out.buffer;
}

function bufToUrl(buf) {
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
}

async function ttsRequest(body) {
  const token = localStorage.getItem('access_token');
  const res = await fetch(`${BASE}/api/story/tts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `TTS failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Stream TTS in 3 parts (first → second → rest).
 * onUpdate(blobUrl, statusText) called after each part is ready.
 * Returns when all three parts are done.
 */
export async function streamTTS(text, onUpdate) {
  try {
    onUpdate(null, 'Generating audio...');

    const first = await ttsRequest({ text, part: 'first', split_offset: 0 });
    let mergedBuf = base64ToArrayBuffer(first.audioContent);
    onUpdate(bufToUrl(mergedBuf), 'Playing (loading more...)');

    const second = await ttsRequest({ text, part: 'second', split_offset: first.splitOffset || 0 });
    mergedBuf = concatWavs(mergedBuf, base64ToArrayBuffer(second.audioContent));
    onUpdate(bufToUrl(mergedBuf), 'Playing (almost ready...)');

    const rest = await ttsRequest({ text, part: 'rest', split_offset: second.splitOffset || 0 });
    mergedBuf = concatWavs(mergedBuf, base64ToArrayBuffer(rest.audioContent));
    onUpdate(bufToUrl(mergedBuf), 'Full audio ready');
  } catch (e) {
    onUpdate(null, `Audio error: ${e.message}`);
  }
}

export function speakText(text, lang = 'ml-IN', rate = 0.9) {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = rate;
    window.speechSynthesis.speak(u);
  } catch (e) {
    console.warn('Speech synthesis failed:', e);
  }
}

export const PROFILE_MAP = (profile) => ({
  child_name: profile.full_name || '',
  child: profile.full_name || '',
  full_name: profile.full_name || '',
  mother_name: profile.mother_name || '',
  father_name: profile.father_name || '',
  grandmother_name: profile.grandmother_name || '',
  grandfather_name: profile.grandfather_name || '',
  favorite_color: profile.favorite_color || '',
  favorite_food: profile.favorite_food || '',
  favorite_animal: profile.favorite_animal || '',
  favorite_interest: profile.favorite_interest || '',
  teacher_name: profile.teacher_name || '',
  place: profile.place || '',
  friends: profile.friends || '',
  friend_name: (profile.friends || '').split(',')[0]?.trim() || '',
  age: profile.age ? String(profile.age) : '',
  interests: Array.isArray(profile.interests) ? profile.interests.join(', ') : (profile.interests || ''),
});

// Fixed set of allowed placeholder fields (display order)
export const ALLOWED_PLACEHOLDERS = [
  { key: 'child_name',        label: 'Child Name' },
  { key: 'place',             label: 'Place' },
  { key: 'favorite_interest', label: 'Favorite Interest' },
  { key: 'mother_name',       label: 'Mother Name' },
  { key: 'favorite_color',    label: 'Favorite Color' },
  { key: 'teacher_name',      label: 'Teacher Name' },
  { key: 'father_name',       label: 'Father Name' },
];

// Normalise a raw placeholder variable string to a clean key
export function normPlaceholderKey(v) {
  return v.replace(/[{}]/g, '').trim();
}

// Filter out garbage/non-latin placeholder keys
export function isValidPlaceholderKey(key) {
  return /^[a-z_]+$/.test(key);
}
