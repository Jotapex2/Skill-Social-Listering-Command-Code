# social-listening-v2

Skill de **social listening** para X (Twitter) e Instagram: recolecta publicaciones y comentarios
sobre un tema y una fecha, los consolida en una base de datos y genera un informe con nubes de
palabras, volumen y posteos por hora.

Todo se recolecta **solo por scraping de navegador** con `agent-browser` (sin APIs ni llaves), y
la skill es **autosuficiente**: no depende de rutas ni de archivos externos, así que puedes copiarla
a otra máquina tal cual.

- Esto está pensado para ser utilizado directamente en **Command-Code**, yo personalmente lo ocupo con 
deepseek 4.1 flash o algún modelo similar, ya que, depende del **agent-browser** que es específico 
del harness. Los modelos gringos suelen dar problemas debido a que el scraping de RRSS puede violar 
sus términos y condiciones. No la he probado en **opencode** u otros, pero se podría adaptar.
**Command-Code** no es caro, el plan más barato vale 1 dólar.

# Problemas conocidos:
- Cuando la skill te pide iniciar sesión, ya que, esta hace un scraping con alguna sesión de alguna
cuenta de IG o X (No es necesario que ocupes la personal, puedes crear una para ello), a veces en
X no te deja iniciar. Solo tienens que abrir una pestaña aparte, entrar a x.com y loguearte.
- No ocupa tu sesión oficial, porque a veces agent-browser se bugea y rompe todas tus sesiones,
teniendo que volver a loguearte a todo de vuelta, por eso pide login aparte.
- Al ser scraping, el proceso puede tardar algo más de una hora. **¿Por qué?** Básicamente
la skill crea scripts de python que van navegando por las RRSS y registrando cada post y comentario
con sus **métricas**.
- Solo funciona con navegadores en base **chormiun** o sea, Google Chorme, Brave, Edge. Igual
puedes pedirle otro tipo Vivaldi u opera, por ejemplo.

# Tips de uso:
- Te recomiendo que ocupes la metodología SDD (Spec Diven Depelovement), la ocupan los ingenieros de
IA para hacer una especie de vibecoding premiun que crea aplicaciones escalables y plenamente 
funcionales.
- **¿Cómo se usa?** Sencillo, pon un prompt así: Crea un plan para crear un análisis de social 
listering de x e instagram ocupando la skill social-listering-v2 (puedes pegar el link de github
acá para que no se pierda), de **(PONER TEMA y Keywords)** desde **(fecha inicio análisis)** a 
**(fecha término análisis)**. 
- Después lee el plan y ve conversando con la IA para refinarlo y ejecutar el análisis.
- Post análisis puedes pedir profundización en ciertos tópicos.

# Limitaciones:
- Al igual que el análisis de RRSS por API, solo lee cuentas públicas, no cuentas privadas.
- Solo lee los copy de los posteos, no los reels, eso es bastante complicado aún. 
- Los modelos estadounidenses (Claude,GPT,Gemini,Meta) y Mistral pueden poner problemas 
por el tema de términos y condiciones. Grok es bueno haciendo análisis en X y no es necesaria
la Skill, pero desconozco su funcionalidad en IG.
- Queda pendiente adaptaciones para otros harness de IA: Opencode, Hermes, Openclaw, Llama,
Deepseek etc.


Créditos: Juan Pablo González Urriola

# Documentación técnica:


## Qué produce

- `db/menciones.md` / `.csv` — una fila por publicación.
- `db/comentarios.md` / `.csv` — una fila por comentario, con sentimiento y texto.
- `output/nube_palabras*.png` — nubes generales (general, por plataforma) y de **conceptos**
  positivos/negativos. Las de conceptos incluyen **solo verbos y adjetivos, sin nombres propios**.
- `output/palabras_*.csv` — las frecuencias reales detrás de cada nube.
- `output/volumen_*.csv` — volumen por plataforma, por hora y por keyword.
- `output/grafico_por_hora.png` y `grafico_por_hora_<red>.png` — **posteos por hora**: uno general
  (X + Instagram) y uno por red social.
- `output/top_influencers.csv`, `top_posts.csv`, `top_comentarios.csv`, `temas.csv`,
  `frases_frecuentes.csv`, `sentimiento.csv` — rankings y agregados.
- `output/informe_<tema>_<fecha>.md` y `.docx` — el informe final.

> Si Instagram no entrega una hora fiable, su gráfico por hora se omite y el informe reporta el
> general y el de X, dejando constancia en la sección de límites.

## Requisitos

- Python 3.9 o superior.
- `agent-browser` disponible en el `PATH`.
- Un navegador instalado: **Chrome**, **Brave** o **Edge** (se detectan automáticamente; también
  sirve el Chromium empaquetado de `agent-browser` como último recurso).
- Dependencias de Python:

  ```bash
  pip install -r requirements.txt
  ```

- (Opcional, recomendado) POS tagging real para las nubes de conceptos:

  ```bash
  pip install spacy
  python -m spacy download es_core_news_sm
  ```

  Sin spaCy, el pipeline usa un fallback heurístico y termina igual.

## Cómo se usa

1. **Prepara un proyecto de trabajo** (una carpeta cualquiera, no la de la skill) y copia ahí:

   ```
   <proyecto>/scripts/                 <- copia scripts/ de esta skill
   <proyecto>/config/keywords.json     <- copia assets/templates/keywords.json
   <proyecto>/config/narrativa_conversacion.md   (opcional)
   ```

   Edita `config/keywords.json`: `tema`, `fecha_objetivo` (`YYYY-MM-DD`), `keywords`,
   `x_queries`, `ig_keywords` y `ig_media_accounts`.

2. **Inicia sesión una vez.** El primer arranque abre una ventana *headed* con un **perfil
   aislado** (`.browser-profiles/<navegador>`). Inicia sesión en X e Instagram en esa ventana. La
   sesión queda guardada en ese perfil; no se vuelve a pedir.

   ```bash
   python scripts/scrape_instagram.py --limit-per-source 3   # abre la ventana para el login
   ```

3. **Recolecta.**

   ```bash
   python scripts/scrape_instagram.py --limit-per-source 8
   python scripts/scrape_x_browser.py --scrolls 8 --reply-posts 40
   ```

4. **Consolida y genera el informe.**

   ```bash
   python scripts/build_md_db.py
   python scripts/build_deliverables.py
   ```

## Cómo funciona

### Fallback de navegador (Chrome → Brave → Edge)

`scripts/ab.py` resuelve el navegador de forma genérica y portable, en este orden:

1. `AB_EXECUTABLE` (ruta explícita) o `AB_BROWSER=chrome|brave|edge` (fuerza uno).
2. Rutas típicas de instalación de Windows.
3. `PATH` (`chrome` / `brave` / `msedge`).
4. Chromium empaquetado de `agent-browser`.

Si el navegador elegido no responde (no lanza o bloquea el login), `ensure_browser()` prueba el
siguiente de la cadena. Cada navegador usa su **propio perfil aislado** y su propia sesión, para que
nunca se mezclen ni se toquen tus sesiones reales.

### Seguridad de tus sesiones

- **Nunca** se usa tu perfil real de Chrome/Brave/Edge.
- **Nunca** se matan tus procesos de navegador: solo se cierra la sesión de `agent-browser`.
- No se borran ni modifican cookies de terceros. No hay likes, follows ni comentarios automáticos.

### Filtro de las nubes de conceptos

Las nubes positivas y negativas se calculan **solo sobre verbos y adjetivos**, sin nombres propios
ni sustantivos institucionales. Con spaCy (`es_core_news_sm`) se etiqueta gramaticalmente cada
token y se conservan los `VERB`/`ADJ`; sin spaCy, se aplica un heurístico por terminaciones de
verbo/adjetivo más el descarte de palabras que solo aparecen capitalizadas.

## Límites

- La cobertura es **parcial y no determinista**: los buscadores de X e Instagram devuelven un
  subconjunto, no todo.
- X puede pedir login o aplicar límites de tasa; Instagram sólo muestra contenido público visible
  con sesión iniciada.
- El sentimiento es orientativo (léxico español conservador); muchos textos quedan `sin_clasificar`.
- Las nubes muestran el top de términos; el detalle completo está en los CSV.
