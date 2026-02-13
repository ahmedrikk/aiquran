# =====================================================
# AlQuran Cloud Backend - Dockerfile (Optimized)
# Multi-stage build with CPU-only PyTorch to keep
# the final image under Railway's 4GB limit.
# =====================================================

# --- Stage 1: Build (install deps + compile hnswlib) ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install C++ build tools needed by hnswlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch FIRST (~200MB vs ~2.5GB with CUDA)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies (sentence-transformers will see torch is already satisfied)
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Pre-download the embedding model so it's baked into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# --- Stage 2: Runtime (no gcc/g++, much smaller) ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded HuggingFace model
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Copy application code and data
COPY backend_cloud.py .
COPY quran_data/ ./quran_data/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

CMD uvicorn backend_cloud:app --host 0.0.0.0 --port ${PORT:-8000}
