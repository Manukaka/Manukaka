# Deploying Satya

## Backend

The backend is a stateless FastAPI app — host it anywhere that runs a container
or a Python process. A `Dockerfile` is provided.

### Environment

Set these on the host (see `backend/.env.example`):

- `ANTHROPIC_API_KEY` — **required**, kept server-side only.
- `SATYA_MODEL` (default `claude-opus-4-8`), `SATYA_EFFORT`, `SATYA_MAX_TOKENS`.
- `SATYA_CORS_ORIGINS` — lock to your app/site origins in production.
- `SATYA_CACHE_TTL_HOURS` — how long a viral-forward verdict stays cached.

### Container

```bash
cd satya
docker build -t satya-backend -f backend/Dockerfile backend   # build context = backend/
# (the Dockerfile also needs ../shared; build from satya/ if you prefer:)
docker build -t satya-backend -f backend/Dockerfile .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... satya-backend
```

### Hosting options

| Option | Notes |
|---|---|
| Render / Railway / Fly.io | Push the repo, set env vars, expose port 8000. Easiest. |
| A VPS + Caddy/Nginx | `uvicorn` behind a reverse proxy with TLS. Most control. |
| Cloud Run / Container Apps | Scales to zero; good for spiky traffic. |

Put it behind HTTPS and add rate limiting (per-IP) before public launch. The
in-process SQLite cache is fine for one instance; for multiple instances move
the cache to Redis (a drop-in for `app/cache.py`).

## App (Play Store)

1. `cd app && flutter create . && flutter pub get`.
2. Set `applicationId = com.satya.app` and a release `versionCode`/`versionName`
   in `android/app/build.gradle`.
3. Point the app at the deployed backend (Settings, or bake the URL into
   `ApiClient.defaultBaseUrl`). Use **https** in production.
4. Build a signed release:
   ```bash
   flutter build appbundle --release
   ```
5. Create the Play Console listing: app name **Satya**, a privacy policy URL
   (checks are stored on-device; uploaded content is used only to fact-check),
   screenshots, and the data-safety form.

## Pre-launch checklist

- [ ] HTTPS on the backend; CORS locked down.
- [ ] Per-IP rate limiting / basic abuse protection.
- [ ] Privacy policy published and linked.
- [ ] Disclaimer visible on results ("based on available evidence").
- [ ] Spot-check verdicts across parties/topics for neutrality.
