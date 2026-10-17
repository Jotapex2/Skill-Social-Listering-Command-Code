"""Recolecta posts de Instagram (por keyword y cuentas de medios) con agent-browser.

Instagram se busca por KEYWORD (no hashtag). Se guarda caption, métricas, fecha y comentarios
visibles (`span[dir="auto"]`).

Uso:
    python scripts/scrape_instagram.py [--limit-per-source 8] [--only-keyword lluvia santiago]

Requiere una sesión iniciada UNA VEZ en el perfil aislado del navegador elegido (ver README.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "keywords.json"
CACHE = ab.RAW_IG / "_posts.jsonl"
LINKS = ab.RAW_IG / "_links.json"
PROGRESS = ab.RAW_IG / "_progress.log"


def log(msg: str) -> None:
    print(msg, flush=True)
    with PROGRESS.open("a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


LINKS_JS = r"""
JSON.stringify(Array.from(document.querySelectorAll('a'))
  .map(a => a.getAttribute('href'))
  .filter(h => h && (h.indexOf('/p/') >= 0 || h.indexOf('/reel/') >= 0 || h.indexOf('/tv/') >= 0))
  .filter((v, i, arr) => arr.indexOf(v) === i)
  .slice(0, 24))
"""

META_JS = r"""
(() => {
  const m = n => { const e = document.querySelector('meta[property="og:' + n + '"]'); return e ? (e.getAttribute('content') || '') : ''; };
  const t = document.querySelector('time[datetime]');
  const userLink = document.querySelector('header a[href^="/"]');
  const spans = Array.from(document.querySelectorAll('span[dir="auto"]'))
    .map(s => (s.innerText || '').replace(/\s+/g, ' ').trim());
  const tiempo = /^\d+\s*(s|sem|semanas?|d|d[ií]as?|h|horas?|min|m)$/i;
  const capt = [];
  for (let i = 0; i < spans.length; i++) {
    if (tiempo.test(spans[i])) {
      const nxt = spans[i + 1];
      if (nxt && nxt.length > 2 && !tiempo.test(nxt) && !/^\d[\d.,]*\s+(Me gusta|likes)/i.test(nxt)) {
        capt.push(nxt);
      }
    }
  }
  const comentarios = capt.filter((v, i, a) => a.indexOf(v) === i).slice(0, 60);
  return JSON.stringify({
    titulo: m('title'),
    descripcion: m('description'),
    url: m('url'),
    fecha_hora: t ? t.getAttribute('datetime') : '',
    autor: userLink ? userLink.getAttribute('href').replace(/\//g, '') : '',
    comentarios_texto: comentarios,
    comentarios_visibles: comentarios.length
  });
})()
"""

EXPAND_JS = r"""
(() => {
  let n = 0;
  const els = Array.from(document.querySelectorAll('div[role="button"], span[role="button"], button'));
  for (const e of els) {
    const t = (e.innerText || '').toLowerCase();
    if (/ver los .*comentario|view all .*comment|ver m[aá]s comentario|m[aá]s comentarios|ver .* respuesta/.test(t)) {
      try { e.click(); n++; } catch (err) {}
    }
  }
  return JSON.stringify(n);
})()
"""


def load_cache() -> dict[str, dict]:
    seen = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError:
                continue
            if p.get("post"):
                seen[p["post"]] = p
    return seen


def norm_url(href: str) -> str:
    h = str(href or "").split("?")[0]
    if not re.search(r"/(p|reel|tv)/", h):
        return ""
    if h.startswith("/"):
        h = "https://www.instagram.com" + h
    if not h.startswith("http"):
        return ""
    return h.rstrip("/") + "/"


def _valid(links) -> set[str]:
    out = set()
    for h in links or []:
        u = norm_url(h)
        if u:
            out.add(u)
    return out


def gather_links(url: str, tag: str) -> list[str]:
    ab.open_url(url, timeout=90)
    ab.wait(8)
    ab.scroll("down", 1600)
    ab.wait(3)
    seen = _valid(ab.eval_json(LINKS_JS, tag=f"ig_{tag}"))
    for extra in range(2):
        ab.scroll("down", 1800)
        ab.wait(2.5)
        seen |= _valid(ab.eval_json(LINKS_JS, tag=f"ig_{tag}_s{extra}"))
    return sorted(seen)


def fetch_post(url: str, tag: str, cache: dict[str, dict]) -> dict | None:
    if url in cache:
        return cache[url]
    if not ab.open_url(url, timeout=60):
        ab.close(ab.SESSION)
    ab.wait(6)
    ab.eval_json(EXPAND_JS, tag=f"igx_{tag}", timeout=45)
    ab.wait(2.5)
    ab.scroll("down", 1600)
    ab.wait(2)
    meta = ab.eval_json(META_JS, tag=f"igp_{tag}", timeout=60) or {}
    if not meta.get("descripcion"):
        ab.wait(4)
        ab.scroll("down", 1600)
        ab.wait(2)
        meta = ab.eval_json(META_JS, tag=f"igp2_{tag}", timeout=60) or meta
    post = {"post": url, "fuente": tag, **meta}
    if not post.get("descripcion") and not post.get("titulo"):
        return None
    with CACHE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(post, ensure_ascii=False) + "\n")
    cache[url] = post
    return post


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-per-source", type=int, default=8)
    ap.add_argument("--only-keyword", nargs="*", default=None)
    ap.add_argument("--skip-accounts", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    keywords = cfg.get("ig_keywords") or []
    if args.only_keyword:
        keywords = [" ".join(args.only_keyword)]

    if not ab.ensure_browser():
        raise SystemExit(
            f"No hay navegador operativo ({ab.describe()}). "
            "Instala/abre Chrome, Brave o Edge, o inicia sesión en el perfil aislado."
        )
    print(f"[ab] {ab.describe()}", flush=True)

    cache = load_cache()
    log(f"cache: {len(cache)} posts ya guardados")

    link_index: dict[str, list[str]] = {}
    if LINKS.exists():
        try:
            link_index = json.loads(LINKS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            link_index = {}

    sources: list[tuple[str, str]] = []
    for h in keywords:
        sources.append(
            (f"kw:{h}", f"https://www.instagram.com/explore/search/keyword/?q={quote(h)}")
        )
    if not args.skip_accounts and not args.only_keyword:
        for a in cfg.get("ig_media_accounts", []):
            sources.append((f"acct:{a}", f"https://www.instagram.com/{a}/"))

    total_new = 0
    for tag, url in sources:
        if tag in link_index and link_index[tag]:
            links = link_index[tag]
            log(f"[{tag}] {len(links)} links (cacheados)")
        else:
            log(f"[{tag}] abriendo {url}")
            links = gather_links(url, ab.slug(tag))
            link_index[tag] = links
            LINKS.write_text(json.dumps(link_index, ensure_ascii=False, indent=1), encoding="utf-8")
            log(f"[{tag}] {len(links)} links")
        for link in links[: args.limit_per_source]:
            if fetch_post(link, ab.slug(tag), cache):
                total_new += 1
                log(f"    + {link}")

    log(f"\nPosts en cache: {len(cache)} (nuevos esta corrida: {total_new})")


if __name__ == "__main__":
    main()
