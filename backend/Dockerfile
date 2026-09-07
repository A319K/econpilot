# EconPilot backend — API + watcher/scheduler.
#
# This image runs the discovery/tracking/watcher services. It deliberately does
# NOT install the `agent` extra: the form-filling agent needs a headed browser
# on the user's desktop and is not dockerized (see the README "Docker" section).
#
# Build context is the REPO ROOT (see docker-compose.yml) so the image can
# include the example profile/company configs used as fallbacks:
#     docker build -f backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies first for better layer caching.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir -e .

# Migrations, config, and seed scripts.
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/scripts ./scripts

# Example configs land at the container repo-root (`/`) so profile.yaml /
# companies.yaml fallbacks resolve even before the user mounts real ones.
COPY profile.example.yaml companies.example.yaml /

# Data (sqlite db + generated PDFs) lives on a mounted volume; see compose.
ENV DATABASE_URL=sqlite:////data/econpilot.db \
    OUTPUT_DIR=/data/output

EXPOSE 8000

# Run migrations, then serve single-process.
CMD ["sh", "-c", "mkdir -p /data/output && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
