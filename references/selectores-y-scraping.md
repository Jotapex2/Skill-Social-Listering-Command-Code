# Selectores y URLs: Instagram y X (solo navegador)

## Instagram

### URLs
- Búsqueda por keyword (la buena): `https://www.instagram.com/explore/search/keyword/?q=<texto>`
  (URL-encoded; `lluvia santiago` → `lluvia%20santiago`).
- `/explore/tags/<tag>/` **no sirve**: redirige a la búsqueda por keyword. Nadie usa hashtags.
- Perfil: `https://www.instagram.com/<usuario>/`.
- Post/reel: `https://www.instagram.com/p/<shortcode>/` o `/reel/<shortcode>/`.

### Links del grid
```js
JSON.stringify(Array.from(document.querySelectorAll('a'))
  .map(a => a.getAttribute('href'))
  .filter(h => h && (h.indexOf('/p/') >= 0 || h.indexOf('/reel/') >= 0 || h.indexOf('/tv/') >= 0))
  .filter((v, i, arr) => arr.indexOf(v) === i)
  .slice(0, 24))
```
Valida siempre el resultado contra `/(p|reel|tv)/` antes de usarlo: un parseo roto devuelve
caracteres sueltos (`"/`, `0/`) que parecen links.

### Datos de una publicación
Las meta `og:` son lo más estable (vienen en el HTML y sobreviven al SPA):

```js
(() => {
  const m = n => { const e = document.querySelector('meta[property="og:' + n + '"]');
                   return e ? (e.getAttribute('content') || '') : ''; };
  const t = document.querySelector('time[datetime]');
  const userLink = document.querySelector('header a[href^="/"]');
  const spans = Array.from(document.querySelectorAll('span[dir="auto"]'))
    .map(s => (s.innerText || '').replace(/\s+/g, ' ').trim());
  const tiempo = /^\d+\s*(s|sem|semanas?|d|d[ií]as?|h|horas?|min|m)$/i;
  const comentarios = [];
  for (let i = 0; i < spans.length; i++) {
    if (tiempo.test(spans[i])) {
      const nxt = spans[i + 1];
      if (nxt && nxt.length > 2 && !tiempo.test(nxt) &&
          !/^\d[\d.,]*\s+(Me gusta|likes)/i.test(nxt)) comentarios.push(nxt);
    }
  }
  return JSON.stringify({
    titulo: m('title'), descripcion: m('description'), url: m('url'),
    fecha_hora: t ? t.getAttribute('datetime') : '',
    autor: userLink ? userLink.getAttribute('href').replace(/\//g, '') : '',
    comentarios_texto: comentarios.filter((v, i, a) => a.indexOf(v) === i).slice(0, 60)
  });
})()
```

`og:description` trae todo junto y es parseable:
`"75K likes, 1,716 comments - usuario el October 13, 2026: \"caption\"."`

```python
re.match(r"\s*([\d.,]+[KMB]?)\s+(?:likes|Me gusta)\s*,\s*([\d.,]+[KMB]?)\s+comments", desc, re.I)
re.search(r"-\s*([\w.]+)\s+(?:on|el)\s+([A-Za-z]+ \d{1,2}, \d{4})", desc)
```

La **hora** sale de `time[datetime]` (`fecha_hora`). Si viene vacía, Instagram **no** aporta hora
y su gráfico por hora se omite (se reportan el general y el de X).

### Comentarios: no hay `ul`
Las páginas de post no tienen `UL`. Los comentarios viven en `span[dir="auto"]`, y el texto sigue al
span del tiempo (`37 sem`, `2 d`, `1 h`). Ver el bloque de arriba.

En `/reel/` los comentarios **no están en el DOM** hasta abrir el panel:
`[aria-label="Comentario"]` (o `"Comment"`). Es un **SVG**, así que `element.click()` falla con
`TypeError: b.click is not a function`: usa `ab.click('[aria-label="Comentario"]')`.

Si el actor limita los comentarios, IG muestra "Se han limitado los comentarios": regístralo como
hallazgo.

### Ritmo
Abriendo permalink: ~7 s de espera y reintento si `og:description` viene vacío. Un post completo con
comentarios tarda ~13 s. Cuentas de medios dan ~8-12 links recientes; la búsqueda por keyword suele
dar solo ~4 (prioriza popular, no reciente).

## X (Twitter) — scraping de navegador

### Búsqueda con ventana de fecha
```
https://x.com/search?q=<query>%20since:<YYYY-MM-DD>%20until:<YYYY-MM-DD+1>
```
**Sin `&f=live`**: la pestaña **Top** respeta `since:`/`until:`. Con `f=live` el filtro de fecha se
ignora y devuelve lo más reciente. Es el error más caro.

### Posts
```js
document.querySelectorAll('article[data-testid="tweet"]').forEach(a => {
  const textEl  = a.querySelector('[data-testid="tweetText"]');
  const userName= a.querySelector('[data-testid="User-Name"]');
  const timeEl  = a.querySelector('time');                       // .getAttribute('datetime')
  const linkEl  = timeEl ? timeEl.closest('a') : null;           // .href = permalink
  // métricas: aria-label de [data-testid="like"|"retweet"|"reply"] (p. ej. "12 mil Me gusta")
});
```
El handle sale de una línea que empieza con `@` dentro de `User-Name`; el nombre, de la primera.

### Comentarios (sin API)
Abre el permalink `https://x.com/<handle>/status/<id>`, espera ~7 s, expande los hilos
("Show more replies" / "Show probable spam" / "Mostrar más respuestas") por click, haz scroll y
vuelve a extraer `article[data-testid="tweet"]`. **Descarta el primer artículo (el tuit focal)**:
filtra el que tenga la misma URL canónica que el permalink. Guarda autor, texto, likes, fecha y URL.
Declara rate limit o muro de login como límite.

### Parseo de fechas
`createdAt`/`datetime` de X llega en ISO (`2026-10-13T18:12:36.000Z`). Si en algún caso llegara en
formato Twitter (`Wed Oct 14 12:32:36 +0000 2026`), un parser ISO lo falla **en silencio**;
`build_md_db.py` ya prueba también `%a %b %d %H:%M:%S %z %Y`.
