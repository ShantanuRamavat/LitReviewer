# =============================================================================
# Nexus Research — Backend Dockerfile
#
# Two-stage build:
#   builder  — installs uv and resolves/installs all Python dependencies
#   runtime  — copies only the virtual environment and app source; no build tools
#
# The runtime image is intentionally slim:
#   - No uv binary
#   - No pip / setuptools
#   - No compiler toolchain
#
# Build:  docker build -t nexus-backend .
# Run:    docker run --env-file .env -p 8000:8000 nexus-backend
# =============================================================================

# ---- Stage 1: dependency installation --------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy uv from the official image — avoids a separate curl/install step and
# pins to a specific version for reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /bin/uv

# UV_SYSTEM_PYTHON=0 keeps the venv isolated inside /build/.venv.
# UV_COMPILE_BYTECODE=1 pre-compiles .pyc files so startup is faster in prod.
ENV UV_SYSTEM_PYTHON=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency manifests first (before app source) so Docker can cache
# this layer and skip re-installing packages when only source files change.
COPY pyproject.toml uv.lock* ./

# Install runtime dependencies only — omit dev dependencies (pytest, ruff etc.)
# --no-install-project: don't install the project package itself, just its deps.
RUN uv sync --no-dev --no-install-project

# ---- Stage 2: runtime image ------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a non-root user to run the application.
# Running as root inside a container is a security anti-pattern.
RUN addgroup --system nexus && adduser --system --ingroup nexus nexus

# Copy the virtual environment from the builder stage.
COPY --from=builder /build/.venv /app/.venv

# Copy application source code.
COPY app/ ./app/

# Make the venv the active Python environment.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to the non-root user before the final CMD.
USER nexus

EXPOSE 8000

# Single worker for MVP — scale horizontally via multiple container replicas.
# --no-access-log reduces log noise; request logging is handled by structlog middleware.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log"]
