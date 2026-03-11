"""
Malayalam Voice RAG System
===========================
1. Listens for Malayalam voice input (microphone via sounddevice)
2. Transcribes speech → Malayalam text (Google Speech Recognition)
3. Queries the ChromaDB vector store for relevant chunks
4. Sends context + question to Google Gemini for a Malayalam answer
5. Displays the answer AND speaks it back in Malayalam (gTTS)

Usage:
    python voice_rag.py                              # interactive voice mode
    python voice_rag.py --text "നിങ്ങളുടെ ചോദ്യം"    # text mode, single query
    python voice_rag.py --mode text                  # interactive text mode

Prerequisites:
    - GROQ_API_KEY env variable (for Groq)
    - ChromaDB index built via build_index.py
    - Microphone for voice mode
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
from groq import Groq
from gtts import gTTS
import numpy as np
import sounddevice as sd
import speech_recognition as sr


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_DB_DIR = "./vectorstore"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GROQ_MODEL = "openai/gpt-oss-120b"
TOP_K = 5  # number of chunks to retrieve

SYSTEM_PROMPT = """You are a helpful assistant that answers questions in Malayalam.
You will be given context passages extracted from Malayalam educational documents.
Use ONLY the provided context to answer the question. If the context does not
contain enough information, say so honestly in Malayalam.

Rules:
- Always reply in Malayalam script (Unicode).
- Be concise and accurate.
- Cite which source document the information comes from when possible.
- If the question is in Malayalam, answer in Malayalam.
- If the question is in English, still answer in Malayalam but you may include
  the English term in parentheses for clarity."""


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
class RAGRetriever:
    """Wraps ChromaDB for retrieval."""

    def __init__(self, db_dir: str, model_name: str):
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        client = chromadb.PersistentClient(path=db_dir)
        self.collection = client.get_collection(
            name="malayalam_rag",
            embedding_function=ef,
        )
        print(f"[RAG] Loaded collection with {self.collection.count()} chunks")

    def query(self, question: str, top_k: int = TOP_K) -> list[dict]:
        results = self.collection.query(
            query_texts=[question],
            n_results=top_k,
        )
        docs = []
        for i in range(len(results["ids"][0])):
            docs.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "page": results["metadatas"][0][i]["page"],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return docs


# ---------------------------------------------------------------------------
# LLM (Groq API)
# ---------------------------------------------------------------------------
class MalayalamLLM:
    """Wraps Groq for Malayalam generation."""

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("ERROR: Set the GROQ_API_KEY environment variable.")
            print("  Get a free key at https://console.groq.com/keys")
            sys.exit(1)
        self.client = Groq(api_key=api_key)
        print(f"[LLM] Using Groq model: {GROQ_MODEL}")

    def generate(self, question: str, context_docs: list[dict]) -> str:
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\n{doc['text']}"
            )
        context_block = "\n\n".join(context_parts)

        user_prompt = f"Context:\n{context_block}\n\nQuestion: {question}\n\nAnswer in Malayalam:"

        # Retry with exponential backoff for rate-limit errors
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10  # 10s, 20s, 40s, 80s
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries. Wait a minute and try again.")


# ---------------------------------------------------------------------------
# Speech-to-Text (sounddevice-based, no PyAudio needed)
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.02  # RMS below this = silence
SILENCE_DURATION = 2.0    # seconds of silence before stopping
MAX_RECORD_SECONDS = 30


class MalayalamSTT:
    """Microphone -> Malayalam text using sounddevice + Google Speech Recognition."""

    def __init__(self):
        self.recognizer = sr.Recognizer()

    def _record_until_silence(self) -> Optional[np.ndarray]:
        """Record from mic until silence is detected, return audio as numpy array."""
        print("[MIC] Listening... (speak in Malayalam, silence to stop)")
        chunks = []
        silent_chunks = 0
        chunk_duration = 0.1  # seconds per chunk
        samples_per_chunk = int(SAMPLE_RATE * chunk_duration)
        max_chunks = int(MAX_RECORD_SECONDS / chunk_duration)
        silence_count_limit = int(SILENCE_DURATION / chunk_duration)
        started_speaking = False

        for _ in range(max_chunks):
            audio_chunk = sd.rec(
                samples_per_chunk, samplerate=SAMPLE_RATE,
                channels=1, dtype="float32",
            )
            sd.wait()
            rms = np.sqrt(np.mean(audio_chunk ** 2))

            if rms > SILENCE_THRESHOLD:
                started_speaking = True
                silent_chunks = 0
                chunks.append(audio_chunk)
            else:
                if started_speaking:
                    chunks.append(audio_chunk)
                    silent_chunks += 1
                    if silent_chunks >= silence_count_limit:
                        break

        if not chunks:
            print("[MIC] No speech detected.")
            return None

        return np.concatenate(chunks)

    def _numpy_to_audio_data(self, audio: np.ndarray) -> sr.AudioData:
        """Convert numpy float32 array to speech_recognition AudioData."""
        pcm = (audio * 32767).astype(np.int16)
        raw_bytes = pcm.tobytes()
        return sr.AudioData(raw_bytes, SAMPLE_RATE, 2)  # 2 bytes per sample (16-bit)

    def listen(self) -> Optional[str]:
        """Record from microphone and return transcribed Malayalam text."""
        audio = self._record_until_silence()
        if audio is None:
            return None

        print("[MIC] Recognising speech...")
        audio_data = self._numpy_to_audio_data(audio)

        try:
            text = self.recognizer.recognize_google(audio_data, language="ml-IN")
            return text
        except sr.UnknownValueError:
            print("[MIC] Could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"[MIC] Speech recognition service error: {e}")
            return None


# ---------------------------------------------------------------------------
# Text-to-Speech (gTTS + Windows media playback)
# ---------------------------------------------------------------------------
class MalayalamTTS:
    """Malayalam text -> spoken audio using gTTS."""

    def __init__(self):
        self._temp_files: list[str] = []

    def speak(self, text: str) -> None:
        """Convert text to speech and play it."""
        if not text.strip():
            return
        try:
            tts = gTTS(text=text, lang="ml", slow=False)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_path = tmp.name
            tmp.close()
            tts.save(tmp_path)
            self._temp_files.append(tmp_path)

            if sys.platform == "win32":
                # Use Windows Media Player via PowerShell (blocks until done)
                ps_cmd = (
                    "Add-Type -AssemblyName PresentationCore; "
                    "$mp = New-Object System.Windows.Media.MediaPlayer; "
                    f"$mp.Open([Uri]::new('{tmp_path}')); "
                    "$mp.Play(); "
                    "Start-Sleep -Milliseconds 500; "
                    "while ($mp.Position -lt $mp.NaturalDuration.TimeSpan) "
                    "{ Start-Sleep -Milliseconds 200 }; "
                    "$mp.Close()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, timeout=120,
                )
            else:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", tmp_path],
                    capture_output=True, timeout=120,
                )
        except Exception as e:
            print(f"[TTS] Speech synthesis/playback failed: {e}")

    def cleanup(self):
        """Remove temp audio files."""
        for f in self._temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass
        self._temp_files.clear()


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------
def run_interactive(retriever: RAGRetriever, llm: MalayalamLLM,
                    stt: Optional[MalayalamSTT], tts: MalayalamTTS,
                    mode: str, top_k: int) -> None:
    """Run the interactive Q&A loop."""
    print("\n" + "=" * 60)
    print("  Malayalam Voice RAG System")
    print("  Mode:", "voice" if mode == "voice" else "text")
    print("  Say/type 'exit' or 'quit' to stop")
    print("=" * 60 + "\n")

    while True:
        # --- Get question ---
        if mode == "voice" and stt:
            question = stt.listen()
            if question is None:
                continue
            print(f"\n  Recognised: {question}")
        else:
            try:
                question = input("\n  Enter question (Malayalam/English): ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question:
                continue

        if question.lower() in ("exit", "quit", "stop", "bye"):
            print("\nExiting. Goodbye!")
            break

        # --- Retrieve ---
        print("\n  Searching knowledge base...")
        docs = retriever.query(question, top_k=top_k)
        if docs:
            print(f"   Found {len(docs)} relevant passages")
            for i, d in enumerate(docs, 1):
                dist_str = f" (distance: {d['distance']:.3f})" if d['distance'] is not None else ""
                print(f"   [{i}] {d['source']} p.{d['page']}{dist_str}")
        else:
            print("   No relevant passages found.")

        # --- Generate ---
        print("\n  Generating Malayalam answer...")
        try:
            answer = llm.generate(question, docs)
        except Exception as e:
            print(f"   LLM error: {e}")
            continue

        print(f"\n{'─' * 60}")
        print(f"  Answer:\n\n{answer}")
        print(f"{'─' * 60}")

        # --- Speak ---
        print("\n  Speaking answer...")
        tts.speak(answer)


def run_single_query(query: str, retriever: RAGRetriever, llm: MalayalamLLM,
                     tts: MalayalamTTS, top_k: int) -> None:
    """Run a single query (non-interactive)."""
    print(f"\n  Query: {query}")
    docs = retriever.query(query, top_k=top_k)
    print(f"  Retrieved {len(docs)} passages")

    answer = llm.generate(query, docs)
    print(f"\n{'─' * 60}")
    print(f"  Answer:\n\n{answer}")
    print(f"{'─' * 60}")

    print("\n  Speaking answer...")
    tts.speak(answer)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Malayalam Voice RAG System")
    parser.add_argument(
        "--mode",
        choices=["voice", "text"],
        default="voice",
        help="Input mode: 'voice' for microphone, 'text' for keyboard (default: voice)",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single question to answer (non-interactive mode)",
    )
    parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"ChromaDB directory (default: {DEFAULT_DB_DIR})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Embedding model name",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help=f"Number of chunks to retrieve (default: {TOP_K})",
    )
    args = parser.parse_args()

    # Initialise components
    print("Initialising components...")
    retriever = RAGRetriever(args.db_dir, args.model)
    llm = MalayalamLLM()
    tts = MalayalamTTS()

    stt = None
    if args.mode == "voice" and args.text is None:
        stt = MalayalamSTT()

    try:
        if args.text:
            run_single_query(args.text, retriever, llm, tts, args.top_k)
        else:
            run_interactive(retriever, llm, stt, tts, args.mode, args.top_k)
    finally:
        tts.cleanup()


if __name__ == "__main__":
    main()
