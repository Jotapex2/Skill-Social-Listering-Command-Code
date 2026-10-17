# agent-browser en Windows: patrones que no se cuelgan

Extraído de sesiones reales de scraping de Instagram y X. Léelo antes de automatizar.

## 1. El deadlock de handles

No captures la salida de `agent-browser` por pipe. El daemon queda como hijo del shell, hereda el
handle de la tubería y nunca devuelve EOF, así que el padre espera para siempre.

```python
# MAL: se cuelga
subprocess.run(cmd, capture_output=True)

# MAL en PowerShell: también cuelga
agent-browser ... | Select-Object -First 20

# BIEN: redirigir a archivo o a NUL, y leer el archivo después
agent-browser --session s open "<url>" > NUL 2>&1
agent-browser --session s eval -b <base64> > "salida.txt" 2>&1
```

En PowerShell `>` también cuelga porque es PowerShell quien posee el pipe. Desde Python, la forma
robusta es `shell=True` con la redirección escrita **dentro** del string del comando.

## 2. Timeouts: no mates el árbol ni el navegador del usuario

```python
def run(cmd, timeout=120, kill_tree=False):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=timeout); return True
    except subprocess.TimeoutExpired:
        # taskkill /T mata también al daemon y obliga a relanzar el navegador en cada paso
        flags = "/F /T" if kill_tree else "/F"
        subprocess.run(f"taskkill {flags} /PID {p.pid} > NUL 2>&1", shell=True)
        return False
```

**Nunca** `taskkill /F /IM chrome.exe|brave.exe|msedge.exe`: rompe las sesiones del usuario.
Solo se mata el PID de la shell. Síntoma de daemon muerto: cada llamada imprime
`[agent-browser] launched browser` y la página queda en `about:blank`.

## 3. Sin concurrencia sobre una sesión

Una sesión (`--session`) es un único navegador. Si mientras corre un scraper lanzas otro
`open`/`eval`/`click` sobre la misma sesión, le cambias la página y el job produce basura **sin
fallar**. Corre el scraper y no toques esa sesión hasta que termine; para diagnosticar usa otra
sesión.

## 4. `eval` devuelve un string JSON escapado

```js
(() => { return JSON.stringify({a: [1, 2]}); })()
```

La salida en disco es `"{\"a\":[1,2]}"`, un string JSON. Hay que desenvolver en bucle
(`ab.eval_json` ya lo hace). Usa `eval -b <base64>` para pasar JS con comillas y saltos de línea
sin pelear con el shell.

## 5. Resolución y fallback de navegador (portable)

`scripts/ab.py` resuelve el navegador **sin rutas fijas de ninguna máquina**, en este orden:

1. `AB_EXECUTABLE` (ruta explícita) o `AB_BROWSER=chrome|brave|edge` (fuerza uno).
2. Rutas típicas de instalación (`%ProgramFiles%`, `%ProgramFiles(x86)%`, `%LocalAppData%`).
3. `PATH` (`chrome` / `brave` / `msedge`).
4. Chromium empaquetado de `agent-browser`.

Cada navegador usa su **propio perfil aislado** en `<proyecto>/.browser-profiles/<nombre>` y una
sesión `slv2-<nombre>`. Si el elegido no responde, `ab.ensure_browser()` prueba el siguiente
(Chrome → Brave → Edge → Chromium). Con `AB_BROWSER` forzado **no** se cambia de navegador.

Login sin detección (hazlo **una vez**, en ventana *headed*, sobre el perfil aislado):

```bash
agent-browser --session slv2-chrome --profile "<proyecto>/.browser-profiles/chrome" --headed \
  --executable-path "<ruta a chrome.exe>" \
  --args "--disable-blink-features=AutomationControlled,--exclude-switches=enable-automation,--start-maximized" \
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36" \
  open "https://www.instagram.com/accounts/login/"
```

Comprueba `navigator.webdriver === false` antes de pedir el login (`ab.probe()`).

## 6. Perfil del usuario: prohibido

Un `--profile` apuntando al perfil real (Brave/Chrome) falla con
`Failed to create a ProcessSingleton` si el navegador está abierto, y `Cookies` queda bloqueado en
exclusiva. Lanzarlo y luego matarlo puede dejar al usuario **deslogueado de todo**: su base
`Cookies` puede quedar con páginas liberadas y valores borrados de forma segura, sin recuperación.
Regla: perfil dedicado, vacío, y que el usuario loguee ahí **una vez**. Nunca se borran ni
modifican las cookies del usuario.
