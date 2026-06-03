FROM python:3.12-slim

WORKDIR /app

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /usr/local/bin/uv

# Configure uv for production
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies only (cached unless lock files change)
RUN uv sync --locked --no-dev

# Copy application code
COPY app ./app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
