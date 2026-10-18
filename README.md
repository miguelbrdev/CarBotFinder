# CarBotFinder

[![ci](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/ci.yml)
[![scan](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/scan.yml/badge.svg)](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/scan.yml)

Watches the main Spanish used-car portals and sends you a **Telegram message within minutes**
when a new listing matches your filters: make and model, year range, max price, max mileage,
excluded provinces (islands by default), private sellers and/or dealers.

Runs **for free, 24/7, on GitHub Actions**. No server, no credit card, no browser automation.

```
🚗 Mazda MX-5 1.8 Active
💶 10.900 €  ·  📅 2008  ·  🛣 157.295 km
📍 Manises (Valencia)  ·  👤 particular  ·  cochesnet
🔗 https://www.coches.net/mazda-mx-5-active-18-...aspx
```

*(Versión en español más abajo.)*

## Portals

| Portal | Source of data | Notes |
|---|---|---|
| [Wallapop](https://es.wallapop.com) | internal JSON search API | mostly private sellers, best prices |
| [coches.net](https://www.coches.net) | internal JSON gateway | biggest volume, filters applied server-side |
| [milanuncios](https://www.milanuncios.com) | server-rendered page state | private sellers |
| [AutoScout24.es](https://www.autoscout24.es) | Next.js page data | filters and sorting in the URL |
| [coches.com](https://www.coches.com) | Next.js page data | mostly dealers |
| [Autocasión](https://www.autocasion.com) | HTML cards | dealers |

Every portal is a thin `fetch` over a pure `parse` function that is unit-tested against a trimmed,
anonymised copy of a real response (`tests/fixtures/`). One request per portal per scan.

## How it works

```
config.yaml ──▶ runner ──▶ portal.fetch() ──▶ parse() ──▶ Listing (normalised)
                  │                                           │
                  │             filters.check() ◀─────────────┘
                  │                  │ match
                  ▼                  ▼
            state (SQLite) ◀── seen before? ──no──▶ Telegram sendMessage
```

- **Filtering is always done locally**, even when a portal also accepts the filter in its URL
  (portal filters are only an optimisation; some ignore them).
- **De-duplication** by `(portal, id)` in a SQLite file. On GitHub Actions the file survives
  between runs through the Actions cache.
- **Seed mode**: on the first run (empty state) only ads published in the last 2 hours are sent;
  everything else is silently marked as seen, so you do not get hundreds of messages.
- **Failure isolation**: a broken portal never stops the others. After 3 consecutive failures
  you get one Telegram warning (at most every 6 h).

## Deploy on GitHub Actions (free)

1. **Create a Telegram bot**: talk to [@BotFather](https://t.me/BotFather), `/newbot`, copy the token.
   Then open a chat with your new bot and press *Start*.
2. **Get your chat id**: message [@userinfobot](https://t.me/userinfobot) (or call
   `https://api.telegram.org/bot<TOKEN>/getUpdates` after writing to your bot).
3. **Fork or push this repository** (public repositories get unlimited Actions minutes).
4. Edit `config.yaml` with your searches (see [Configuration](#configuration)) and commit. Check it
   locally first with `uv run carbotfinder run --dry-run --no-seed --state /tmp/x.sqlite -vv`: a portal
   reporting `fetched=0` spells the make or model differently.
5. In the repository go to *Settings → Secrets and variables → Actions* and add
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
6. Open the *Actions* tab. On a fork GitHub keeps workflows disabled until you enable them there.
7. *Actions → probe portals → Run workflow* prints which portals answer from GitHub's IPs. If one is
   blocked, drop it from the `--portal` list in `.github/workflows/scan.yml`.
8. *Actions → scan → Run workflow* with **seed = true** once. From then on you only receive
   genuinely new ads.
9. **Set up the external trigger** (below). Without it GitHub runs the scan only a few times a day.

### External trigger (required for a real cadence)

GitHub's `schedule` is best effort. Measured on a fresh repository (2026-10-17/18): a `*/5` cron ran
**4 times in 13 hours**. So the workflow keeps a `*/10` schedule only as a backup, and the real
cadence comes from a free [cron-job.org](https://cron-job.org) job that triggers `workflow_dispatch`:

1. GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token*. Repository access: only this repo. Permission: **Actions: Read and write**.
2. cron-job.org → *Create cronjob*:
   - URL: `https://api.github.com/repos/<you>/CarBotFinder/actions/workflows/scan.yml/dispatches`
   - Schedule: every 10-15 minutes (5 if you want; keep the request volume to the portals in mind).
   - *Advanced*: request method **POST**; request body `{"ref":"main"}`; headers
     `Authorization: Bearer <token>` (the word `Bearer` matters), `Accept: application/vnd.github+json`,
     `Content-Type: application/json`, `User-Agent: carbotfinder-cron`.
3. *Run now* on cron-job.org: a `scan` run labelled "Manually run" appears in *Actions* within a
   minute. A 404 from GitHub means the token lacks access to the repo; a 422 means the body is wrong.

The workflow's `concurrency` group makes overlapping triggers queue instead of racing on the state.
Scheduled workflows are disabled after 60 days without commits; the external trigger is not affected.

### Other caveats
- **milanuncios and Autocasión return 403 to GitHub's IP ranges** (checked 2026-10-17), so `scan.yml`
  only runs the other four portals (`--portal ...`). Both work from a residential connection: run
  `carbotfinder run --portal milanuncios --portal autocasion --interval 300` at home (below) to cover
  them. State is per machine, and the portals do not overlap, so you get no duplicate alerts.
- If another portal starts failing from Actions, remove it from the `--portal` list in `scan.yml`
  or run the bot at home.

## Run at home (PC, Raspberry Pi, NAS)

```bash
pip install uv
uv sync
cp .env.example .env            # bot token + chat id
uv run carbotfinder run --dry-run       # one pass, prints matches, sends nothing
uv run carbotfinder run --seed          # first real run
uv run carbotfinder run --interval 120  # keep scanning every 2 minutes
```

On Windows, `scripts/` has ready-made launchers for the portals that block GitHub's IPs:

- `scripts\start-home-scan.bat` opens a window that scans milanuncios and Autocasión every 5 minutes
  (pass other `--portal` arguments to override) and remembers its PID.
- `scripts\stop-home-scan.bat` stops that window. Closing it or pressing Ctrl+C works too.
- `scripts\home-scan-window.bat` is the script that runs inside the window; double-click it to run
  in the foreground.
- `scripts\refresh-home-scan.bat` does a single pass and exits: a manual refresh.

Or with Docker:

```bash
docker compose up -d --build     # reads .env, keeps state in ./state
```

## Configuration

See `config.example.yaml`. A search looks like:

```yaml
searches:
  - name: mx5-nc
    make: Mazda
    model: MX-5
    year_min: 2005
    year_max: 2015
    price_max: 14000
    km_max: 180000
    title_exclude: []            # whole-word matches, e.g. ["NA", "NB", "ND"]
    seller_types: [private, dealer]
    portals: [wallapop, cochesnet, milanuncios, autoscout24, cochescom, autocasion]
```

Province names are normalised (accents stripped, lower-case), so `Illes Balears`, `Baleares` and
`Palma de Mallorca` all count as the same excluded province. Ads whose portal does not state a
price are dropped; ads without year or mileage are kept (better a look than a miss).

## Development

```bash
uv sync
uv run pytest --cov --cov-report=term-missing
uv run ruff check . && uv run ruff format --check .
uv run mypy carbotfinder
uv run carbotfinder run --dry-run --no-seed --state /tmp/x.sqlite -vv   # live, verbose
```

Adding a portal: implement `Portal` in `carbotfinder/portals/<name>.py` (a `parse()` that takes
the raw response and a `fetch()` that performs one request), register it with `@register`, add
the name to `ALL_PORTALS` in `config.py`, drop a trimmed fixture in `tests/fixtures/` and a test.

## Responsible use

This tool is for personal use: it makes roughly one request per portal every few minutes, sends
a browser-like `User-Agent`, never bypasses CAPTCHAs or authentication, and does not store or
redistribute listing data beyond the ids it has already notified. Check each portal's terms of
service before using it, and keep the request volume low.

## Español

Bot que vigila los principales portales de coches de segunda mano de España (Wallapop,
coches.net, milanuncios, AutoScout24, coches.com y Autocasión) y te avisa por **Telegram en
pocos minutos** cuando aparece un anuncio que cumple tus filtros: marca y modelo, rango de años,
precio máximo, kilómetros máximos, provincias excluidas (por defecto las islas) y tipo de
vendedor.

Funciona **gratis y 24/7 en GitHub Actions**, sin servidor ni tarjeta. milanuncios y Autocasión bloquean
las IPs de GitHub; para cubrirlos desde casa (Windows) usa `scripts\start-home-scan.bat` y
`scripts\stop-home-scan.bat`. Para desplegarlo:

1. Crea un bot en Telegram con [@BotFather](https://t.me/BotFather) y copia el token. Abre un chat
   con tu bot y pulsa *Start*.
2. Consigue tu `chat_id` escribiendo a [@userinfobot](https://t.me/userinfobot).
3. Haz un fork (o sube el repo a un repositorio público tuyo).
4. Edita `config.yaml` con tus búsquedas y pruébalo en local con
   `uv run carbotfinder run --dry-run --no-seed --state /tmp/x.sqlite -vv`.
5. Añade los secretos `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en
   *Settings → Secrets and variables → Actions*.
6. Entra en la pestaña *Actions* y habilita los workflows (en un fork vienen desactivados).
   Lanza *probe portals* para ver qué portales responden desde GitHub.
7. Lanza una vez *Actions → scan → Run workflow* con **seed = true**. A partir de ahí solo te
   llegan anuncios nuevos.
8. El cron de GitHub es poco fiable (medido: 4 ejecuciones en 13 horas). Crea un job gratuito en
   [cron-job.org](https://cron-job.org) que dispare el workflow cada 10-15 minutos; los pasos exactos
   están en la sección *External trigger* de arriba.

El plan de desarrollo y la investigación de cada portal están en `docs/PLAN.md`.
