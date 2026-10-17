# CarBotFinder

Bot que vigila los principales portales de coches de segunda mano de España y avisa por Telegram,
en pocos minutos, cuando aparece un anuncio que cumple los filtros del usuario (modelo, año, precio,
km, zona). Coste de operación: 0 €. El repositorio es público y sirve también como portfolio.

El plan detallado, la investigación de portales y las decisiones técnicas están en `docs/PLAN.md`.
Léelo antes de tocar un portal o la infraestructura.

## Objetivo concreto del usuario (primer caso de uso)

- Mazda MX-5 generación NC (años 2005-2015, cualquiera vale).
- Precio máximo 14.000 €. Kilometraje máximo 180.000 km.
- Cualquier provincia de la España peninsular. Excluidas: Illes Balears, Las Palmas, Santa Cruz de Tenerife.
  Ceuta y Melilla NO se excluyen por defecto (el usuario solo pidió excluir islas); es configurable.
- Aviso al móvil con enlace, a cualquier hora, lo antes posible tras la publicación.

El código debe ser genérico (varias búsquedas configurables en YAML), no un script a medida del MX-5.

## Decisiones cerradas (no reabrir sin motivo nuevo)

| Tema | Decisión | Por qué |
|---|---|---|
| Lenguaje | Python 3.12 | Mejor ecosistema de scraping/parsing; legible para portfolio |
| HTTP | `httpx` (HTTP/2, cabeceras de navegador realistas) | Sin navegador: todos los portales objetivo sirven datos en HTML/JSON embebido a un GET simple (verificado 2026-10-17) |
| Navegador headless | NO en la ruta principal | Pesado en CI, detectable; solo como fallback documentado si un portal empieza a bloquear |
| Notificaciones | Telegram Bot API | Gratis sin límite práctico para uso personal. WhatsApp Cloud API requiere cuenta Meta Business y desde oct-2026 cobra plantillas utility; libs no oficiales violan ToS |
| Ejecución | GitHub Actions (repo público = minutos ilimitados), `schedule` cada 5 min + `workflow_dispatch` | 0 €, sin tarjeta. Latencia real 5-20 min por retrasos de GitHub; se mitiga con cron-job.org disparando `workflow_dispatch` (ver PLAN) |
| Estado (anuncios ya vistos) | Fichero SQLite en GitHub Actions cache (`actions/cache` restore/save con clave por run) | Evita cientos de commits al día. Si se pierde el cache, el modo "seed" evita re-notificar anuncios antiguos |
| Config | `config.yaml` (búsquedas, filtros, portales) + variables de entorno para secretos | Secretos nunca en el repo público |
| Dependencias | `uv` + `pyproject.toml` | Rápido y reproducible en CI |
| Calidad | `ruff` (lint+format), `pytest`, `mypy` en modo estricto razonable | Portfolio |

## Portales (verificados en vivo el 2026-10-17 desde IP residencial; los seis responden)

| Portal | Cómo se obtienen datos | Notas |
|---|---|---|
| Wallapop | JSON `GET api.wallapop.com/api/v3/search` (`category_ids=100`, `brand`, `model`, `max_km`, `max_sale_price`, `order_by=newest`) | año no se filtra en servidor; `seller_type` desconocido |
| coches.net | JSON `POST web.gw.coches.net/search` con cabeceras `x-adevinta-channel: web-desktop` y `x-schibsted-tenant: coches`; exige `makeId`/`modelId` (lookup en `/makes` y `/models?makeId=`) | solo orden `relevance`; filtros precio/km/año en servidor; `size=100` cubre todo |
| milanuncios | HTML SSR `window.__INITIAL_PROPS__` → `adListPagination.adList.ads` | `orden=date` y `hasta=` funcionan; km/año vienen como texto en `tags` |
| AutoScout24.es | `__NEXT_DATA__` → `props.pageProps.listings`; filtros y `sort=age&desc=1` en URL | sin fecha de publicación ni provincia (se deriva del CP) |
| coches.com | `__NEXT_DATA__` → `pageProps.classifieds.classifiedList` | Imperva, pero sirve HTML; URL del anuncio desde los `<a href="...?id=">` de la página |
| Autocasión | HTML `<article class="anuncio">` + `<ul class="supplementary">` | `?orden=fecha`; todo concesionarios |

Lección aprendida: no fijar `Accept-Encoding` a mano; httpx no descodifica brotli sin el paquete
`brotli` y el HTML llega ilegible (coches.com y Autocasión fallaban por eso).
Lección aprendida (2026-10-17): milanuncios (Imperva) devolvió la página "Pardon Our Interruption" con
HTTP 200 tras ~6 peticiones en pocos minutos desde IP residencial (pruebas manuales seguidas). Se detecta
como `PortalBlocked` en `http.py`. En producción (1 req/5 min) no debería ocurrir; no lanzar pasadas
manuales en ráfaga contra milanuncios.
Riesgo principal pendiente: IPs de GitHub Actions. Se comprueba con el workflow `probe portals`.
Detalles y ejemplos de respuesta en `docs/PLAN.md`.

## Arquitectura (resumen)

```
carbotfinder/
  config.py        # modelos pydantic; carga config.yaml + env
  models.py        # Listing normalizado: portal, id, title, price, year, km, province, url, published_at, seller_type
  filters.py       # aplica filtros de una búsqueda a un Listing (puro, sin I/O)
  state.py         # SQLite: anuncios vistos (portal, id, first_seen, price)
  http.py          # cliente httpx compartido: cabeceras, timeouts, reintentos, backoff
  notify/telegram.py
  portals/base.py  # interfaz Portal.fetch(search) -> list[Listing]
  portals/{wallapop,cochesnet,milanuncios,autoscout24,cochescom,autocasion}.py
  runner.py        # orquesta: por cada búsqueda y portal → fetch → filtrar → dedup → notificar
  cli.py           # `carbotfinder run [--dry-run] [--seed] [--portal X] [--interval N]`
tests/             # fixtures HTML/JSON reales recortados y anonimizados; un test por parser
.github/workflows/scan.yml
docs/PLAN.md
config.example.yaml
```

Reglas de diseño:
- Cada portal falla de forma aislada: una excepción en uno no impide notificar los demás.
- Los parsers son funciones puras `parse(html_or_json) -> list[Listing]` testeadas con fixtures.
  La red solo se toca en `fetch`.
- Filtrado siempre en local aunque el portal admita el filtro en la URL (los filtros remotos
  son una optimización; la verdad es `filters.py`). Ej.: Wallapop devolvió MX-5 de 1999 con `min_year=2005`.
- Una petición por portal y búsqueda por ejecución (primera página, ordenada por más recientes).
  Nunca paginar en bucle en producción.
- Mensaje de Telegram: título, precio, año, km, provincia, portal, enlace. Un mensaje por anuncio.
- Errores repetidos de un portal se avisan por Telegram como máximo una vez cada 6 h.

## Convenciones

- Código, nombres, comentarios, commits y README principal en inglés (portfolio). `CLAUDE.md` y
  `docs/PLAN.md` en español. README incluirá sección en español.
- Commits convencionales: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`.
- Tipado en todas las funciones públicas. Sin `Any` salvo en bordes de parseo.
- No añadir dependencias sin justificarlo en el PR/commit.
- Nunca commitear tokens, `chat_id`, ni el fichero de estado. `.env` está en `.gitignore`.
- Fixtures de tests: recortar a 1-3 anuncios, quitar teléfonos, nombres y user ids.
- Respeto a los portales: cabecera `User-Agent` honesta pero de navegador, `Accept-Language: es-ES`,
  volumen bajo (~1 req/portal/5 min), no eludir CAPTCHAs ni autenticación. Si un portal bloquea,
  se desactiva en config y se documenta; no se escala con proxies de pago.

## Comandos

```
uv sync                                  # instalar
uv run carbotfinder run --dry-run        # una pasada sin notificar (una pasada es el modo por defecto)
uv run carbotfinder run --seed           # marca lo actual como visto sin avisar (primer arranque)
uv run carbotfinder run --interval 120   # bucle cada 2 min (PC/Raspberry)
uv run pytest                            # tests (añade --cov --cov-report=term-missing para cobertura)
uv run ruff check . && uv run ruff format --check .
```

Variables de entorno: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `CARBOT_STATE_PATH` (por defecto `state/seen.sqlite`).

## Estado del proyecto

- 2026-10-17: Fases 0-5 hechas en local (núcleo, 6 portales, workflows, README, Docker). 115 tests, cobertura 85%.
  Pendiente del usuario: crear bot de Telegram, repo público en GitHub, secretos, y lanzar `scan` con
  `seed=true`. Después: ejecutar `probe portals` y anotar aquí qué portales responden desde GitHub.
