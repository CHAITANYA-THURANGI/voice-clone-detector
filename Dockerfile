# Multi-stage lightweight deployment container for VoiceShield AI
# Fully compatible with Hugging Face Spaces (16GB RAM) and Render
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    WEB_CONCURRENCY=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    ENABLE_LOCAL_WHISPER=0

# Install system audio libraries and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000) for Hugging Face Spaces security requirements
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

# Install Python dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application source code
COPY --chown=user . .

# Expose service port (7860 for Hugging Face Spaces, dynamically overridden by $PORT on Render)
EXPOSE 7860

# Start FastAPI backend server and dashboard dynamically respecting $PORT
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --limit-concurrency 8"]
