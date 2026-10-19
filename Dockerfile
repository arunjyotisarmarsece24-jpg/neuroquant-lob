# ==============================================================================
# NeuroQuant-LOB Enterprise Multi-Stage Dockerfile
# Stage 1: High-Performance C++20 AVX2 SIMD Compilation
# Stage 2: Hardened Lightweight Python Production Runtime
# Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
# Version: 1.1.0-PROD
# ==============================================================================

# ------------------------------------------------------------------------------
# STAGE 1: C++20 AVX2 SIMD Core Builder
# ------------------------------------------------------------------------------
FROM gcc:13-bookworm AS builder

WORKDIR /build

# Copy C++ source files
COPY csrc/ /build/csrc/

# Compile shared library with aggressive AVX2, FMA, and C++20 optimizations
RUN g++ -std=c++20 -O3 -mavx2 -mfma -shared -fPIC \
    -DNDEBUG -march=x86-64-v3 -Wall -DLIF_EXPORTS \
    /build/csrc/lif_core.cpp \
    /build/csrc/itch_parser.cpp \
    /build/csrc/almgren_chriss_simd.cpp \
    -o /build/lif_core.so

# ------------------------------------------------------------------------------
# STAGE 2: Hardened Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL maintainer="Arunjyoti Sarma <arunjyotisarmarsece24@gmail.com>" \
      description="NeuroQuant-LOB Digital Neuromorphic Spiking Engine & HFT Execution Core" \
      version="1.1.0-PROD"

WORKDIR /app

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEUROQUANT_ENV=production \
    SIMD_MODE=AVX2 \
    PORT=5000

# Install minimal runtime dependencies (OpenMP runtime, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled C++20 AVX2 SIMD binary from Stage 1
COPY --from=builder /build/lif_core.so /app/csrc/lif_core.so

# Copy Python dependency manifests first for maximum Docker layer caching
COPY requirements.txt pyproject.toml setup.py /app/

# Install Python production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application codebase
COPY . /app/

# Install neuroquant package in editable mode for unified CLI binary access
RUN pip install --no-cache-dir -e .

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Expose Web Dashboard & Mobile PWA port
EXPOSE 5000

# Enterprise healthcheck probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/telemetry || exit 1

# Container entrypoint with automated AVX2 SIMD self-tests
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command: launch unified terminal & companion web app
CMD ["neuroquant", "app", "--host", "0.0.0.0", "--port", "5000", "--no-browser"]
