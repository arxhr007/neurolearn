"""Groq-backed LLM service."""

import os
import sys
import time

from groq import Groq

from langgraph_app.config import GROQ_MODEL, SYSTEM_PROMPT


class MalayalamLLM:
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
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\\n{doc['text']}"
            )
        context_block = "\\n\\n".join(context_parts)

        user_prompt = f"Context:\\n{context_block}\\n\\nQuestion: {question}\\n\\nAnswer in Malayalam:"

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
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

