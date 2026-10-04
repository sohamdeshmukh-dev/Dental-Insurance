# syntax=docker/dockerfile:1

# ----------------------------------------------------------------------------
# Lincoln Dental Connect — single-container image.
# Stage 1 builds the React/Vite frontend; stage 2 runs FastAPI, which also
# serves the built frontend. One port, one URL (mirrors the Vercel routing).
#
# Build (pass your Mapbox PUBLIC token so the map renders):
#   docker build -t dental-connect --build-arg VITE_MAPBOX_TOKEN=pk.xxx .
# Run:
#   docker run -p 8000:8000 dental-connect            # open http://localhost:8000
# Optional AWS Bedrock agent:
#   docker run -p 8000:8000 -e BEDROCK_MODEL_ID=... -e AWS_REGION=us-east-1 \
#              -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... dental-connect
# ----------------------------------------------------------------------------

# ---------- Stage 1: build the frontend ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
# Public Mapbox token is baked in at build time (safe for client code). Empty
# API base => the app calls /api/... on the same origin that serves this image.
ARG VITE_MAPBOX_TOKEN=""
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
ENV VITE_API_BASE=""
RUN npm run build

# ---------- Stage 2: FastAPI runtime (serves API + built frontend) ----------
FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    FRONTEND_DIST=/app/apps/api/static

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY apps/api/ ./apps/api/
COPY --from=web /web/dist ./apps/api/static

WORKDIR /app/apps/api
EXPOSE 8000
# Shell form so $PORT (set by most hackathon hosts) is honored at runtime.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
