"""Selecciona verbos y adjetivos (sin nombres propios) para las nubes de sentimiento.

Estrategia en dos capas:
1. Si spaCy + el modelo `es_core_news_sm` están disponibles, se usa POS tagging real y se
   conservan los tokens con `pos_ in {"VERB", "ADJ"}` (y se descartan entidades nombradas).
2. Si no, un heurístico conservador por terminaciones de verbo/adjetivo en español, más el
   descarte de nombres propios (tokens que solo aparecen capitalizados).

Uso:
    from pos import content_words, is_available
    permitidos = content_words(lista_de_textos)   # set de tokens normalizados
"""
from __future__ import annotations

import re
import unicodedata

# Stopwords ES mínimas (para no depender de otros módulos).
STOP = set("""a al algo algunas algunos ante antes aqui asi aun aunque como con contra cual cuales
cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos
esta estaba estan estar estas este esto estos fin fue fueron ha hace hacia han hasta hay la las le
les lo los mas me mi mientras mis mucho muchos muy nada ni no nos nosotros o os otra otras otro
otros para pero poco por porque primer que quien quienes se sea segun ser si sin sobre sois solo
son su sus tambien tanto te tener tiene tienen todo todos tu tus un una unas uno unos usted
vosotros y ya yo rt via https http www com instagram reel video videos q dia dias hoy ayer manana
ahora vamos ver gente lugar parte cosa cosas hacer dijo""".split())

# Sustantivos institucionales / genéricos que no aportan sentimiento.
NEUTRAL = set("""sindicato sindicatos empresa empresas compania companias gobierno estado ministerio
gremio gremios asociacion trabajadores trabajador region pais nacional sector servicio servicios
grupo holding sociedad corporacion institucion municipalidad comuna autoridades autoridad
empresario empresarios ministro subsecretario directorio gerente""".split())

_VERB_SUFFIX = (
    "ando", "iendo", "yendo", "ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas",
    "aba", "abas", "abamos", "aban", "ia", "ias", "iamos", "ian", "aron", "ieron", "aba",
    "iste", "imos", "aste", "asteis", "are", "ara", "eran", "ian", "amos", "emos", "imos",
)
_ADJ_SUFFIX = (
    "oso", "osa", "osos", "osas", "ble", "bles", "ivo", "iva", "ivos", "ivas", "ico", "ica",
    "icos", "icas", "al", "ales", "ente", "entes", "il", "iles", "esco", "esca", "oso",
)

TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")
PROPER = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")

_NLP = None
_NLP_TRIED = False


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _load_nlp():
    """Carga spaCy + es_core_news_sm, o None si no está disponible."""
    global _NLP, _NLP_TRIED
    if _NLP_TRIED:
        return _NLP
    _NLP_TRIED = True
    try:
        import spacy  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    for model in ("es_core_news_sm", "es_core_news_md", "es_core_news_lg"):
        try:
            _NLP = spacy.load(model)
            return _NLP
        except Exception:  # noqa: BLE001
            continue
    return None


def is_available() -> bool:
    """True si hay POS tagging real (spaCy + modelo español)."""
    return _load_nlp() is not None


def proper_nouns(texts) -> set[str]:
    """Tokens que aparecen SIEMPRE capitalizados (nombres propios). Si un token también aparece
    en minúscula, se considera palabra común."""
    has_lower, caps_only = set(), set()
    for txt in texts:
        for w in PROPER.findall(str(txt or "")):
            lw = norm(w)
            if w == w.lower():
                has_lower.add(lw)
            elif w != w.upper():
                caps_only.add(lw)
    return caps_only - has_lower


def _heuristic_word(word: str) -> bool:
    return word.endswith(_VERB_SUFFIX) or word.endswith(_ADJ_SUFFIX)


def content_words(texts) -> set[str]:
    """Devuelve el conjunto de tokens normalizados que son verbo o adjetivo (sin nombres propios).

    `texts` puede ser cualquier iterable de strings.
    """
    texts = [str(t or "") for t in texts]
    proper = proper_nouns(texts)
    allowed: set[str] = set()
    nlp = _load_nlp()
    if nlp is not None:
        for doc in nlp.pipe(texts):
            for tok in doc:
                if tok.pos_ not in ("VERB", "ADJ") or tok.is_stop:
                    continue
                if tok.ent_type_ in ("PER", "ORG", "LOC", "MISC"):
                    continue
                w = norm(tok.text)
                if len(w) < 3 or w in STOP or w in NEUTRAL or w in proper:
                    continue
                allowed.add(w)
        return allowed
    for txt in texts:
        for raw in TOKEN.findall(txt):
            w = norm(raw)
            if len(w) < 3 or w in STOP or w in NEUTRAL or w in proper:
                continue
            if _heuristic_word(w):
                allowed.add(w)
    return allowed
