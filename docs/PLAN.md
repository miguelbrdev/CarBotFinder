# Plan de desarrollo: CarBotFinder

Fecha de la investigación: 2026-10-17. Todo lo marcado "verificado" se comprobó con `curl` desde
una conexión doméstica en España (IP residencial, Windows). Lo marcado "por verificar" se resuelve
en la fase indicada.

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Filtros | precio máximo, modelo (marca+modelo), rango de años, km máximo, provincias excluidas |
| Caso inicial | Mazda MX-5 NC, 2005-2015, <= 15.000 EUR (14.000 hasta 2026-10-18), <= 180.000 km, península (sin Baleares ni Canarias) |
| Portales | coches.net, Wallapop, milanuncios (pedidos) + AutoScout24.es, coches.com, Autocasión (añadidos) |
| Aviso | Telegram, con enlace, minutos después de publicarse, 24/7 |
| Coste | 0 EUR |
| Extra | repo público como portfolio, código genérico y configurable |

## 2. Investigación: notificaciones

- **Telegram Bot API**: gratis. Límite relevante para chat personal: aprox. 1 msg/s y 20 msg/min por chat;
  la cota de 30 msg/s es para difusión masiva. Basta `sendMessage` con `chat_id` propio. Sin framework.
- **WhatsApp**: la Cloud API exige cuenta Meta Business con número verificado; desde el 1-oct-2026
  Meta cobra las plantillas *utility* (las notificaciones proactivas) y solo deja 1.000 mensajes de servicio
  gratis al mes (respuestas dentro de la ventana de 24 h, que no sirven para avisos iniciados por el bot).
  Las librerías no oficiales (whatsapp-web.js, Baileys) violan los ToS y pueden bloquear el número.
  **Descartado.**
- Alternativas gratuitas si Telegram no gustara: ntfy.sh (app push, sin cuenta), Discord webhook, email.

**Decisión: Telegram.**

## 3. Investigación: dónde ejecutar 24/7 gratis

| Opción | Coste | Cadencia mínima | Contras |
|---|---|---|---|
| GitHub Actions (repo público) | 0 EUR, sin tarjeta, minutos ilimitados | `schedule` cada 5 min nominal | Retrasos de 5-20 min en horas punta, ejecuciones a veces descartadas; se desactiva tras 60 días sin commits; IP de datacenter (riesgo 403) |
| GitHub Actions + cron-job.org | 0 EUR | cron-job.org llama a `workflow_dispatch` cada 5 min con precisión de minuto | Necesita un PAT de grano fino guardado en cron-job.org |
| Oracle Cloud Always Free (VM ARM) | 0 EUR pero exige tarjeta | 1 min o menos (loop propio) | Cuota reducida a 2 OCPU/12 GB en 2026; registro a veces rechazado; IP de datacenter |
| Google Cloud e2-micro | 0 EUR con tarjeta | 1 min | 1 GB RAM, tarjeta obligatoria |
| Cloudflare Workers cron | 0 EUR | 1 min, 5 triggers | 10 ms de CPU por ejecución en plan free: insuficiente para parsear HTML de 1,5 MB |
| Fly.io / Render / Railway | Ya no tienen free tier real o duermen | - | Descartado |
| PC propio / Raspberry Pi | 0 EUR | 1 min | Depende de que esté encendido; IP residencial (ventaja anti-bot) |

**Decisión: Fase 3 en GitHub Actions** (`schedule` + `workflow_dispatch`). Resultado medido
(2026-10-17/18): el `schedule: */5` corrió 4 veces en 13 h, así que cron-job.org disparando
`workflow_dispatch` cada 10 min es la cadencia real y el cron (`*/10`) solo respaldo. Si las IPs de GitHub
reciben 403 en algún portal, ese portal se marca como "solo residencial" y se documenta; la opción de
ejecutarlo en un PC/Raspberry con Docker queda como despliegue alternativo soportado (Fase 6).

Persistencia del estado en Actions: `actions/cache/restore` con `restore-keys: state-` y
`actions/cache/save` con `key: state-${{ github.run_id }}`. El cache caduca a los 7 días sin uso
(no aplica, se usa cada 5 min). Si se pierde, el runner arranca en modo seed automático: notifica solo
anuncios con `published_at` dentro de las últimas 2 h y marca el resto como vistos.

## 4. Investigación: portales (verificado 2026-10-17)

### 4.1 Wallapop (prioridad 1, muchos particulares)

- Endpoint JSON no documentado: `GET https://api.wallapop.com/api/v3/search`
- Parámetros que funcionaron: `source=search_box`, `category_ids=100` (Cars), `brand=Mazda`,
  `model=MX-5`, `max_km=180000`, `max_sale_price=14000`, `order_by=newest`, `latitude`, `longitude`,
  `distance_in_km=1000`. `min_year/max_year` **no filtró** (devolvió un 1999): filtrar en local.
- Cabeceras usadas: UA de Chrome, `Accept: application/json`, `X-DeviceOS: 0`, `Accept-Language: es-ES`.
- Respuesta: `data.section.payload.items[]` con `id`, `title`, `price.amount`, `location.{region,region2,city,postal_code}`,
  `type_attributes.{brand,model,year,km,engine,gearbox,horsepower}`, `created_at` (ms epoch), `modified_at`,
  `web_slug`, `reserved.flag`. `meta.next_page` es un JWT para paginar (no se usa).
- URL del anuncio: `https://es.wallapop.com/item/{web_slug}`.
- Lista de categorías: `GET /api/v3/categories` (100 = Cars, 14000 = Motorbike, 12800 = Motor y accesorios).
- Riesgo: la API puede cambiar sin aviso o exigir `X-Signature`/tokens (proyectos como WallpopMCP mencionan
  reintentos con firma ante 403). Hoy no hizo falta.

### 4.2 coches.net (prioridad 2, líder en volumen, muchos concesionarios)

**Resultado (verificado 2026-10-17, implementado):** la página SSR no admite ordenar por fecha
(`sortBy` siempre `relevance`; los parámetros `fi=`/`or=` no cambian nada). La app web usa un gateway
JSON: `POST https://web.gw.coches.net/search` con cabeceras `x-adevinta-channel: web-desktop` y
`x-schibsted-tenant: coches` (sin ellas: 400). Cuerpo:
`{"pagination":{"page":1,"size":100},"sort":{"order":"desc","term":"relevance"},"filters":{"categories":{"category1Ids":[2500]},"price":{"to":14000},"km":{"to":180000},"year":{"from":2005,"to":2015},"vehicles":[{"makeId":27,"modelId":237}]}}`.
Los nombres de marca/modelo sin ids devuelven 0 resultados; ids vía `GET /makes?categoryId=2500` y
`GET /models?makeId=27&categoryId=2500` (`{"items":[{"id","label"}]}`). Solo acepta `term: relevance`
(`publishedDate`/`SortDate` → 400). Respuesta: `{"items":[...],"meta":{"totalPages","totalResults"}}`
con `publishedDate`, `creationDate`, `isProfessional`, `price.hasReservation`, `location.mainProvince`
(ojo: abreviado, p. ej. "Sta. C. Tenerife", "Coruña (A)"). El host antiguo `ms-mt--api-web.spain.advgo.net`
ya no existe (502).

Notas originales de la investigación:

- URL: `https://www.coches.net/segunda-mano/mazda/mx-5/` (también `/mazda-mx-5/segunda-mano/`).
  Paginación `?pg=N` (35 anuncios/página). **Por verificar (Fase 2):** parámetros de URL para ordenar por
  fecha y para filtros (`initialSearch` muestra `kms`, `price`, `year`, `onlyPeninsula`, `provinceIds`).
  Ojo: una URL mal formada redirige 301 a `/noticias/...` sin error.
- Datos: `window.__INITIAL_PROPS__ = JSON.parse("<json escapado>")` → `initialResults.items[]`.
- Campos: `id`, `title`, `price`, `km`, `year`, `location.{regionLiteral,mainProvince,mainProvinceId,cityLiteral}`,
  `url` (relativa), `publicationDate`, `creationDate`, `isProfessional`, `offerType.literal`, `fuelType`, `hp`.
- Sin bloqueo observado (CloudFront, 200).

### 4.3 milanuncios (prioridad 3, particulares)

**Resultado:** `orden=date` y `hasta=` (precio máx.) se reflejan en `adSearchParams`; `kmshasta`,
`anodesde`, `anohasta` no (se filtra en local). 41 anuncios por página, `pagination.nextToken` para seguir.


- URL: `https://www.milanuncios.com/mazda-de-segunda-mano/mx-5.htm?orden=date&fromSearch=1`.
  **Por verificar:** parámetros `desde`, `hasta` (precio), `kmsdesde`, `kmshasta`, `anodesde`, `anohasta`.
- Datos: mismo patrón `__INITIAL_PROPS__` (misma plataforma Adevinta) → `adListPagination.adList.ads[]` (41).
- Campos: `id`, `title`, `price.cashPrice.value`, `location.{region,province,city}`, `url` (relativa),
  `publishDate`, `updateDate`, `sellerType` (`private`/`professional`), `isReserved`,
  `tags[]` con `{type: "kilómetros", text: "198.000 kms"}` y `{type: "año", text: "2004"}` → parsear texto.
- Sin bloqueo observado (200, 1,5 MB de HTML).

### 4.4 AutoScout24.es (prioridad 4)

- URL con filtros nativos: `https://www.autoscout24.es/lst/mazda/mx-5?atype=C&cy=E&fregfrom=2005&fregto=2015&kmto=180000&priceto=14000&sort=age&desc=1`.
- Datos: `<script id="__NEXT_DATA__">` → `props.pageProps.listings[]` (+ `numberOfResults`, `numberOfPages`).
- Campos: `id`, `title`, `price.priceRaw`, `vehicle.{make,model,mileageInKm ("135.000 km"),fuel,transmission}`,
  `tracking.firstRegistration ("06-2010")`, `location.{zip,city}` (**sin provincia**: derivar de los dos primeros
  dígitos del CP), `seller.type` (`PrivateSeller`/`Dealer`), `url` (relativa). No hay fecha de publicación
  clara en el listado: dedup por id.
- Aparece la palabra "Captcha" en el HTML (scripts de defensa cargados), pero la respuesta fue 200 con datos.

### 4.5 coches.com (prioridad 5, casi todo concesionarios)

**Resultado:** la URL del anuncio es `https://www.coches.com/coches-segunda-mano/ocasion-<slug>.htm?id=<visibleId>`
y se toma de los `<a href>` de la propia página. Sin parámetros de filtro ni orden verificados.
Importante: la respuesta llega en brotli; httpx la descodifica solo si no se fuerza `Accept-Encoding`.


- URL: `https://www.coches.com/coches-segunda-mano/mazda-mx-5.htm?order[created_at]=desc` (20 por página,
  más nuevos primero; auditado 2026-10-17: sin el orden solo se veían 20 de 25 anuncios por relevancia).
  La query string solo admite `page` y `order[...]` (valores del menú "Ordenar": `order[price][amount]`,
  `order[registration][year]`, `order[mileage][amount]`, `order[created_at]`); cualquier otro parámetro → 404.
  Los filtros `filters[price]...` son de su API privada, no de la página.
- Datos: `__NEXT_DATA__` → `props.pageProps.classifieds.classifiedList[]` (20).
- Campos: `id`, `make.name`, `model.name`, `version.name`, `mileage.amount`, `price.amount`, `priceOffer`,
  `currentProvince.name`, `registration.year`, `createdAt`, `updatedAt`, `visibleId`, `dealer`.
  URL del anuncio: **por verificar** (construir desde `visibleId`/slug).
- Protegido por Imperva/Incapsula (cookies `visid_incap_*`), aun así 200 a curl. Riesgo medio-alto de 403 desde datacenter.

### 4.6 Autocasión (prioridad 6, concesionarios)

**Resultado:** se parsean las tarjetas HTML (`data-ad`, `<h2>`, `<p class="precio">`,
`<ul class="supplementary">` = año, combustible, km, provincia, municipio). Clase `con-concesionario` = profesional.


- URL: `https://www.autocasion.com/coches-segunda-mano/mazda-mx-5-ocasion?orden=fecha&sort=updated_at&direction=desc`
  (25 por página; auditado 2026-10-17: `orden=fecha` solo devuelve el orden por defecto y se veían 25 de 36;
  el enlace "Publicación: Más recientes" del propio menú añade `sort=updated_at&direction=desc`.
  Otros `sort`: `price`, `kilometers`, `year`).
- Datos: un `<script type="application/ld+json">` con lista de 25 `Product` → `offers.{price,url}`,
  `offers.itemOffered` (`Car`: `model`, `color`, `bodyType`; km/año **por verificar** dentro del `Car`).
  Complementar con las tarjetas HTML (`data-product-key`, `data-path`) si faltan km/año/provincia.
- Cloudflare, 200.

### 4.7 Descartados / futuro

- motor.es: agregador de stock de concesionarios, Cloudflare. Evaluar en Fase 6 si aporta anuncios no vistos.
- Agregadores (cochessegundamano.es, etc.): duplican lo anterior.
- Servicios de pago (Apify, Scrappa): fuera por coste.

### 4.8 Exclusión de islas

Por defecto no se excluye ninguna provincia (decisión del usuario 2026-10-18: el proyecto es para
cualquiera). El `config.yaml` del usuario excluye `Baleares`, `Las Palmas` y `Santa Cruz de Tenerife`.
Normalizar acentos y variantes (`Illes Balears`, `Islas Baleares`, `Balears`, `Sta. Cruz de Tenerife`).
Para AutoScout24, mapear CP → provincia (07 Baleares, 35 Las Palmas, 38 S/C Tenerife).
Ceuta (51) y Melilla (52) configurables, no excluidas por defecto.

### 4.9 Detección de generación (MX-5 NC)

Filtro principal: `year` entre 2005 y 2015. Es suficiente para el usuario ("me vale cualquiera").
Opcional en config: `title_exclude: ["NA", "NB", "ND"]` con coincidencia de palabra completa, para
limpiar los bordes 2005 (NB tardíos) y 2015 (ND tempranos). Desactivado por defecto.

## 5. Diseño

### 5.1 Modelo normalizado

```
Listing:
  portal: str            # "wallapop" | "cochesnet" | ...
  id: str                # id nativo del portal
  title: str
  price: int | None      # euros
  year: int | None
  km: int | None
  province: str | None   # normalizada, sin acentos, minúsculas, para comparar
  province_raw: str | None
  city: str | None
  url: str               # absoluta
  published_at: datetime | None
  seller_type: "private" | "dealer" | None
  reserved: bool
  raw: dict              # solo en memoria, no se persiste
```

### 5.2 Config (`config.yaml`)

```yaml
telegram:
  chat_id_env: TELEGRAM_CHAT_ID
  token_env: TELEGRAM_BOT_TOKEN
defaults:
  excluded_provinces: [baleares, las palmas, santa cruz de tenerife]
  seed_window_hours: 2
searches:
  - name: mx5-nc
    make: Mazda
    model: MX-5
    year_min: 2005
    year_max: 2015
    price_max: 14000
    km_max: 180000
    title_exclude: []        # ej. ["NA", "NB", "ND"]
    seller_types: [private, dealer]
    portals: [wallapop, cochesnet, milanuncios, autoscout24, cochescom, autocasion]
```

Cada portal recibe la búsqueda y construye su URL/params a partir de `make`/`model` (tabla de slugs por
portal dentro del módulo; si un portal no conoce el modelo, falla con mensaje claro).

### 5.3 Flujo por ejecución

1. Cargar config y estado (SQLite). Si el estado está vacío → modo seed.
2. Para cada búsqueda x portal: `fetch` (1 request, página 1, orden más recientes) → `parse` → `filters.apply`.
3. Para cada listing que pasa filtros y no está en estado: enviar Telegram, insertar en estado.
   En modo seed: insertar sin enviar salvo `published_at` reciente.
4. Guardar estado. Registrar métricas por portal (n obtenidos, n filtrados, n nuevos, errores).
5. Si un portal lleva 3 o más ejecuciones seguidas fallando, enviar un aviso de error (máx. 1 cada 6 h).

### 5.4 Mensaje de Telegram (HTML parse mode)

```
🚗 <b>Mazda MX-5 1.8 126 CV</b>
💶 11.999 EUR  ·  📅 2011  ·  🛣 98.000 km
📍 Sevilla (Andalucía)  ·  👤 particular  ·  wallapop
🔗 https://es.wallapop.com/item/...
```

## 6. Fases

| Fase | Entregable | Criterio de hecho |
|---|---|---|
| 0. Bootstrap | `git init`, `pyproject.toml` (uv), ruff, pytest, mypy, `.gitignore`, `.env.example`, `config.example.yaml`, LICENSE MIT, README esqueleto | `uv run pytest` pasa en verde con un test trivial |
| 1. Núcleo | `models`, `config`, `filters`, `state`, `http`, `notify/telegram`, `runner`, `cli` | Tests de filtros y estado; `--dry-run` imprime listings de un portal falso |
| 2. Portales | Wallapop → coches.net → milanuncios → AutoScout24 → coches.com → Autocasión, cada uno con fixture y test de parser | Cada parser devuelve `Listing` correctos desde fixture real; `--once --dry-run --portal X` funciona en local |
| 3. Despliegue | `.github/workflows/scan.yml` (schedule + dispatch), secrets, cache de estado, workflow de sondeo que registra el código HTTP de cada portal desde la IP del runner | Primer aviso real recibido en Telegram desde Actions; tabla de portales OK/bloqueado desde GitHub |
| 4. Robustez | reintentos con backoff, aislamiento de fallos, alerta de errores, logs estructurados, seed automático | Simular 403 en un portal y comprobar que los demás notifican |
| 5. Portfolio | README (EN + sección ES) con diagrama, GIF/captura del aviso, badges de CI, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md` | README explica en 1 minuto qué hace y cómo desplegarlo |
| 6. Opcional | cron-job.org → `workflow_dispatch`; Dockerfile + `docker compose` para PC/Raspberry; aviso de bajada de precio; motor.es | Según resultados de la Fase 3 |

Orden de los portales en Fase 2 justificado por valor para el usuario: Wallapop y milanuncios concentran
particulares (mejores precios para un MX-5 de hasta 14k); coches.net es el mayor volumen; el resto es
mayoritariamente concesionario.

## 6.1 Estado de ejecución (2026-10-17)

Fases 0-5 completadas en local; pasada en vivo (`--dry-run`) con los seis portales: Wallapop 4→1,
coches.net 24→22, milanuncios 41→8, AutoScout24 7→7, coches.com 20→0, Autocasión 25→1
(obtenidos→coinciden con el filtro MX-5 NC).

Despliegue: repo público subido y CI en verde (2026-10-17). Sondeo `probe portals` desde GitHub Actions:
Wallapop 3→1, coches.net 24→21, AutoScout24 7→7, coches.com 20→0 responden; **milanuncios y Autocasión 403**.
Decisión: `scan.yml` ejecuta solo los cuatro portales que responden (`--portal`); milanuncios y Autocasión
quedan en `config.yaml` para la ejecución doméstica (Docker/`--interval`), que puede correr en paralelo sin
duplicar avisos porque el estado es por máquina y los portales no se solapan. No se usan proxies.

## 7. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| 403 desde IPs de GitHub Actions en algún portal | Media (coches.com alta) | Sondeo en Fase 3; portal desactivable; despliegue alternativo en PC/Raspberry con Docker |
| Cambio de estructura HTML/JSON | Alta a medio plazo | Parsers aislados + tests con fixtures; alerta si un portal devuelve 0 anuncios N veces seguidas cuando antes devolvía más |
| Retrasos de `schedule` en GitHub | Alta | cron-job.org como disparador; aceptar 5-20 min como peor caso |
| Pérdida del cache de estado | Baja | Seed automático con ventana de 2 h |
| Spam de Telegram al arrancar | Media | Modo seed obligatorio en la primera ejecución |
| ToS de los portales | - | Uso personal, volumen mínimo, sin eludir CAPTCHAs, sin redistribuir datos; README lo deja claro |

## 8. Preguntas abiertas (asumido hasta que el usuario diga lo contrario)

1. Ceuta y Melilla: se incluyen (solo se excluyen islas).
2. Concesionarios: se incluyen junto a particulares; el mensaje indica cuál es.
3. El usuario tiene cuenta de Telegram y de GitHub (necesarias para Fase 1 y 3).
4. Idioma del código y README: inglés, con sección en español.

## 9. Plan v2: hacer el proyecto usable por otras personas (2026-10-18)

> **Decisión final (2026-10-18, mismo día):** el usuario prefiere no ampliar el proyecto, para no
> complicarlo ni fomentar un uso masivo que acabe en bloqueos de IP. De este plan solo se ejecuta
> lo mínimo: `carbotfinder setup-telegram` (el paso donde todo el mundo tropieza), una comprobación
> de credenciales al arrancar `run` (los fallos de Telegram dejan de ser silenciosos) y un README
> con la ruta completa y una tabla de errores reales. El resto (A2-A5) queda archivado aquí como
> referencia por si cambia la decisión.

Objetivo: que alguien sin conocimientos de Python pueda tener el bot funcionando en 15 minutos
siguiendo el README, sin tocar código y sin que nadie le acompañe. Decisión del usuario: **camino A**,
cada persona ejecuta su propia copia (fork/template + su bot de Telegram + su GitHub). El bot compartido
multiusuario (camino B) queda descartado por ahora: convertiría al autor en proveedor de un servicio y
multiplicaría las peticiones a los portales desde una misma IP.

### 9.1 Fricción medida en el primer despliegue real (2026-10-17)

| # | Paso | Qué falló o costó | Fase que lo resuelve |
|---|---|---|---|
| 1 | Instalar Python + uv y ejecutar comandos | `uv` no estaba en PATH; cp1252 en consola | A4 (Docker) y A1 (`setup` tolerante) |
| 2 | Obtener el `chat_id` | @userinfobot no respondía; hubo que usar `getUpdates` a mano | A1 |
| 3 | Escribir `config.yaml` | Grafía de marca/modelo sin ayuda; no se sabe si un portal devuelve 0 por error o por grafía | A1 |
| 4 | Despliegue en GitHub (9 pasos) | Secretos, habilitar Actions, probe, seed, token, cron-job.org; el `Bearer` olvidado solo se detecta probando | A2 |
| 5 | Portales bloqueados desde GitHub | Lista `--portal` escrita a mano en `scan.yml` | A2 (autodesactivación) |
| 6 | Scripts de casa solo Windows | `.bat` | A4 |
| 7 | Fallos silenciosos | Token caducado, parser roto, caché perdido: nadie se entera | A3 |

### 9.2 Fases

**A1. Onboarding local: `carbotfinder setup` y `carbotfinder doctor`** (prioridad máxima)

- `setup`: asistente interactivo en consola (sin dependencias nuevas, `input()` + validación pydantic).
  1. Token del bot → llama a `getMe`, muestra el nombre del bot.
  2. Chat id automático: pide al usuario que escriba "hola" al bot y sondea `getUpdates` hasta 2 min;
     muestra nombre y chat id encontrados; envía un mensaje de prueba.
  3. Búsqueda: marca, modelo, años, precio, km, provincias excluidas (islas por defecto), vendedores.
  4. Comprobación en vivo: una petición por portal con esa búsqueda; por cada portal muestra
     `N anuncios, M cumplen filtros` y dos títulos de ejemplo. `fetched=0` → sugerencia de grafía
     (para coches.net, lista de modelos de esa marca desde su API; para Wallapop, aviso de que usa su
     catálogo). Permite corregir y repetir.
  5. Escribe `.env` y `config.yaml` (conservando comentarios del ejemplo) y hace el seed inicial si el
     usuario quiere.
- `doctor`: comprobación no interactiva que imprime una tabla con OK/FAIL: credenciales de Telegram
  (`getMe`, `sendMessage` opcional), fichero de config válido, cada portal responde y devuelve anuncios,
  estado accesible y fecha de última pasada, versión instalada vs. última publicada. Salida apta para
  pegar en un issue. Es también lo que ejecuta el workflow `probe`.
- Mensajes de error de config legibles (pydantic → frase en español/inglés con el campo y el valor).
- Tests: el asistente se prueba con `respx` y entradas simuladas; `doctor` con portales falsos.

Criterio de hecho: una persona que nunca ha visto el proyecto, con Python instalado, llega a recibir
un mensaje de prueba y a tener `config.yaml` válido solo con `uv run carbotfinder setup`.

**A2. Despliegue en GitHub sin pasos frágiles**

- Repo marcado como **template** en GitHub ("Use this template" crea una copia limpia con Actions
  activas; no hereda historial ni los badges del autor). Verificar que los `schedule` arrancan en copias
  de template sin push adicional; si no, documentar "haz un commit".
- **Autodesactivación de portales bloqueados por runner**: el runner ya guarda `portal_health`; se
  amplía con una ventana: si un portal devuelve `PortalBlocked` en 3 pasadas seguidas, se salta
  durante 24 h (y se reintenta después) en lugar de fallar cada vez. Así `scan.yml` deja de llevar la
  lista `--portal` a mano y cada copia se adapta sola a lo que su runner puede ver. Se avisa una vez por
  Telegram ("milanuncios bloquea esta IP; usa el modo casa").
- Workflow `scan` con `inputs` claros y un workflow `setup` de un solo clic: hace el probe, el seed y
  deja un resumen en el *job summary* de GitHub (markdown visible en la propia pestaña Actions).
- Cron externo sin errores: `carbotfinder cron-command --repo <owner/repo>` imprime el comando cURL
  exacto (con cabeceras, cuerpo y marcador para el token) para el botón **Import from cURL** de
  cron-job.org, que rellena método, cabeceras y cuerpo solo. Documentar también el plan B (GitHub
  `schedule`) y sus límites con los datos medidos.
- Badges y URLs del README generados desde el nombre del repo (o instrucción "sustituye `<you>`").

Criterio de hecho: el README de despliegue baja de 9 pasos a 5 y ninguno exige escribir cabeceras a mano.

**A3. Salud y mantenimiento sin vigilancia**

- Latido: el estado guarda `last_run_at`; `doctor` y cada pasada avisan por Telegram si la pasada
  anterior fue hace más de X horas (configurable, por defecto 6 h), una vez al día como máximo. Cubre
  caché perdido, cron-job.org parado y token caducado (en los casos en que alguna pasada llega a correr).
- Deriva de parsers: si un portal devuelve 0 anuncios durante N pasadas seguidas para una búsqueda que
  antes devolvía resultados, aviso por Telegram ("puede que X haya cambiado su web"). Es la señal de que
  hay que actualizar el parser; no se puede automatizar la corrección.
- Resumen diario opcional (`daily_summary: true`): un mensaje con pasadas realizadas, anuncios vistos
  por portal y errores. Da confianza de que el bot vive.
- Smoke test semanal en CI contra los portales reales (`probe`) que abre o actualiza un issue en el
  repo si un parser falla, de modo que los forks reciban la señal por el *upstream*.
- Dependabot para `uv.lock` y acciones de GitHub. Versionado semántico con tags y `CHANGELOG.md`;
  `doctor` compara con la última release para avisar de actualizaciones.

**A4. Portabilidad: casa, Docker, Raspberry**

- Scripts equivalentes para Linux/macOS (`scripts/home-scan.sh` start/stop/refresh con PID file) y
  un ejemplo de unidad `systemd` y de `launchd`.
- Imagen Docker publicada en GHCR por workflow en cada release (`ghcr.io/<owner>/carbotfinder`), con
  `docker-compose.yml` listo (`restart: unless-stopped`, volumen `state/`, `.env`). Objetivo:
  `docker compose up -d` en una Raspberry sin instalar Python.
- `setup` ejecutable dentro del contenedor (`docker compose run --rm bot setup`).

**A5. Documentación y comunidad**

- README reorganizado: "Qué hace" (1 pantalla, con captura del mensaje de Telegram), "En 15 minutos"
  (ruta única recomendada), "Otras formas de ejecutarlo", "Configuración", "Preguntas frecuentes" con
  los errores reales vistos (401 `Bearer`, 404 token sin permiso, 422 cuerpo, `fetched=0`, 403 desde
  GitHub, "Pardon Our Interruption"), "Cómo añadir un portal".
- Capturas de pantalla de los pasos de GitHub y cron-job.org; GIF corto de `setup`.
- Plantillas de issue ("portal roto", "nuevo portal", "pregunta") y `CONTRIBUTING.md` actualizado.
- Sección "Uso responsable" ampliada: qué volumen es razonable, por qué no hay proxies ni evasión.

### 9.3 Orden, esfuerzo y dependencias

| Fase | Esfuerzo | Depende de | Qué desbloquea |
|---|---|---|---|
| A1 setup + doctor | 2-3 sesiones | nada | todo lo demás (probe y setup workflow reutilizan `doctor`) |
| A2 despliegue | 1-2 sesiones | A1 (`doctor`) | README corto; cron sin errores |
| A3 salud | 1-2 sesiones | A1 (estado con `last_run_at`) | confianza a largo plazo |
| A4 portabilidad | 1 sesión | A1 (`setup` en Docker) | Raspberry/NAS, Linux/Mac |
| A5 documentación | 1 sesión, al final | A1-A4 | adopción |

Sin dependencias nuevas de Python salvo justificación; sin servicios de pago; sin recoger datos de
usuarios (cada copia es privada). Cada fase termina con tests, CI en verde y README actualizado.

### 9.4 Riesgos específicos de v2

| Riesgo | Mitigación |
|---|---|
| Más usuarios → más peticiones a los portales desde los rangos de GitHub → bloqueo general | Cadencia por defecto 15 min, una petición por portal, autodesactivación en bloqueo, documentación de uso responsable. No se puede controlar del todo: es inherente a repartir la herramienta. |
| El asistente se queda obsoleto si un portal cambia la grafía | `setup` consulta en vivo, no una lista fija; coches.net expone su catálogo. |
| Más superficie de código = más mantenimiento | `setup`/`doctor` reutilizan `runner`, `portals` y `notify`; nada duplicado. |
| Template repo y `schedule` | Verificar en la primera fase A2 con una copia de prueba. |

### 9.5 Fuera de alcance (por ahora)

Bot compartido multiusuario, interfaz web, más portales (se añaden con el procedimiento de
`CONTRIBUTING.md` cuando alguien los pida), notificaciones por WhatsApp o email, proxies o navegador
headless para portales que bloquean.
