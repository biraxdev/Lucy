FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PORT=8000

# Install build tools and curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so layer caching helps rebuilds.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source and supporting agent tree.
COPY backend/ ./
COPY agent/ /app/agent

# Copy the container entrypoint and make it executable.
COPY scripts/backend-entrypoint.sh /app/scripts/backend-entrypoint.sh
RUN chmod +x /app/scripts/backend-entrypoint.sh

# Ensure the data directory exists for SQLite and reports.
RUN mkdir -p /app/data/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/scripts/backend-entrypoint.sh"]
