# Deployment and submission checklist

## 0. Before anything: real data

```bash
cd backend
pip install -r requirements-dev.txt
python scripts/fetch_data.py
ls -la data/            # actuals.json + forecasts.json must exist
pytest -q               # 33 passed
```

If `fetch_data.py` returns zero rows, open the Elexon docs pages for the two endpoints and
compare the query-parameter names with `app/elexon_client.py` (`settlementDateFrom/To` +
`fuelType` for FUELHH; `publishDateTimeFrom/To` for WINDFOR). Adjust and re-run.

Sanity-check the snapshot:

```bash
python - <<'EOF'
import json; a=json.load(open('data/actuals.json')); f=json.load(open('data/forecasts.json'))
print(len(a), 'actuals', a[0], a[-1]); print(len(f), 'forecasts', len({r[1] for r in f}), 'runs')
EOF
```

Expect ~1,536 actuals (32 days × 48) and many forecast runs.

## 1. GitHub repo (anonymous name)

```bash
cd <repo root>
git init && git add -A && git commit -m "Wind forecast monitor"
gh repo create kjhwr --public --source=. --push     # or any random string
```

Make sure your Git author name/email are not identifying if that matters to you
(`git config user.name`).

## 2a. Vercel (recommended, one project for UI + API)

1. `npm i -g vercel && vercel login`
2. From the repo root: `vercel` → accept defaults (it reads `vercel.json`), then `vercel --prod`.
3. Open `https://<project>.vercel.app/api/meta` — you should see JSON with `"source": "snapshot"`.
4. Open the root URL; both tabs should load within a second.

If the Python function fails to find `backend/`, check the Vercel build log; `includeFiles` in
`vercel.json` must point at `backend/**`. Alternative: Vercel supports Docker-less Python only, so
if packaging misbehaves, use Heroku/Render (below) for the API and set `VITE_API_BASE` on the
Vercel frontend to that URL (and `CORS_ORIGINS` on the API to the Vercel URL).

## 2b. Heroku (Docker)

```bash
heroku login
heroku create <random-name> --stack container
git push heroku main
heroku open
```

`heroku.yml` builds the Dockerfile; the container serves UI + API on `$PORT`.

## 3. Video (unlisted YouTube, ≤10 min)

Script in `docs/VIDEO_SCRIPT.md`. Record with OBS / Loom / QuickTime at 1080p; show the deployed
URL, not localhost. Upload → Visibility **Unlisted** (not Private).

## 4. Verify in an incognito window

- [ ] YouTube link plays without signing in
- [ ] GitHub repo opens, README renders, no personal name in repo name
- [ ] App URL loads, both tabs work, `/api/meta` returns JSON
- [ ] README's "Live app" line updated with the real URL

## 5. Submit the form

Video link, repo link, app link.
