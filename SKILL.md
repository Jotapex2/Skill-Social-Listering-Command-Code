---
name: social-listening-v2
description: Recolecta y analiza la conversación pública en X (Twitter) e Instagram sobre un tema y una fecha, SOLO por scraping de navegador (agent-browser), con fallback Chrome → Brave → Edge y sin tocar las sesiones reales del usuario. Entrega BBDD en Markdown/CSV de publicaciones y comentarios, nubes de palabras (general, por plataforma y de conceptos positivos/negativos limitados a verbos y adjetivos, sin nombres propios), volumen y posteos por hora (tabla + gráfico general y por red), top de influencers e informe en Markdown y Word. Úsala cuando pidan "social listening", "qué se dijo en redes" sobre un tema, monitoreo de X e Instagram, nube de palabras, volumen de conversación o comentarios de un día concreto.
argument-hint: "<tema> [fecha YYYY-MM-DD] [keyword, keyword, ...]"
---

# Social listening en X e Instagram (v2, solo navegador)

Convierte un tema y una fecha en un corpus de publicaciones y comentarios, y en entregables
analíticos citables. **X e Instagram se recolectan por scraping de navegador** (`agent-browser`),
sin API. El informe replica el formato del informe modelo de Lluvias.

## Autosuficiencia (no negociable)

La skill es **portable**: no depende de rutas ni archivos de ninguna máquina.

- Cero rutas absolutas: todo se resuelve relativo a la **carpeta del proyecto** (`ROOT/scripts`,
  `ROOT/config`, `ROOT/db`, `ROOT/output`).
- Dependencias en `requirements.txt` (`pip install -r requirements.txt`). spaCy es opcional.
- **Copia `scripts/` al `<proyecto>/scripts/`** y `assets/templates/*` a `<proyecto>/config/`
  (como `keywords.json` y `narrativa_conversacion.md`) antes de correr.

## Antes de empezar (no negociable)

- **Nunca uses el perfil real del navegador del usuario** (Chrome/Brave/Edge). Lanzarlo o matarlo
  puede **borrar sus cookies y sesiones**. Usa un **perfil dedicado y vacío** por navegador
  (`<proyecto>/.browser-profiles/<navegador>`), sesión `slv2-<navegador>`, y pide al usuario que
  inicie sesión **una vez** en la ventana *headed*.
- **Nunca cierres procesos del navegador del usuario** (`taskkill /F /IM chrome.exe|brave.exe|msedge.exe`).
  Para cerrar usa `agent-browser close`; en timeout se mata **solo el PID de la shell**.
- No borres ni modifiques cookies de terceros. No interactúes (like, follow, comentar).

## Entregables

| Archivo | Contenido |
|---|---|
| `db/menciones.md` / `.csv` | BBDD maestra: una fila por publicación |
| `db/comentarios.md` / `.csv` | Una fila por comentario (X + IG), con sentimiento y texto |
| `output/nube_palabras.png`, `_x.png`, `_instagram.png` | Nubes generales (sustantivos permitidos) |
| `output/nube_palabras_positivas.png` / `_negativas.png` | Solo **verbos y adjetivos**, sin nombres propios |
| `output/palabras_*.csv` | Frecuencias reales detrás de cada nube |
| `output/volumen_plataforma.csv`, `_por_hora.csv`, `_keywords.csv` | Volumen de conversación |
| `output/grafico_por_hora*.png` | Posteos por hora: general y por red social |
| `output/top_influencers.csv`, `top_autores.csv`, `top_posts.csv`, `top_comentarios.csv` | Rankings |
| `output/temas.csv`, `frases_frecuentes.csv`, `sentimiento.csv` | Conversaciones y polaridad |
| `output/informe_<tema>_<fecha>.md` y `.docx` | Informe (mismo formato que el de Lluvias) |

## Flujo

1. **Configurar.** Copia `assets/templates/keywords.json` a `config/` con `tema`, `fecha_objetivo`,
   `keywords`, `x_queries`, `ig_keywords` y `ig_media_accounts`. Opcional:
   `config/narrativa_conversacion.md` (se inyecta al informe).
2. **Instagram.** `python scripts/scrape_instagram.py --limit-per-source 8`.
   Requiere la ventana con sesión iniciada. Es lento (~13 s por post): córrelo en background. Si un
   `/reel/` no muestra comentarios, ábrelos con `ab.click('[aria-label="Comentario"]')`.
3. **X por navegador.** `python scripts/scrape_x_browser.py --scrolls 8 --reply-posts 40`.
   La búsqueda usa `since:`/`until:` en la pestaña Top (sin `f=live`) y extrae comentarios del
   permalink de los posts con más engagement.
4. **Consolidar.** `python scripts/build_md_db.py` → BBDD MD/CSV + tabla de comentarios.
5. **Entregables.** `python scripts/build_deliverables.py` → nubes, volumen, gráficos por hora,
   CSV e informe (MD + DOCX).

## Trampas que ya costaron tiempo

### agent-browser en Windows
- **Nunca captures su salida por pipe** (`subprocess.run(capture_output=True)`, `| Select-Object`):
  el daemon hereda el handle y el proceso nunca devuelve EOF. Redirige a archivo o a `NUL`.
- En timeout **no uses `taskkill /F /T`**: mata el árbol, se lleva el daemon y cada comando
  siguiente relanza el navegador. Mata solo el PID de la shell.
- Si cada llamada imprime `[agent-browser] launched browser`, el daemon murió.
- **No ejecutes otros comandos de agent-browser sobre la misma sesión mientras corre un scraper**:
  le cambias la página y el job devuelve basura en silencio.
- `eval` devuelve la salida **envuelta como string JSON con comillas escapadas**: hay que parsear
  dos veces (`ab.eval_json` lo hace). Usa `eval -b <base64>` para evitar infiernos de comillas.
- Detalle completo: [references/agent-browser-windows.md](references/agent-browser-windows.md).

### Navegador: resolución y fallback
`ab.py` resuelve el navegador de forma genérica: `AB_EXECUTABLE`/`AB_BROWSER` → rutas típicas de
Windows → `PATH` → Chromium de agent-browser. `ab.ensure_browser()` prueba **Chrome → Brave → Edge**
y cambia al siguiente si el elegido no responde (con `AB_BROWSER` forzado, no cambia). Añade
`--args "--disable-blink-features=AutomationControlled,--exclude-switches=enable-automation"` y un
`--user-agent` real; verifica `navigator.webdriver === false` antes de pedir el login.

### Instagram
- **Se busca por keyword, no por hashtag**: `https://www.instagram.com/explore/search/keyword/?q=<texto>`.
- Los links del grid se sacan de `a[href]` con `/p/`, `/reel/` o `/tv/`, y hay que **validar el
  patrón**: un parseo roto devuelve caracteres sueltos que parecen links.
- Los datos del post salen de las meta `og:title`, `og:description` (likes, comentarios, fecha,
  autor) y `time[datetime]`. Espera ~7 s y reintenta si vienen vacías.
- **Los comentarios NO están en `ul li`** (las páginas de post no tienen `ul`). Están en
  `span[dir="auto"]`: el texto sigue a un span de tiempo (`\d+\s*(s|sem|d|h|min|m)`).
- En `/reel/` los comentarios no están en el DOM hasta abrir el panel; el botón es
  `[aria-label="Comentario"|"Comment"]` y es un **SVG** (no tiene `.click()`): usa el click del CLI.
- Selectores y ejemplos: [references/selectores-y-scraping.md](references/selectores-y-scraping.md).

### X (navegador)
- **`f=live` ignora `since:`/`until:`.** La URL correcta es
  `https://x.com/search?q=<q> since:<fecha> until:<fecha+1>` (pestaña Top).
- Comentarios: abre el permalink, expande hilos, y **descarta el primer artículo** (tuit focal).
- Un parser ISO falla **en silencio** ante el formato Twitter (`%a %b %d %H:%M:%S %z %Y`);
  `build_md_db.py` ya prueba ambos.

## Análisis

- **Convierte a `America/Santiago` antes de asignar el día** y deduplica por URL canónica.
- **Filtra off-topic** (opcional con `--filtrar-off-topic`): descarta publicaciones sin ninguna
  keyword en el texto.
- Nube general/por plataforma: fondo blanco, 2000×900, `collocations=False`,
  `prefer_horizontal≈0.985`, sin título dentro de la imagen.
- **Nubes positivas/negativas: solo VERBOS y ADJETIVOS, sin nombres propios.** `scripts/pos.py` usa
  spaCy `es_core_news_sm` (`pos_ in {VERB, ADJ}`, descartando entidades) y, si no está, un fallback
  heurístico por terminaciones + `proper_nouns()` (tokens solo capitalizados) + sustantivos
  institucionales. El sentimiento usa un léxico español **conservador** (~70% queda
  `sin_clasificar` y hay que decirlo).
- **Posteos por hora:** tabla y gráfico general + uno por red. Si Instagram no entrega hora fiable,
  se omite su gráfico y se reporta general + X.
- **Influencers**: top 5 por plataforma ordenado por **cantidad de posteos**, desempata engagement.
- Guarda siempre el **texto de cada comentario** en su propia tabla.

## Redactar el informe

Estructura en [references/formato-informe.md](references/formato-informe.md): resumen ejecutivo →
**resumen de la conversación** (narrativa inyectable desde `config/narrativa_conversacion.md`) →
metodología → volumen → **posteos por hora (tabla + gráficos)** → top influencers → nubes →
positivos/negativos → conversaciones frecuentes → comentarios (con citas y enlace) → top posts →
sentimiento → límites. Toda afirmación factual con su enlace.

## Límites que hay que declarar

Recolección solo por scraping: cobertura parcial y no determinista; X puede pedir login o aplicar
rate limit; IG entrega poco volumen (su búsqueda prioriza lo popular) pero concentra el engagement.
Declara siempre lo que no se pudo abrir y, si aplica, que el gráfico por hora de IG se omitió.
