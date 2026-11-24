# Fase 2: exploración y calidad de series. Diseño

Estado: pendiente de aprobación. Rama: `fase-2-exploracion`.

## Por qué

El panel de la fase 1 tiene 144 centros × 11 cursos. Antes de modelar hay que saber qué series
son fiables. La exploración de solo lectura mostró:

- No hay huecos interiores: cada centro es una serie continua.
- 124 centros están activos en 2025-26; 109 tienen 4 o más cursos.
- 32 centros empiezan tarde y 20 terminan antes de 2025.
- Unos 16 pares (centro que termina, centro que empieza, misma universidad) parecen un cambio de
  código de centro. Si no se enlazan, un cambio administrativo se vería como "muere una serie y
  nace otra", y ninguna de las dos tendría historia suficiente para prever.
- Los saltos grandes parecen crecimiento real (centros que abren grupos), no errores.
- Tamaño en 2025: media 475, mediana 404, mínimo 3, máximo 1913.

## Objetivos

1. Detectar candidatos a sucesión de código de centro con una regla explícita y revisable.
2. Aplicar solo los enlaces que el usuario confirme, guardados en un fichero versionado.
3. Producir un panel de series (`series_id`) con las series enlazadas ya unidas.
4. Medir la calidad de cada serie y marcar cuáles son elegibles para prever.
5. Dejar constancia en notebook, documento y pipeline, como en la fase 1.

## No objetivos

- No se corrigen ni se suavizan saltos: se marcan y se documentan.
- No se imputan cursos ni se rellenan valores.
- No se entrena ningún modelo ni se miden errores (fase 3 y 4).
- No se enlazan automáticamente casos ambiguos (País Vasco, Internacional de la Empresa).
- San Juan de Dios sigue como dos series (decisión de la fase 1), salvo que el usuario la revoque
  al revisar los candidatos.

Antiobjetivo: que un enlace erróneo pase sin que se vea. Por eso toda decisión es un registro
explícito en un CSV, con nota, y revisable en un diff de git.

## Enfoques considerados

- A. Fusionarlo en `unify_center_series` de la fase 1. Corto, pero mezcla un juicio humano con una
  regla mecánica y obliga a reabrir una fase ya fusionada.
- B. Diccionario de enlaces en `config.py`. Cada decisión es una edición de código; con unos 15
  enlaces es incómodo de revisar.
- C. Paso nuevo sobre el panel, con CSV versionado de enlaces. **Elegido por el usuario.** La fase 1
  queda intacta, las decisiones viven en datos y no en código.

## Diseño

### Flujo

```
enfermeria_panel.csv (fase 1)
   │
   ├─ detect_candidates ──► data/processed/link_candidates.csv   (generado; lo revisa el usuario)
   │                                   │  el usuario marca sí / no / dudoso
   │                                   ▼
   │                        data/reference/center_links.csv       (versionado)
   │                                   │
   └─ apply_links ◄───────────────────┘
          │
          ├─► data/processed/enfermeria_series.csv   (panel con series_id)
          └─► series_quality  ─► data/processed/series_quality.csv
```

### Detección de candidatos

Para cada centro A que termina antes del último curso (último año `y` < último del fichero) y cada
centro B de la misma universidad cuyo primer curso está en `{y, y+1}` y que es distinto de A,
se genera una fila candidata con: universidad, códigos y nombres de A y B, último curso de A,
primer curso de B, matrícula de A en su último curso, matrícula de B en su primero, cociente
entre ambas y `n_options` (cuántos B posibles tiene A y cuántos A posibles tiene B).
No hay umbral automático sobre el cociente: se muestra para que decida el usuario. Los casos con
`n_options > 1` en cualquiera de los dos lados se marcan `ambiguo`.

### Fichero de enlaces confirmados

`data/reference/center_links.csv`, columnas: `university, from_center_code, to_center_code,
decision, note`. `decision` ∈ {`sí`, `no`, `dudoso`}. Solo `sí` se aplica. Se versiona en git.
Los `no` y `dudoso` también se guardan para que la decisión no se vuelva a preguntar.

### Aplicación de enlaces

`apply_links(panel, links)` asigna `series_id = "{university}|{center_code_final}"`, donde
`center_code_final` es el código más reciente de la cadena (se admiten cadenas A→B→C, resueltas
con componentes conexos). Centros sin enlace tienen su propio `series_id`. Si dos centros de una
misma serie coinciden en un curso, se suman las matrículas (`min_count=1`), `pct_women` se pondera
por matrícula, `is_provisional` es verdadero si alguno lo es, y el nombre es el del centro más
reciente. Invariante comprobada en tests y en el pipeline: la suma de matrícula por curso antes y
después del enlace es idéntica. Se rechazan enlaces cuyos centros no existen en el panel o
pertenecen a universidades distintas (ValueError).

### Calidad de series

Una fila por `series_id`: `first_year, last_year, n_seasons, active_last` (tiene el último curso),
`size_last`, `max_jump_ratio` (mayor cociente interanual, en la dirección que más se aleja de 1),
`n_jumps` (saltos por encima del umbral), `is_linked`, `eligible`.
Umbrales de partida, parámetros en `config.py` y a decidir con los datos en el notebook:
`MIN_SEASONS` (propuesta inicial 4, por los 109 centros de 4+), `JUMP_RATIO` (se fija mirando la
distribución de saltos). `eligible = active_last and n_seasons >= MIN_SEASONS`. Los saltos solo
se marcan, no se alteran.

### Entregables

- `src/prevision/linking.py`: `detect_candidates`, `load_links`, `apply_links`.
- `src/prevision/quality.py`: `series_quality`.
- `src/prevision/pipeline.py`: extendido con el paso de series (`python -m prevision.pipeline` sigue
  funcionando; si no existe `center_links.csv`, se genera solo la tabla de candidatos y se avisa).
- `data/reference/center_links.csv`, con las decisiones del usuario.
- `notebooks/02_exploracion.ipynb`: hallazgos, candidatos, revisión, series y calidad; llama a las
  funciones del paquete sin lógica propia y termina verificando que coincide con el pipeline.
- `docs/fase-2-exploracion.md`, y fila de fase 2 actualizada en `README.md`.
- Tests de cada función, incluido un test que ejecuta el notebook.

### Pruebas (casos que deben cubrirse)

- Detección: sucesión simple; B que empieza el mismo año que A termina y el siguiente; centro de
  otra universidad no es candidato; ambigüedad marcada; ningún candidato si nadie termina antes.
- Aplicación: enlace simple, cadena de tres, solape en un curso (suma y % mujeres ponderado),
  invariante de totales, `decision` distinta de `sí` ignorada, enlace a centro inexistente o de otra
  universidad da error, sin enlaces el resultado equivale al panel con `series_id` propio.
- Calidad: `eligible` en el límite de `MIN_SEASONS`; serie que acaba antes del último curso no es
  elegible; salto marcado sin modificar el dato.

## Decisiones tomadas por mí (corrígelas si no te valen)

- `series_id` usa el código más reciente de la cadena.
- Los umbrales `MIN_SEASONS` y `JUMP_RATIO` son parámetros y se fijan con los datos, no antes.
- La tabla de candidatos va a `data/processed/` (generada) y solo las decisiones a `data/reference/`.
- El pipeline no falla si faltan los enlaces: genera candidatos y avisa.

## Riesgos y límites que se documentarán

- Enlazar por cercanía de fechas y tamaño es un juicio: un enlace falso une dos series distintas.
- El curso 2025-26 es provisional; una serie que "termina" ahí puede estar incompleta.
- Series cortas (centros nuevos) no se podrán prever con rigor: quedan fuera del conjunto elegible
  y se documenta cuántos y cuáles.
