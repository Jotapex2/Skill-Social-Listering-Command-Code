"""Recolecta X (Twitter) con agent-browser — SIN API — incluyendo posts y comentarios.

Hallazgo clave: la búsqueda de X respeta `since:`/`until:` SÓLO en la pestaña "Top" (URL sin
`&f=live`). Con `f=live` el filtro de fecha se ignora y devuelve lo más reciente.

Los comentarios se toman abriendo el permalink de cada post y extrayendo los artículos de la
vista de conversación (se descarta el tuit focal).

Uso:
    python scripts/scrape_x_browser.py [--scrolls 8] [--max-por-query 200] [--reply-posts 40]

Requiere una sesión iniciada UNA VEZ en el perfil aislado del navegador elegido (ver README.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "keywords.json"
OUT = ab.RAW_X / "_browser.json"

EXTRACT_JS = r"""
(() => {
  const out = [];
  document.querySelectorAll('article[data-testid="tweet"]').forEach(a => {
    const textEl = a.querySelector('[data-testid="tweetText"]');
    const userName = a.querySelector('[data-testid="User-Name"]');
    const timeEl = a.querySelector('time');
    const linkEl = timeEl ? timeEl.closest('a') : null;
    const lines = userName ? (userName.innerText || '').split('\n').map(s => s.trim()).filter(Boolean) : [];
    const cnt = sel => {
      const e = a.querySelector(sel);
      if (!e) return '';
      const t = e.getAttribute('aria-label') || '';
      const m = t.match(/^\s*([\d][\d.,]*(?:\s*(?:mil|millones|M|K))?)(?=\s|$)/i);
      return m ? m[1].replace(/\s+/g, ' ') : '';
    };
    const viewEl = a.querySelector('a[href*="/analytics"]');
    out.push({
      handle: lines.find(x => x.startsWith('@')) || '',
      nombre: lines[0] || '',
      texto: textEl ? textEl.innerText : '',
      fecha_hora: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
      url: linkEl ? linkEl.href : '',
      likes: cnt('[data-testid="like"]'),
      reposts: cnt('[data-testid="retweet"]'),
      respuestas: cnt('[data-testid="reply"]'),
      vistas: viewEl ? (viewEl.innerText || '').replace(/\s/g, '') : ''
    });
  });
  return JSON.stringify(out);
})()
"""

# Expande hilos de respuestas ("Mostrar más respuestas", spam probable, etc.).
EXPAND_JS = r"""
(() => {
  let n = 0;
  const els = Array.from(document.querySelectorAll('[role="button"], button, span'));
  for (const e of els) {
    const t = (e.innerText || '').toLowerCase();
    if (/show more replies|show probable spam|show additional replies|mostrar m[aá]s respuestas|mostrar spam probable/.test(t)) {
      try { e.click(); n++; } catch (err) {}
    }
  }
  return JSON.stringify(n);
})()
"""


def url_top(query: str, fecha: str) -> str:
    """Sin `f=live`: la pestaña Top respeta since:/until:."""
    hasta = (datetime.strptime(fecha, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    return "https://x.com/search?q=" + quote(f"{query} since:{fecha} until:{hasta}")


def _norm_url(u: str) -> str:
    return re.sub(r"[?#].*$", "", str(u or "")).rstrip("/")


def parse_num(v) -> int:
    if v is None:
        return 0
    s = str(v).strip().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KMBkmb])?(?![A-Za-z])", s)
    if not m:
        return 0
    try:
        n = float(m.group(1))
    except ValueError:
        return 0
    return int(n * {"k": 1e3, "m": 1e6, "b": 1e9}.get((m.group(2) or "").lower(), 1))


def collect_query(query: str, fecha: str, scrolls: int, max_por_query: int) -> dict[str, dict]:
    url = url_top(query, fecha)
    print(f"  -> {query}", flush=True)
    ab.open_url(url, timeout=90)
    ab.wait(7)
    posts: dict[str, dict] = {}
    for i in range(scrolls):
        for t in ab.eval_json(EXTRACT_JS, tag=f"xb_{ab.slug(query)}_{i}", timeout=60) or []:
            key = t.get("url") or (t.get("handle", "") + "|" + t.get("texto", ""))
            if key and key not in posts and len(posts) < max_por_query:
                t["query_origen"] = query
                posts[key] = t
        ab.scroll("down", 2600)
        ab.wait(2.2)
    n = sum(1 for p in posts.values() if p.get("fecha_hora", "").startswith(fecha))
    print(f"     {len(posts)} posts ({n} del {fecha})", flush=True)
    return posts


def collect_replies(permalink: str, tag: str) -> list[dict]:
    """Abre el permalink y extrae los comentarios (artículos), descartando el tuit focal."""
    ab.open_url(permalink, timeout=90)
    ab.wait(7)
    for _ in range(3):
        ab.eval_json(EXPAND_JS, tag=f"xexp_{tag}", timeout=45)
        ab.wait(1.2)
    ab.scroll("down", 2600)
    ab.wait(2)
    for i in range(3):
        ab.eval_json(EXPAND_JS, tag=f"xexp_{tag}_{i}", timeout=45)
        ab.scroll("down", 2600)
        ab.wait(2)
    focal = _norm_url(permalink)
    replies, seen = [], set()
    for t in ab.eval_json(EXTRACT_JS, tag=f"xr_{tag}", timeout=60) or []:
        u = _norm_url(t.get("url", ""))
        if u and u == focal:
            continue
        texto = (t.get("texto") or "").strip()
        if not texto:
            continue
        k = u or (t.get("handle", "") + "|" + texto)
        if k in seen:
            continue
        seen.add(k)
        replies.append({
            "autor": t.get("handle", ""),
            "nombre": t.get("nombre", ""),
            "texto": texto,
            "fecha_hora": t.get("fecha_hora", ""),
            "likes": t.get("likes", ""),
            "url": t.get("url", ""),
        })
    return replies


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scrolls", type=int, default=8)
    ap.add_argument("--max-por-query", type=int, default=200)
    ap.add_argument("--reply-posts", type=int, default=40,
                    help="Cuántos posts (por engagement) se abren para extraer comentarios")
    ap.add_argument("--sin-comentarios", action="store_true")
    ap.add_argument("--queries", nargs="*", default=None)
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    fecha = cfg["fecha_objetivo"]
    queries = args.queries or cfg["x_queries"]

    if not ab.ensure_browser():
        raise SystemExit(
            f"No hay navegador operativo ({ab.describe()}). "
            "Instala/abre Chrome, Brave o Edge, o inicia sesión en el perfil aislado."
        )
    print(f"[ab] {ab.describe()}", flush=True)

    posts: dict[str, dict] = {}
    for q in queries:
        posts.update(collect_query(q, fecha, args.scrolls, args.max_por_query))

    if not args.sin_comentarios and args.reply_posts > 0:
        target = sorted(
            posts.values(),
            key=lambda p: parse_num(p.get("likes")) + parse_num(p.get("respuestas")),
            reverse=True,
        )[: args.reply_posts]
        print(f"\nBuscando comentarios en {len(target)} posts", flush=True)
        for i, p in enumerate(target, 1):
            link = p.get("url")
            if not link:
                continue
            reps = collect_replies(link, tag=ab.slug(link))
            p["comentarios"] = reps
            p["comentarios_texto"] = [r["texto"] for r in reps]
            print(f"    [{i}/{len(target)}] {p.get('handle','')}: +{len(reps)} comentarios", flush=True)

    for p in posts.values():
        p.setdefault("comentarios", [])
        p.setdefault("comentarios_texto", [])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(list(posts.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    total_comments = sum(len(p.get("comentarios", [])) for p in posts.values())
    print(f"\nX (browser): {len(posts)} posts, {total_comments} comentarios -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
