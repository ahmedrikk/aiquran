# =====================================================
# AlQuran Cloud Backend - Dockerfile
# =====================================================
# Build: docker build -t alquran-backend .
# Run:   docker run -p 8000:8000 --env-file .env alquran-backend
# =====================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for hnswlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy application code
COPY backend_cloud.py .

# Copy vector database and metadata
COPY quran_data/ ./quran_data/

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Start the server
CMD uvicorn backend_cloud:app --host 0.0.0.0 --port ${PORT:-8000}
