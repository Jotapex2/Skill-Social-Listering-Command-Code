"""Consolida los crudos de X (navegador) e Instagram en una BBDD Markdown + CSV.

Fuentes esperadas:
    data/raw/x/_browser.json            posts de X con su lista de comentarios
    data/raw/instagram/_posts.jsonl     posts de Instagram (una línea por post)

Uso:
    python scripts/build_md_db.py [--fecha YYYY-MM-DD] [--incluir-otros-dias]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sentiment import classify

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "keywords.json"
RAW_X = ROOT / "data" / "raw" / "x" / "_browser.json"
RAW_X_ALL = ROOT / "data" / "raw" / "x" / "_all.json"
RAW_IG = ROOT / "data" / "raw" / "instagram" / "_posts.jsonl"
DB = ROOT / "db"
TZ = ZoneInfo("America/Santiago")

COLS = [
    "id", "plataforma", "autor", "nombre", "fecha_hora", "hora_local", "texto",
    "comentarios_texto", "n_comentarios_texto", "likes", "comentarios", "reposts",
    "vistas", "url", "keywords_match", "lugar", "tipo_cuenta", "tema", "tono", "evidencia",
]

COLS_COMENTARIOS = [
    "plataforma", "post_url", "autor", "comentario", "sentimiento", "likes", "fecha_hora",
]

MEDIOS = {
    "biobiochile", "lacuarta", "latercera", "meganoticias", "tvn", "chilevision",
    "24horas.cl", "cooperativa", "cnnchile", "radioagricultura", "t13",
    "elmostrador", "diariofinanciero", "grupoprensadigital", "t13.cl",
    "chvnoticias", "adnradiochile", "publimetrochile", "eldinamo",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_ig_desc(desc: str) -> dict:
    out = {}
    m = re.match(
        r"\s*([\d.,]+[KMB]?)\s+(?:likes|Me gusta)\s*,\s*([\d.,]+[KMB]?)\s+comments",
        desc or "", re.I,
    )
    if m:
        out["likes"], out["comentarios"] = m.group(1), m.group(2)
    else:
        m2 = re.match(r"\s*([\d.,]+[KMB]?)\s+(?:views|reproducciones)", desc or "", re.I)
        if m2:
            out["vistas"] = m2.group(1)
    m3 = re.search(r"-\s*([\w.]+)\s+(?:on|el)\s+([A-Za-z]+ \d{1,2}, \d{4})", desc or "")
    if m3:
        out["ig_user"] = m3.group(1)
        try:
            out["ig_date"] = datetime.strptime(m3.group(2), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    m4 = re.search(r":\s*\"(.*)", desc or "", re.S)
    if m4:
        out["ig_caption"] = m4.group(1).rstrip('"')
    return out


TW_FORMATS = ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z")


def to_local(iso: str) -> tuple[str, str]:
    if not iso:
        return "", ""
    s = str(iso).strip()
    dt = None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        for fmt in TW_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return s, ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    loc = dt.astimezone(TZ)
    return loc.strftime("%Y-%m-%d %H:%M"), loc.strftime("%Y-%m-%d")


def keywords_in(text: str, kws: list[str]) -> str:
    t = norm(text)
    return "; ".join(k for k in kws if norm(k) in t)


def guess_tema(text: str, kws: list[str]) -> str:
    t = norm(text)
    for k in kws:
        if norm(k) in t:
            return k
    return "otros"


def load_x() -> list[dict]:
    src = RAW_X if RAW_X.exists() else RAW_X_ALL
    if not src.exists():
        return []
    rows = []
    for t in json.loads(src.read_text(encoding="utf-8")):
        fecha_hora, dia = to_local(t.get("fecha_hora", ""))
        rows.append({
            "id": "x:" + (t.get("url", "") or "").rstrip("/").rsplit("/", 1)[-1],
            "plataforma": "x",
            "autor": t.get("handle", ""),
            "nombre": t.get("nombre", ""),
            "fecha_hora": t.get("fecha_hora", ""),
            "hora_local": fecha_hora,
            "texto": t.get("texto", ""),
            "likes": t.get("likes", ""), "comentarios": t.get("respuestas", ""),
            "reposts": t.get("reposts", ""), "vistas": t.get("vistas", ""),
            "url": t.get("url", ""), "dia": dia,
            "comentarios_full": t.get("comentarios") or [
                {"autor": "", "texto": c, "likes": "", "url": ""}
                for c in (t.get("comentarios_texto") or [])
            ],
        })
    return rows


def load_ig() -> list[dict]:
    if not RAW_IG.exists():
        return []
    rows = []
    for line in RAW_IG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            p = json.loads(line)
        except json.JSONDecodeError:
            continue
        meta = parse_ig_desc(p.get("descripcion", ""))
        fecha_hora, dia = to_local(p.get("fecha_hora", ""))
        if not dia and meta.get("ig_date"):
            dia = meta["ig_date"]
        texto = meta.get("ig_caption") or p.get("titulo", "")
        rows.append({
            "id": "ig:" + (p.get("post", "") or "").rstrip("/").rsplit("/", 1)[-1],
            "plataforma": "instagram",
            "autor": meta.get("ig_user") or p.get("autor", ""),
            "nombre": meta.get("ig_user") or p.get("autor", ""),
            "fecha_hora": p.get("fecha_hora", ""),
            "hora_local": fecha_hora,
            "texto": texto,
            "likes": meta.get("likes", ""), "comentarios": meta.get("comentarios", ""),
            "reposts": "", "vistas": meta.get("vistas", ""),
            "url": p.get("url") or p.get("post", ""), "dia": dia,
            "fuente": p.get("fuente", ""),
            "comentarios_full": [
                {"autor": "", "texto": c, "likes": "", "url": ""}
                for c in (p.get("comentarios_texto") or [])
            ],
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fecha", default=None)
    ap.add_argument("--incluir-otros-dias", action="store_true")
    ap.add_argument("--filtrar-off-topic", action="store_true",
                    help="Descartar publicaciones sin ninguna keyword en el texto")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    tema = cfg.get("tema", "conversación")
    fecha = args.fecha or cfg["fecha_objetivo"]
    kws = cfg["keywords"]

    raw = load_x() + load_ig()
    print(f"crudos: {len(raw)}")

    others = [r for r in raw if r.get("dia") and r["dia"] != fecha]
    raw = [r for r in raw if args.incluir_otros_dias or r.get("dia") == fecha]
    print(f"del {fecha}: {len(raw)}  (descartados de otros dias: {len(others)})")

    seen, records, all_comments = set(), [], []
    off_topic = 0
    for r in raw:
        url = (r.get("url") or "").rstrip("/")
        key = url or r["id"]
        if key in seen:
            continue
        seen.add(key)
        r["keywords_match"] = keywords_in(r.get("texto", ""), kws)
        if not r["keywords_match"] and args.filtrar_off_topic:
            off_topic += 1
            continue
        autor_key = norm(r.get("autor", "")).lstrip("@")
        r["tipo_cuenta"] = "medio" if autor_key in {norm(m) for m in MEDIOS} else "usuario"
        r["tema"] = guess_tema(r.get("texto", ""), kws)
        r["lugar"] = ""
        r["tono"] = classify(r.get("texto", ""))[0]
        r["evidencia"] = r.get("fuente", "")
        comments = []
        for c in r.get("comentarios_full") or []:
            if not (c.get("texto") or "").strip():
                continue
            comments.append(c)
        r["n_comentarios_texto"] = len(comments)
        r["comentarios_texto"] = " || ".join(
            re.sub(r"\s+", " ", c.get("texto", "") or "").strip() for c in comments
        )
        records.append(r)
        for c in comments:
            all_comments.append({
                "plataforma": r["plataforma"], "post_url": r["url"],
                "autor": c.get("autor", ""), "comentario": c.get("texto", ""),
                "sentimiento": classify(c.get("texto", ""))[0],
                "likes": c.get("likes", ""), "fecha_hora": c.get("fecha_hora", ""),
            })

    records.sort(key=lambda r: (r["plataforma"], r.get("hora_local", "")))

    DB.mkdir(parents=True, exist_ok=True)
    with (DB / "menciones.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    def cell(v, limit=400):
        s = str(v or "").replace("|", "¦").replace("\n", " ").replace("\r", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s[:limit] + ("…" if len(s) > limit else "")

    lines = [
        f"# BBDD — Conversación sobre {tema}",
        "",
        f"- **Fecha cubierta:** {fecha} (hora local America/Santiago)",
        f"- **Registros:** {len(records)}",
        f"- **Plataformas:** " + ", ".join(sorted({r["plataforma"] for r in records})),
        f"- **Keywords:** {', '.join(kws)}",
        f"- **Registros de otros días descartados:** {len(others)}",
        f"- **Publicaciones sin keyword descartadas (off-topic):** {off_topic}",
        "- **Cobertura:** parcial y no exhaustiva; ver informe para límites.",
        "",
        "| " + " | ".join(COLS) + " |",
        "|" + "---|" * len(COLS),
    ]
    for r in records:
        lines.append("| " + " | ".join(cell(r.get(c, "")) for c in COLS) + " |")
    (DB / "menciones.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (DB / "comentarios.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS_COMENTARIOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_comments)

    clines = [
        f"# Comentarios — {tema}",
        "",
        f"- **Fecha cubierta:** {fecha}",
        f"- **Comentarios:** {len(all_comments)}",
        "",
        "| " + " | ".join(COLS_COMENTARIOS) + " |",
        "|" + "---|" * len(COLS_COMENTARIOS),
    ]
    for c in all_comments:
        clines.append("| " + " | ".join(cell(c.get(k, "")) for k in COLS_COMENTARIOS) + " |")
    (DB / "comentarios.md").write_text("\n".join(clines) + "\n", encoding="utf-8")

    print(f"-> {DB/'menciones.md'}  ({len(records)} filas)")
    print(f"-> {DB/'menciones.csv'}")
    print(f"-> {DB/'comentarios.md'}  ({len(all_comments)} comentarios)")
    print(f"-> {DB/'comentarios.csv'}")


if __name__ == "__main__":
    main()
