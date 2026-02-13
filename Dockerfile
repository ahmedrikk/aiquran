# =====================================================
# AlQuran Cloud Backend - Dockerfile (Lightweight)
# No PyTorch — uses ONNX Runtime for embeddings.
# Final image ~1-1.5GB instead of 8GB.
# =====================================================

# --- Stage 1: Build (compile hnswlib) ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# gcc/g++ needed to compile hnswlib C++ extension
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Pre-download the ONNX embedding model (~80MB)
RUN python -c "\
    from huggingface_hub import hf_hub_download; \
    hf_hub_download('sentence-transformers/all-MiniLM-L6-v2', 'onnx/model.onnx'); \
    hf_hub_download('sentence-transformers/all-MiniLM-L6-v2', 'tokenizer.json')"

# --- Stage 2: Runtime (no build tools) ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded HuggingFace model cache
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Copy application code and data
COPY backend_cloud.py .
COPY embeddings.py .
COPY quran_data/ ./quran_data/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

CMD uvicorn backend_cloud:app --host 0.0.0.0 --port ${PORT:-8000}
