# TheHub PRII Federation — MCP API image.
# Serves the hosted MCP router (server/backend/mcp_api.py) plus the existing
# entity API via uvicorn. Build from the repo root:
#   docker build -t thehub-mcp .
#   docker run --rm -p 8000:8000 thehub-mcp
FROM python:3.11-slim

# System deps: git is used by the github-bridge live `fetch` action.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install first with just the metadata for better layer caching, then the code.
COPY pyproject.toml README.md ./
COPY src ./src
COPY server ./server
COPY packages ./packages
COPY registry ./registry
COPY schemas ./schemas
COPY mcp ./mcp
COPY tools ./tools
COPY data ./data

RUN pip install --no-cache-dir -e ".[server]"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness — the MCP API's /healthz.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else sys.exit(1)"

CMD ["uvicorn", "server.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
