# NeuroLearn API
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install CPU-only torch before requirements.txt. Plain `pip install torch`
# resolves to the CUDA build (~2.5 GB of GPU libraries this project never
# uses); pinning the CPU index first means the requirements install finds torch
# already satisfied.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bake the sentence-transformers embedding model into the image. Without this
# the first request downloads ~500 MB, so a fresh `compose up` would appear to
# hang and would need network access at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

# Runtime directories. The app opens sqlite at ./data/neurolearn.db on startup
# and fails outright if the directory is missing.
RUN mkdir -p data vectorstore checkpoints

EXPOSE 8000

# Generous start period: the first health probe initializes the retriever and
# loads the embedding model.
HEALTHCHECK --interval=15s --timeout=10s --start-period=120s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()" || exit 1

CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8000"]
