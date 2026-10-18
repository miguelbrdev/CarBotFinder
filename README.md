# CarBotFinder

[![ci](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/ci.yml)
[![scan](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/scan.yml/badge.svg)](https://github.com/miguelbrdev/CarBotFinder/actions/workflows/scan.yml)

Looking for a specific used car in Spain? CarBotFinder watches the main car portals for you and
sends you a **Telegram message within minutes** when a new ad matches what you want: make and
model, years, maximum price, maximum mileage, provinces to skip, private sellers and/or dealers.

It runs **for free, 24/7, on GitHub**. No server, no credit card, nothing to install on your
computer. Setting it up takes about 20 minutes in a web browser.

```
🚗 Mazda MX-5 1.8 Active
💶 10.900 €  ·  📅 2008  ·  🛣 157.295 km
📍 Manises (Valencia)  ·  👤 particular  ·  cochesnet
🔗 https://www.coches.net/mazda-mx-5-active-18-...aspx
```

*(Guía completa en español más abajo: [Guía en español](#guía-en-español).)*

---

## Quick start (no technical knowledge needed)

You need a Telegram account and a free [GitHub](https://github.com/signup) account. Everything
below happens in your browser.

### Step 1. Create your Telegram bot (2 min)

1. In Telegram, open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Give it a name (anything, e.g. `My car alerts`) and a username that must end in `bot`
   (e.g. `mycaralerts_bot`).
3. BotFather replies with a **token** that looks like `123456789:AAH4k...`. Copy it somewhere safe.
   This token is a password: anyone who has it can send messages as your bot.

### Step 2. Find your chat id (2 min)

The bot needs to know which Telegram chat to write to. That chat has a number, the *chat id*.

1. Open your new bot in Telegram (BotFather gives you a `t.me/...` link), press **Start** and send
   it any message, for example `hola`. The bot will not answer; that is normal.
2. In your browser open this address, replacing `TOKEN` with your token:
   `https://api.telegram.org/botTOKEN/getUpdates`
3. You will see some text. Look for `"chat":{"id":` followed by a number, e.g. `"id":1323873175`.
   That number is your **chat id**. Copy it.

If you see `"result":[]`, your message did not reach this bot: check that you wrote to the bot
with the exact username BotFather gave you, send another message and reload the page.

### Step 3. Make your own copy of this project (1 min)

Click the **Fork** button at the top right of this page and confirm. GitHub creates a copy of the
project in your account; that copy is what will run for you. Keep it public: public projects get
unlimited free execution time on GitHub.

### Step 4. Tell the bot what car you want (5 min)

In **your copy**, open the file `config.yaml`, click the pencil icon (*Edit this file*) and change
the search. You can have several searches; each one looks like this:

```yaml
searches:
  - name: mx5-nc              # any short name, shown in each message
    make: Mazda               # make, spelled as the portals spell it
    model: MX-5               # model, spelled as the portals spell it
    year_min: 2005            # delete a line you do not need
    year_max: 2015
    price_max: 14000          # euros
    km_max: 180000
    seller_types: [private, dealer]   # keep both, or only one of them
```

Other things you can set:

- `excluded_provinces: [baleares, las palmas, santa cruz de tenerife]` in the `defaults` block
  skips ads from those provinces (any spelling works: `Illes Balears`, `Baleares`...). By default
  nothing is excluded.
- `title_exclude: ["NA", "NB"]` drops ads whose title contains any of those words;
  `title_include: ["GTI"]` keeps only ads whose title contains one of them.

Click **Commit changes** when done. You can come back and edit this file whenever you want; the
next run uses the new filters.

### Step 5. Give your copy the bot's credentials (2 min)

In your copy go to **Settings → Secrets and variables → Actions → New repository secret** and
create two secrets:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from step 1 |
| `TELEGRAM_CHAT_ID` | the chat id from step 2 |

Paste the values without spaces before or after. Secrets are encrypted and nobody else can read
them, not even in a public project.

### Step 6. Start it (3 min)

1. Open the **Actions** tab of your copy. If GitHub asks, click *I understand my workflows, go
   ahead and enable them*.
2. In the left list click **scan**, then **Run workflow**. Tick **seed** and click the green
   **Run workflow** button.
3. Wait about a minute and refresh. The run must show a green tick. If it is red, open it and read
   the last lines: a wrong token or chat id is reported there in plain words (see
   [Troubleshooting](#troubleshooting)).

The first run with *seed* ticked remembers every ad that already exists so you do not get dozens
of old ads at once. From now on you only receive ads that appear after this moment.

### Step 7. Make it run every 15 minutes (5 min)

GitHub can run the bot on a timer, but its free timer is unreliable (in our tests it ran only a
few times a day). A free account on [cron-job.org](https://cron-job.org) fixes that by pressing the
"Run workflow" button for you every 15 minutes. It needs a key from GitHub so it is allowed to.

1. **Create the key**: in GitHub click your profile picture → **Settings** → **Developer settings**
   (bottom of the left menu) → **Personal access tokens** → **Fine-grained tokens** → **Generate new
   token**. Name it `carbotfinder-cron`, choose *No expiration* (or the longest allowed), under
   *Repository access* pick **Only select repositories** and select your copy, and under
   *Permissions → Repository permissions* set **Actions** to **Read and write**. Generate it and
   copy the key (it starts with `github_pat_`).
2. **Create the job** on cron-job.org (*Cronjobs → Create cronjob*):
   - *Title*: `CarBotFinder scan`.
   - *URL*: `https://api.github.com/repos/YOUR_GITHUB_USER/CarBotFinder/actions/workflows/scan.yml/dispatches`
     (replace `YOUR_GITHUB_USER` with your GitHub username).
   - *Schedule*: every 15 minutes.
   - Tab *Advanced*: *Request method* **POST**; *Request body* `{"ref":"main"}`; and four headers:

     | Header | Value |
     |---|---|
     | `Authorization` | `Bearer github_pat_...` (the word `Bearer`, a space, then your key) |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
     | `User-Agent` | `carbotfinder-cron` |
3. Click **Test run**: the response must be **204**. Then **Create**.

Done. From now on, every 15 minutes, GitHub checks the portals for you and you get a Telegram
message for each new ad that matches. Each message has the title, price, year, mileage, province,
seller type, portal and a link to the ad.

### Things to know

- **Two portals only work from a home connection.** milanuncios and Autocasión block requests
  coming from GitHub's servers. The other four (Wallapop, coches.net, AutoScout24, coches.com)
  work fine. If you also want those two, see [Run at home](#run-at-home-pc-raspberry-pi-nas).
- **To change the filters**, edit `config.yaml` in your copy again. **To pause the bot**, disable
  the job in cron-job.org. **To stop it for good**, delete the job and your copy of the project.
- **Keep the token and the key private.** If you think the bot token leaked, revoke it in
  BotFather (*/mybots → API Token → Revoke*) and update the secret.
- **Be reasonable with the frequency.** The bot makes one request per portal per run. Every 15
  minutes is plenty for a car search and keeps the portals happy.

---

## Technical reference

### Portals

| Portal | Source of data | Notes |
|---|---|---|
| [Wallapop](https://es.wallapop.com) | internal JSON search API | mostly private sellers, best prices |
| [coches.net](https://www.coches.net) | internal JSON gateway | biggest volume, filters applied server-side |
| [milanuncios](https://www.milanuncios.com) | server-rendered page state | private sellers; blocks datacenter IPs |
| [AutoScout24.es](https://www.autoscout24.es) | Next.js page data | filters and sorting in the URL |
| [coches.com](https://www.coches.com) | Next.js page data | mostly dealers; sorted newest first via `order[created_at]=desc` |
| [Autocasión](https://www.autocasion.com) | HTML cards | dealers; blocks datacenter IPs |

Every portal is a thin `fetch` over a pure `parse` function that is unit-tested against a trimmed,
anonymised copy of a real response (`tests/fixtures/`). One request per portal per scan, first
page, newest ads first.

### How it works

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
  everything else is silently marked as seen.
- **Credentials are checked at startup** (`getMe` + `getChat`), so a wrong token or chat id fails
  the run immediately with a clear message instead of silently never notifying.
- **Failure isolation**: a broken portal never stops the others. After 3 consecutive failures you
  get one Telegram warning (at most every 6 h).

### Run at home (PC, Raspberry Pi, NAS)

Useful for the portals that block GitHub's IPs, or if you prefer not to use GitHub at all.

```bash
pip install uv
uv sync
uv run carbotfinder setup-telegram      # finds your chat id, sends a test message, writes .env
uv run carbotfinder run --dry-run       # one pass, prints matches, sends nothing
uv run carbotfinder run --seed          # first real run
uv run carbotfinder run --interval 900  # keep scanning every 15 minutes
```

On Windows, `scripts/` has launchers that cover milanuncios and Autocasión alongside a GitHub
deployment (state is per machine and the portals do not overlap, so no duplicate alerts):

- `scripts\start-home-scan.bat` opens a window that scans those two portals every 5 minutes
  (pass other `--portal` arguments to override) and remembers its PID.
- `scripts\stop-home-scan.bat` stops that window. Closing it or pressing Ctrl+C works too.
- `scripts\refresh-home-scan.bat` does a single pass and exits: a manual refresh.
- `scripts\home-scan-window.bat` is what runs inside the window; double-click to run in the
  foreground.

Or with Docker:

```bash
docker compose up -d --build     # reads .env, keeps state in ./state
```

### Configuration reference

See `config.example.yaml`. All fields of a search:

| Field | Meaning |
|---|---|
| `name` | label shown in every message |
| `make`, `model` | as the portals spell them (`Mazda`, `MX-5`) |
| `year_min`, `year_max` | first registration year; ads without a year are kept |
| `price_min`, `price_max` | euros; ads without a price are dropped |
| `km_min`, `km_max` | ads without mileage are kept |
| `seller_types` | `private`, `dealer` or both |
| `include_reserved` | keep ads marked as reserved (default `false`) |
| `title_exclude`, `title_include` | whole-word, case-insensitive matches on the title |
| `portals` | override `defaults.portals` for this search |
| `excluded_provinces` | override `defaults.excluded_provinces` for this search |

`defaults` holds `excluded_provinces` (empty by default), `seed_window_hours` (2) and `portals`.
Province names are normalised (accents stripped, lower-case), and island provinces are recognised
under their usual spellings, postal codes and the portals' abbreviations.

### External trigger: why cron-job.org

GitHub's `schedule` is best effort. Measured on a fresh repository (2026-10-17/18): a `*/5` cron ran
**4 times in 13 hours**. The workflow keeps a `*/10` schedule only as a backup; the real cadence
comes from cron-job.org calling `workflow_dispatch` (steps in [Step 7](#step-7-make-it-run-every-15-minutes-5-min)).

- The workflow's `concurrency` group makes overlapping triggers queue instead of racing on the state.
- GitHub disables the backup `schedule` after 60 days without commits (it emails you a week before;
  *Actions → scan → Enable workflow* or any commit turns it back on). The external trigger is not
  affected.
- `scan.yml` passes `--portal` for the four portals that answer from GitHub's IPs. If one of them
  starts failing with 403, remove it from that list or run it at home. *Actions → probe portals*
  prints what answers from GitHub right now.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `getUpdates` shows `"result":[]` | Your message did not reach this bot | Write to the exact bot username BotFather gave you and reload |
| `getUpdates` shows `Not Found` / 404 | Token mistyped in the address (the word `bot` must be glued to the token) | Check the address: `.../bot123456:AAH.../getUpdates` |
| A run fails with `telegram rejected the bot token` | The `TELEGRAM_BOT_TOKEN` secret is wrong (often a stray character) | Update the secret with the token copied from BotFather |
| A run fails with `telegram getChat: chat not found` | Wrong `TELEGRAM_CHAT_ID`, or you never wrote to the bot | Redo step 2 and update the secret |
| `setup-telegram` waits and finds no message | You wrote to another bot with a similar name | Open the exact `t.me/<bot>` link it prints and send a message there |
| A portal reports `fetched=0` every time | That portal spells the make or model differently | Try the spelling the portal uses in its own URL; see `_SLUG_OVERRIDES` in that portal's module |
| `blocked (HTTP 403)` from GitHub Actions only | The portal rejects datacenter IPs | Run that portal at home, keep the rest on GitHub |
| `Pardon Our Interruption` from your own PC | Too many manual passes in a few minutes | Wait a while; one pass every few minutes is fine |
| cron-job.org shows 401 | `Authorization` header without the word `Bearer`, or wrong key | `Bearer <key>` |
| cron-job.org shows 404 | The key has no access to your copy or lacks *Actions: read and write* | Create the key again with those settings |
| cron-job.org shows 422 | Request body is not exactly `{"ref":"main"}` | Fix the body and the `Content-Type: application/json` header |
| No scheduled runs appear in *Actions* | GitHub's `schedule` is best effort | Use cron-job.org (step 7) |

### Development

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
See `CONTRIBUTING.md`.

### Responsible use

This tool is for personal use: it makes roughly one request per portal every few minutes, sends
a browser-like `User-Agent`, never bypasses CAPTCHAs or authentication, and does not store or
redistribute listing data beyond the ids it has already notified. Check each portal's terms of
service before using it, and keep the request volume low.

---

## Guía en español

CarBotFinder vigila los principales portales de coches de segunda mano de España (Wallapop,
coches.net, AutoScout24, coches.com, y desde casa también milanuncios y Autocasión) y te avisa
por **Telegram en pocos minutos** cuando aparece un anuncio que cumple tus filtros: marca y
modelo, años, precio máximo, kilómetros máximos, provincias que quieras evitar y tipo de vendedor.

Funciona **gratis y 24/7 en GitHub**, sin servidor, sin tarjeta y sin instalar nada en tu
ordenador. Montarlo lleva unos 20 minutos en el navegador. Necesitas una cuenta de Telegram y una
cuenta gratuita de [GitHub](https://github.com/signup).

### Paso 1. Crea tu bot de Telegram (2 min)

1. En Telegram abre [@BotFather](https://t.me/BotFather) y envía `/newbot`.
2. Ponle un nombre (el que quieras) y un usuario que termine en `bot` (por ejemplo `misalertascoche_bot`).
3. BotFather te responde con un **token** parecido a `123456789:AAH4k...`. Guárdalo: es una
   contraseña, quien lo tenga puede enviar mensajes como tu bot.

### Paso 2. Averigua tu chat id (2 min)

1. Abre tu bot en Telegram (BotFather te da un enlace `t.me/...`), pulsa **Iniciar** y escríbele
   cualquier cosa, por ejemplo `hola`. El bot no contesta; es normal.
2. En el navegador abre esta dirección, cambiando `TOKEN` por tu token:
   `https://api.telegram.org/botTOKEN/getUpdates`
3. Busca `"chat":{"id":` seguido de un número, por ejemplo `"id":1323873175`. Ese número es tu
   **chat id**.

Si ves `"result":[]`, tu mensaje no ha llegado a ese bot: comprueba que has escrito al usuario
exacto que te dio BotFather, escribe otra vez y recarga la página.

### Paso 3. Haz tu copia del proyecto (1 min)

Pulsa el botón **Fork** arriba a la derecha y confirma. GitHub crea una copia del proyecto en tu
cuenta; esa copia es la que trabajará para ti. Déjala pública: los proyectos públicos tienen
tiempo de ejecución gratis sin límite.

### Paso 4. Dile al bot qué coche buscas (5 min)

En **tu copia**, abre el fichero `config.yaml`, pulsa el lápiz (*Edit this file*) y cambia la
búsqueda. Puedes tener varias; cada una es así:

```yaml
searches:
  - name: mx5-nc              # un nombre corto, sale en cada mensaje
    make: Mazda               # marca, escrita como la escriben los portales
    model: MX-5               # modelo, escrito como lo escriben los portales
    year_min: 2005            # borra las líneas que no necesites
    year_max: 2015
    price_max: 14000          # euros
    km_max: 180000
    seller_types: [private, dealer]   # particulares, profesionales o ambos
```

Más opciones:

- `excluded_provinces: [baleares, las palmas, santa cruz de tenerife]` en el bloque `defaults`
  descarta anuncios de esas provincias (vale cualquier grafía: `Illes Balears`, `Baleares`...).
  Por defecto no se excluye ninguna.
- `title_exclude: ["NA", "NB"]` descarta anuncios cuyo título contenga esas palabras;
  `title_include: ["GTI"]` solo deja pasar los que contengan alguna.

Pulsa **Commit changes**. Puedes volver a editar este fichero cuando quieras; la siguiente pasada
usa los filtros nuevos.

### Paso 5. Dale a tu copia las credenciales del bot (2 min)

En tu copia: **Settings → Secrets and variables → Actions → New repository secret**, dos veces:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | el token del paso 1 |
| `TELEGRAM_CHAT_ID` | el chat id del paso 2 |

Pega los valores sin espacios delante ni detrás. Los secretos van cifrados y nadie puede leerlos,
tampoco en un proyecto público.

### Paso 6. Arráncalo (3 min)

1. Abre la pestaña **Actions** de tu copia. Si GitHub pregunta, pulsa *I understand my workflows,
   go ahead and enable them*.
2. En la lista de la izquierda pulsa **scan**, luego **Run workflow**, marca **seed** y pulsa el
   botón verde **Run workflow**.
3. Espera un minuto y recarga. La ejecución debe tener un tic verde. Si está en rojo, ábrela y
   lee las últimas líneas: un token o chat id incorrecto se indica ahí con palabras claras (mira
   la tabla [Troubleshooting](#troubleshooting)).

La primera pasada con *seed* marcado memoriza los anuncios que ya existen para no mandarte
decenas de golpe. Desde ese momento solo recibes anuncios nuevos.

### Paso 7. Haz que corra cada 15 minutos (5 min)

GitHub puede ejecutar el bot con un temporizador, pero su temporizador gratuito es poco fiable
(en nuestras pruebas corrió solo unas pocas veces al día). Una cuenta gratuita en
[cron-job.org](https://cron-job.org) lo arregla: pulsa el botón "Run workflow" por ti cada 15
minutos. Necesita una llave de GitHub para tener permiso.

1. **Crea la llave**: en GitHub, foto de perfil → **Settings** → **Developer settings** (al final
   del menú izquierdo) → **Personal access tokens** → **Fine-grained tokens** → **Generate new
   token**. Nombre `carbotfinder-cron`, caducidad *No expiration* (o la máxima), en *Repository
   access* elige **Only select repositories** y marca tu copia, y en *Permissions → Repository
   permissions* pon **Actions** en **Read and write**. Genera y copia la llave (empieza por
   `github_pat_`).
2. **Crea el job** en cron-job.org (*Cronjobs → Create cronjob*):
   - *Título*: `CarBotFinder scan`.
   - *URL*: `https://api.github.com/repos/TU_USUARIO_GITHUB/CarBotFinder/actions/workflows/scan.yml/dispatches`
     (cambia `TU_USUARIO_GITHUB` por tu usuario).
   - *Horario*: cada 15 minutos.
   - Pestaña *Avanzado*: *Método* **POST**; *Cuerpo de la solicitud* `{"ref":"main"}`; y cuatro
     encabezados:

     | Clave | Valor |
     |---|---|
     | `Authorization` | `Bearer github_pat_...` (la palabra `Bearer`, un espacio y tu llave) |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
     | `User-Agent` | `carbotfinder-cron` |
3. Pulsa **Ejecución de prueba**: la respuesta debe ser **204**. Luego **Crear**.

Listo. Cada 15 minutos GitHub consulta los portales por ti y recibes un mensaje de Telegram por
cada anuncio nuevo que cumpla tus filtros, con título, precio, año, km, provincia, tipo de
vendedor, portal y enlace.

### Cosas que conviene saber

- **Dos portales solo funcionan desde casa.** milanuncios y Autocasión bloquean las peticiones que
  vienen de los servidores de GitHub. Los otros cuatro funcionan bien. Si también quieres esos dos,
  mira [Run at home](#run-at-home-pc-raspberry-pi-nas): en Windows basta con
  `scripts\start-home-scan.bat` y `scripts\stop-home-scan.bat`.
- **Para cambiar los filtros**, edita `config.yaml` en tu copia. **Para pausar el bot**, desactiva
  el job en cron-job.org. **Para dejar de usarlo**, borra el job y tu copia del proyecto.
- **Guarda el token y la llave en privado.** Si crees que el token del bot se ha filtrado, revócalo
  en BotFather (*/mybots → API Token → Revoke*) y actualiza el secreto.
- **Frecuencia razonable.** El bot hace una petición por portal y pasada. Cada 15 minutos es más
  que suficiente para buscar coche y no molesta a los portales.
- **Si algo falla**, la tabla [Troubleshooting](#troubleshooting) recoge los errores típicos y su
  solución.
