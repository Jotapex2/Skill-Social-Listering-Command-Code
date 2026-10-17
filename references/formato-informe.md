# Formato del informe

El informe se genera en `output/informe_<tema>_<fecha>.md` y `.docx` con esta estructura, calcada
del informe modelo del proyecto Lluvias. `build_deliverables.py` la produce; este documento es la
referencia para revisar y para redactar la narrativa.

## Estructura

1. **Título:** `# Social listening — <tema> (<fecha>)`.
2. **Resumen ejecutivo:** total de publicaciones del día, plataformas, keywords, suma de likes,
   comentarios y reposteos, y cuántos comentarios se recolectaron.
3. **Resumen de la conversación:** narrativa inyectada desde `config/narrativa_conversacion.md`
   (línea de tiempo, eje del relato, marco institucional, conversaciones paralelas, engagement,
   tono). Si el archivo no existe, se omite la sección.
4. **Metodología:** recolección solo por scraping de navegador (X por búsqueda con `since/until`,
   Instagram por keyword), unidad de conteo deduplicada por URL canónica, fechas en
   `America/Santiago`.
5. **Volumen de conversación:** tabla por plataforma (posts, likes, comentarios, reposts,
   engagement, autores únicos) + tabla de posts por keyword.
6. **Posteos por hora:** frase de peak, **tabla** hora/Posts/% del total, **gráfico general**
   (`grafico_por_hora.png`) y **gráfico por red** (`grafico_por_hora_x.png` y, si aplica,
   `grafico_por_hora_instagram.png`).
7. **Top 5 influencers por plataforma:** ranking por cantidad de posteos, desempate por engagement.
8. **Nube de palabras:** imagen general (sustantivos permitidos) + conteo de términos.
9. **Conceptos positivos y negativos:** clasificación por léxico conservador, declarando que las
   nubes incluyen **solo verbos y adjetivos** (sin nombres propios ni sustantivos institucionales);
   imágenes positiva y negativa.
10. **Conversaciones más frecuentes:** temas (por keyword matcheada) con ejemplos enlazados +
    frases más repetidas.
11. **Comentarios:** total recolectado por plataforma + tabla con autor, likes, texto y enlace.
12. **Publicaciones con más engagement:** tabla con las top publicaciones y su enlace.
13. **Sentimiento: positivo, negativo y neutro:** tabla por alcance (posts/comentarios).
14. **Límites:** cobertura parcial, muro de login/rate limit en X, contenido público de IG,
    sentimiento orientativo y alcance del top de las nubes. Si Instagram no aportó hora, se declara
    que su gráfico por hora se omitió.

## Reglas

- Toda afirmación factual debe llevar su enlace.
- Las cifras de las tablas y la narrativa deben cuadrar con los CSV de `db/` y `output/`.
- El `.docx` replica las secciones con tablas `Table Grid` y las imágenes embebidas (nubes y
  gráficos por hora).
