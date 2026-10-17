"""Clasificador de sentimiento por léxico (español chileno), conservador.

Uso:
    from sentiment import classify
    etiqueta, puntaje = classify(texto)   # positivo | negativo | sin_clasificar
"""
from __future__ import annotations

import re
import unicodedata

POS = set("""bueno buena buenisimo excelente genial increible hermoso hermosa lindo linda
espectacular maravilloso maravillosa precioso bello bella rico rica delicioso feliz contento
alegre gracias bendicion amo encanta encanto mejor divertido chistoso gracioso bacan choris
limpia limpio refresca alivio esperanza solidaridad top wow jajaja jaja bonito disfrutar disfruto
emocionante apasionante agradable simpatico magico perfecto afortunado orgullo orgulloso
impresionante sorprendente amor carino tierno relindo bravo buenisima geniales hermosas preciosas
lindas magica gratitud dios""".split())

NEG = set("""malo mala malisimo pesimo terrible horrible horroroso feo fea desastre catastrofe caos
colapso inundacion inundado inundada anegado anegada dano danos destrozado destrozo peligro
peligroso emergencia emergencias evacuacion evacuados accidente muerto muerte herido heridos
tragedia miedo panico rabia enojo indignante vergonzoso negligencia culpa apagon tacos trafico
embotellamiento sucio asco harto odio lamentable preocupante grave crisis damnificados rescate
alerta roja sufrimiento dolor angustia estres asustado susto destruccion perdida perdidas colapsado
insoportable espantoso awful desgraciado bronca webeo molesto enojado frustrante frustracion""".split())

EMOJI = {"😀": 1, "😃": 1, "😄": 1, "😁": 1, "😂": 1, "🤣": 1, "🙌": 1, "❤": 1, "❤️": 1,
         "💚": 1, "😍": 1, "🥰": 1, "🌧": 0, "⛈": 0, "😭": -0.5, "😢": -1, "😡": -1,
         "🤬": -1, "😱": -1, "💀": -0.5, "🔥": 0.5, "☀": 0.5}

TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def classify(text: str) -> tuple[str, int]:
    """Devuelve (etiqueta, puntaje). Sin señal -> 'sin_clasificar'."""
    t = norm(text)
    score = 0
    for w in TOKEN.findall(t):
        if w in POS:
            score += 1
        elif w in NEG:
            score -= 1
    for emo, val in EMOJI.items():
        if emo in str(text):
            score += val
    if score > 0:
        return "positivo", int(score)
    if score < 0:
        return "negativo", int(score)
    return "sin_clasificar", 0
