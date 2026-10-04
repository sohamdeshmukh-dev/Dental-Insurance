# Dental Benefits — Web (React + Vite + TypeScript)

Single-page app in the Lincoln Financial brand (maroon `#650030` / orange `#FF4F17`,
Spectral + IBM Plex Sans). Views: **Ask the AI** (chat + in/out-network cost receipt),
**Dashboard** (funding through the year), **Rewards** (prototype loyalty program),
**Care Plan** (treatment tracker), and a full-screen **Provider Radar** (Mapbox).
Framer Motion drives the view transitions, count-ups, and chart/gauge animations.

## Run
```bash
cp .env.example .env.local   # add your Mapbox public token (VITE_MAPBOX_TOKEN)
npm install
npm run dev                  # http://localhost:5173
```
Point it at the backend with `VITE_API_BASE` (default `http://localhost:8000` in development, same-origin in production).
Every view falls back to embedded demo data when the backend isn't running.

## Build
```bash
npm run build && npm run preview
```

For Vercel, set `VITE_MAPBOX_TOKEN` to the public Mapbox token before building. The web service builds with `npm run build` and serves `dist/`; API requests use the same-origin routes in `vercel.json`.
