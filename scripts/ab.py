"""Helper para manejar agent-browser desde Python en Windows, sin el deadlock de pipes.

Reglas clave:
- `open`/`close` redirigen a NUL; `eval`/`get text` redirigen a un archivo propio que luego se
  lee. Nunca se captura la salida por pipe: el daemon hereda el handle y el proceso no termina.
- El navegador se resuelve de forma GENÉRICA y portable: variable de entorno -> rutas típicas de
  Windows -> PATH -> Chromium empaquetado de agent-browser. Nunca se usa el perfil real del usuario.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_X = ROOT / "data" / "raw" / "x"
RAW_IG = ROOT / "data" / "raw" / "instagram"
TMP = ROOT / "data" / "raw" / "_tmp"
for _d in (RAW_X, RAW_IG, TMP):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Resolución de navegador: Chrome -> Brave -> Edge -> Chromium empaquetado
# --------------------------------------------------------------------------------------
_CANDIDATES = {
    "chrome": (
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    ),
    "brave": (
        r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ),
    "edge": (
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe",
    ),
}
_ORDER = ("chrome", "brave", "edge")
_PATH_BIN = {"chrome": "chrome", "brave": "brave", "edge": "msedge"}


def find_executable(name: str) -> str:
    """Ruta al ejecutable de un navegador conocido, o '' si no está instalado."""
    for template in _CANDIDATES.get(name, ()):
        path = os.path.expandvars(template)
        if os.path.isfile(path):
            return path
    return shutil.which(_PATH_BIN.get(name, name)) or ""


def available_browsers() -> list[tuple[str, str]]:
    """[(nombre, ruta_exe)] de los navegadores instalados, en orden de preferencia."""
    out = []
    for name in _ORDER:
        exe = find_executable(name)
        if exe:
            out.append((name, exe))
    return out


def _initial_browser() -> tuple[str, str]:
    forced = os.environ.get("AB_EXECUTABLE", "").strip()
    if forced:
        return ("custom", forced)
    want = os.environ.get("AB_BROWSER", "").strip().lower()
    if want in _ORDER:
        return (want, find_executable(want))
    avail = available_browsers()
    if avail:
        return avail[0]
    return ("bundled", "")


_BROWSER_NAME, EXECUTABLE = _initial_browser()
SESSION = os.environ.get("AB_SESSION", f"slv2-{_BROWSER_NAME}")
PROFILE = os.environ.get("AB_PROFILE", str(ROOT / ".browser-profiles" / _BROWSER_NAME))
HEADED = os.environ.get("AB_HEADED", "1") == "1"
UA = os.environ.get(
    "AB_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
)
LAUNCH_ARGS = os.environ.get(
    "AB_ARGS",
    "--disable-blink-features=AutomationControlled,"
    "--exclude-switches=enable-automation,--start-maximized",
)


def describe() -> str:
    exe = EXECUTABLE or "(Chromium empaquetado de agent-browser)"
    return f"navegador={_BROWSER_NAME} exe={exe} sesion={SESSION} perfil={PROFILE}"


def select_browser(name: str) -> bool:
    """Cambia a otro navegador para el fallback. Cierra la sesión anterior. True si cambió."""
    global _BROWSER_NAME, EXECUTABLE, SESSION, PROFILE
    exe = find_executable(name)
    if name != "bundled" and not exe:
        return False
    close(SESSION)
    _BROWSER_NAME, EXECUTABLE = name, exe
    SESSION = os.environ.get("AB_SESSION", f"slv2-{name}")
    PROFILE = os.environ.get("AB_PROFILE", str(ROOT / ".browser-profiles" / name))
    return True


def _profile_args() -> str:
    parts = []
    if EXECUTABLE:
        parts.append(f'--executable-path "{EXECUTABLE}"')
    if PROFILE:
        parts.append(f'--profile "{PROFILE}"')
    if HEADED:
        parts.append("--headed")
    if LAUNCH_ARGS:
        parts.append(f'--args "{LAUNCH_ARGS}"')
    if UA:
        parts.append(f'--user-agent "{UA}"')
    return " ".join(parts)


def run(cmd: str, timeout: int = 120, kill_tree: bool = False) -> bool:
    """Ejecuta un comando de agent-browser.

    En timeout NO se mata el árbol por defecto: matar el árbol tumba el daemon (que es padre del
    proceso) y obliga a relanzar el navegador en cada paso. Además, jamás se matan procesos del
    navegador del usuario: solo el PID de esta shell.
    """
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        proc.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        flags = "/F /T" if kill_tree else "/F"
        subprocess.run(f"taskkill {flags} /PID {proc.pid} > NUL 2>&1", shell=True)
        return False


def open_url(url: str, timeout: int = 90) -> bool:
    return run(
        f'agent-browser --session {SESSION} {_profile_args()} open "{url}" > NUL 2>&1',
        timeout=timeout,
    )


def close(session: str | None = None) -> None:
    s = session or SESSION
    run(f"agent-browser --session {s} close > NUL 2>&1", timeout=60)


def close_all() -> None:
    run("agent-browser close --all > NUL 2>&1", timeout=120)


def click(selector: str, timeout: int = 60) -> bool:
    return run(
        f'agent-browser --session {SESSION} click "{selector}" > NUL 2>&1', timeout=timeout
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def eval_js(js: str, tag: str = "ev", timeout: int = 90) -> str:
    """Ejecuta JS y devuelve el texto crudo de salida."""
    b64 = base64.b64encode(js.encode("utf-8")).decode("ascii")
    out = TMP / f"{tag}.out"
    if out.exists():
        out.unlink()
    run(
        f'agent-browser --session {SESSION} eval -b {b64} > "{out}" 2>&1',
        timeout=timeout,
    )
    return _read(out)


def eval_json(js: str, tag: str = "ev", timeout: int = 90):
    """Parsea el resultado de eval. agent-browser suele envolver la salida como un string JSON
    con comillas escapadas, así que hay que desenvolverla en bucle."""
    raw = eval_js(js, tag=tag, timeout=timeout).strip()
    if not raw:
        return None
    queue, seen = [raw], set()
    while queue:
        cand = queue.pop(0).strip()
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            if isinstance(parsed, str):
                queue.append(parsed)
                continue
            return parsed
        pair = {"{": ("{", "}"), "[": ("[", "]")}.get(cand[0])
        if not pair:
            continue
        i, j = cand.find(pair[0]), cand.rfind(pair[1])
        if i == -1 or j <= i:
            continue
        try:
            inner = json.loads(cand[i : j + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(inner, str):
            queue.append(inner)
        else:
            return inner
    return None


def get_text(tag: str, timeout: int = 90) -> str:
    out = TMP / f"{tag}.txt"
    if out.exists():
        out.unlink()
    run(
        f'agent-browser --session {SESSION} get text body > "{out}" 2>&1',
        timeout=timeout,
    )
    return _read(out)


def scroll(direction: str = "down", px: int = 2500) -> None:
    run(
        f"agent-browser --session {SESSION} scroll {direction} {px} > NUL 2>&1",
        timeout=60,
    )


def wait(seconds: float) -> None:
    time.sleep(seconds)


def probe(timeout: int = 60) -> bool:
    """Comprueba que el navegador responde y no expone navigator.webdriver."""
    if not open_url("about:blank", timeout=timeout):
        return False
    return eval_json("navigator.webdriver === false", tag="ab_probe", timeout=timeout) is True


def ensure_browser(allow_bundled: bool = True) -> bool:
    """Prueba el navegador en uso y, si no responde, intenta los siguientes (Chrome -> Brave ->
    Edge -> Chromium empaquetado). Devuelve True si alguno quedó operativo.

    Si `AB_BROWSER` está forzado, se respeta y NO se cambia de navegador.
    """
    if os.environ.get("AB_BROWSER", "").strip().lower() in _ORDER:
        return probe()
    order = [name for name, _ in available_browsers()]
    if allow_bundled:
        order.append("bundled")
    if _BROWSER_NAME in order:
        order.remove(_BROWSER_NAME)
    order.insert(0, _BROWSER_NAME)
    for name in order:
        if name != _BROWSER_NAME and not select_browser(name):
            continue
        if probe():
            print(f"[ab] navegador operativo: {describe()}", flush=True)
            return True
    return False


def slug(text: str, keep: int = 60) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", str(text)).strip("_").lower()
    return s[:keep] or "item"
