# Decisiones por fase

Registro de las decisiones tomadas en cada fase, con su motivo. Es documentación de trabajo del
proyecto: qué se decidió, quién lo decidió y qué cuesta si resulta ser un error. Los resultados y
los límites de cada fase están en su documento (`docs/fase-N-*.md`).

Convención: **[Autor]** lo decidió el autor. **[Propuesta]** lo propuso el asistente y el autor lo
aprobó. **[Criterio]** lo resolvió el asistente durante la implementación sin que fuera una
pregunta abierta; se anota para poder revisarlo.

## Decisiones generales

| Decisión | Motivo | Quién |
|---|---|---|
| Prever matriculados totales en Grado en Enfermería, por centro, para el curso siguiente (horizonte de 1 curso) | Es lo que se quiere prever; el nuevo ingreso y otros horizontes quedan como ampliación futura | Autor |
| Unidad de análisis: panel por centro (universidad + código de centro), no solo total nacional | Permite prever el centro del autor y comparar centros | Autor |
| Evaluación de origen móvil, siempre comparada con un modelo ingenuo | Con series de unos 11 cursos, un modelo complejo que no supera al ingenuo no vale | Autor |
| Modelo primero, MLOps por capas: cada herramienta entra cuando resuelve un problema ya aparecido | La infraestructura no debe pesar más que el modelo | Autor |
| `Egresados.xlsx` queda fuera de la primera versión | `CLAUDE.md` no lo menciona y no hace falta para el objetivo | Autor |
| Una rama de git por fase, integrada por Pull Request; un documento, un notebook y un pipeline por fase | Llevar orden y aprender git; que notebook y pipeline no puedan divergir | Autor |
| Los diseños y planes de trabajo (`docs/superpowers/`) no se versionan; las decisiones se recogen aquí | Son material de trabajo, no documentación del proyecto | Autor |
| Entorno conda `prev-mat`, Python 3.11 | Entorno del proyecto | Autor |

## Fase 1: carga y limpieza

Documento: `docs/fase-1-limpieza.md`.

| Decisión | Motivo | Quién |
|---|---|---|
| Quedarse con *Graduado o Graduada en Enfermería* admitiendo el sufijo "por la Universidad de X" (patrón `^Graduado o Graduada en Enfermería( por .*)?$`) | El texto literal de `CLAUDE.md` solo da 8 filas; el patrón da 158 (70 universidades) | Criterio, confirmado por el autor |
| Excluir Diplomado en Enfermería, PCEO y dobles grados, másteres y doctorados | Fuera de la variable objetivo | Autor |
| Clave de unificación: (universidad, código de centro), no el nombre | El nombre cambia con el mismo código (p. ej. Melilla); por nombre salen 145 centros y por código, 144 | Autor |
| Sumar los códigos de titulación de un centro por curso, con suma que da NaN si todos son NaN; % de mujeres ponderado por matrícula | Los planes antiguo y nuevo conviven con estudiantes distintos del mismo centro | Autor |
| San Juan de Dios (Sevilla → Pontificia Comillas): dos series separadas, no se suman | Los datos muestran una transferencia progresiva, no un corte limpio. Coste: el modelo puede leer como tendencia un efecto administrativo | Autor |
| NaN es "sin dato" y no se imputa; no hay ceros | Así viene en el SIIU | Autor |
| 2025-26 se marca provisional como el último curso del fichero, no como un año fijo | Sigue siendo correcto al añadir cursos | Criterio (corrección posterior) |
| Validar los totales por universidad y curso contra la hoja "Matriculados Grado" | Detecta filas perdidas o duplicadas al agrupar. No detecta errores del propio SIIU | Propuesta |
| `data/processed/` no se versiona; se regenera con `python -m prevision.pipeline` | Es derivado y reproducible | Autor |

## Fase 2: exploración y calidad de series

Documento: `docs/fase-2-exploracion.md`.

| Decisión | Motivo | Quién |
|---|---|---|
| Enlazar cambios de código de centro con un paso nuevo sobre el panel y un CSV versionado (`data/reference/center_links.csv`), no dentro de la fase 1 ni en `config.py` | La fase 1 queda intacta y cada decisión se revisa en un diff | Autor |
| Los enlaces los confirma siempre una persona; la detección solo propone | Un enlace falso une dos series distintas sin que nada lo delate | Autor |
| `series_id = universidad + código más reciente de la cadena` | Etiqueta estable y que admite cadenas A→B→C | Propuesta |
| Solo `decision = sí` se aplica; `no` y `dudoso` se guardan | Para no volver a preguntar | Propuesta |
| 22 candidatos revisados: 14 `sí`, 1 `dudoso` (Internacional de la Empresa, el tamaño se triplica) y 7 `no` | Decisión del autor sobre cada par | Autor |
| País Vasco "sí" se aplica solo a Donostia → Guipúzcoa y Leioa → Facultad; los otros seis pares, `no` | Los ocho `sí` darían una bifurcación y un ciclo, que se rechazan | Criterio |
| Enlace manual de Antonio de Nebrija `28051891` → `28055225` | El código antiguo se extingue con 3 alumnos y la regla de detección no lo ve | Autor |
| Se rechazan con error los enlaces a centros inexistentes, los ciclos, las bifurcaciones y las `decision` no válidas | Un error silencioso contamina series enteras | Criterio |
| La suma por curso debe dar la misma matrícula total antes y después de enlazar; se comprueba en cada ejecución | Enlazar no puede crear ni perder matrícula | Propuesta |
| Elegible = llega al último curso y tiene al menos `MIN_SEASONS = 4` cursos con dato | Entre las series activas hay un corte natural entre 3 y 4 cursos. Es un mínimo de historia, no garantía de poder evaluar | Propuesta, confirmado con los datos |
| Saltos: se marcan con `JUMP_RATIO = 1,5` y no se corrigen | Son crecimiento real o cambios administrativos; corregirlos sería inventar datos | Propuesta, confirmado con los datos |
| Contar solo los cursos con matrícula informada para primer curso, último curso y longitud | El panel es rectangular: un curso sin dato es una fila con NaN | Criterio (hallazgo al ejecutar con datos reales) |
| El pipeline no falla si falta el CSV de enlaces: avisa y no enlaza | Permite generar los candidatos la primera vez | Propuesta |
| `README.md` pasa de UTF-16 a UTF-8 | Git lo trataba como binario y GitHub lo muestra mal | Criterio |

## Fase 3: líneas base y evaluación de origen móvil

Documento: `docs/fase-3-lineas-base.md`.

| Decisión | Motivo | Quién |
|---|---|---|
| Tres líneas base: ingenuo (último valor), ingenuo con deriva y media móvil de ventana 3 | Son el suelo que debe superar cualquier modelo | Autor |
| Modelos como funciones `historia → previsión` registradas en un diccionario, no como clases | Las líneas base no tienen estado; si la fase 4 necesita clases, se introducen entonces | Propuesta |
| Mínimo de 4 cursos de entrenamiento por origen, igual que `MIN_SEASONS` | Coherencia con la elegibilidad de la fase 2 | Propuesta |
| Métricas MAE, WAPE y MAPE, por curso objetivo y en total | WAPE y MAPE comparan centros de distinto tamaño de formas distintas | Propuesta |
| 2025-26 entra como objetivo y se reportan los resultados con y sin él | Es provisional y puede cambiar | Propuesta |
| Test de no-fuga: alterar datos posteriores al origen no cambia la previsión de ese origen | Evita la fuga de información del futuro | Propuesta |
| Sin MLflow todavía | Con tres funciones sin parámetros que ajustar no resuelve un problema real | Propuesta |

Decisiones tomadas durante la implementación:

| Decisión | Motivo | Quién |
|---|---|---|
| `drift` usa la pendiente media de toda la historia, calculada por año (no por posición) | Un curso sin dato en medio no distorsiona la pendiente. Sin ventana: no se ha probado con ventana | Criterio |
| Una serie con exactamente 4 cursos no da ningún par | Hace falta un curso más como objetivo; afecta a 2 de las 112 series elegibles | Criterio |
| Añadir `bias` (error medio con signo) a las métricas | Sin él no se ve que las tres líneas base infravaloran en un periodo de crecimiento | Criterio |
| Añadir `compare_to_naive` (pares y series donde un modelo mejora al ingenuo) | Contesta "en qué centros y por cuánto" con cifras reproducibles desde el notebook, sin lógica propia en él | Criterio |
| Añadir `add_size_tier` (terciles de `size_last`) | El notebook necesita agrupar por tamaño sin lógica propia | Criterio |
| Informar siempre del tamaño de la muestra y avisar de que las diferencias pequeñas no están contrastadas | Los 761 pares salen de 110 series y no son independientes | Criterio |

Resultado que condiciona la fase 4: la deriva mejora un 9 % el WAPE del ingenuo (4,3 % frente a 4,7 %, cifras recalculadas en la tarea previa
de la fase 4; antes 4,4 % frente a 4,8 %), pero
solo la sostienen los centros grandes; en los medianos y pequeños gana el ingenuo. La media móvil es
claramente peor (+64 %). Detalle y límites en `docs/fase-3-lineas-base.md`.

## Fase 4: modelos globales

Documento: `docs/fase-4-modelos.md`.

### Tarea previa: enlaces pendientes

Se aplican como primer paso de la fase 4, en su misma rama, y no en una rama aparte (decisión del autor).

| Decisión | Motivo | Quién |
|---|---|---|
| Enlazar Murcia `30013116` → `30011821` (`sí`) | La Escuela termina en 2023-24 con 225 y la Facultad sube +193 al curso siguiente; enlazadas, el salto baja de 1,26 a 1,09. El listón pasa de WAPE ingenuo 4,76 % a 4,71 % y de deriva 4,37 % a 4,30 %, con los mismos 761 pares. Coste: si fueran centros distintos, se unen dos series que no lo son | Autor |
| València La Fe `46014601` → Facultat `46014455`: `dudoso`, no se aplica | La suma de ambas queda casi plana (1385, 1387, 1430, 1438) pero no es concluyente. Coste: La Fe sigue como serie propia y la Facultat conserva una subida que puede ser administrativa | Autor |
| Autónoma de Barcelona, Europea de Madrid `46035631`, Málaga y València `12003274` no se enlazan | Extinciones sin sucesor visible | Autor |
| Los tramos de tamaño siguen calculándose con todas las series de la tabla de calidad | No se cambia el método a mitad de fase; se anota que el corte pequeño/mediano pasó de 299 a 301 alumnos al salir una serie y una serie cambió de tramo | Criterio |

### Modelos y evaluación

| Decisión | Motivo | Quién |
|---|---|---|
| Dos modelos globales: Ridge (control) y gradient boosting, con las mismas variables | Si el gradient boosting no le gana a Ridge, la no linealidad no aporta. Descartados de esta fase: modelos por serie, preentrenados y datos externos | Autor |
| La región (CCAA del Excel) no entra como variable por defecto; sí como sensibilidad y como error descriptivo por comunidad | Diagnóstico previo: la media de la comunidad tiene correlación +0,03 con el crecimiento siguiente y la nacional −0,09; el propio, +0,66. Coste: si la región importara de forma no lineal, no se ha visto | Autor (propuesta aprobada) |
| Los hiperparámetros se confirman tal cual y no se ajustan con los pares de evaluación | Evita presentar como honesta una previsión ajustada con los datos de evaluación. Coste: pueden no ser los mejores | Autor |
| La versión principal es `base` (con `system_growth`) aunque `*_no_system` salga mejor | El aporte de `system_growth` se vio después de ver resultados; decidir por esos pares sería ajustar con los datos de evaluación. Coste: se mide una versión probablemente algo peor que la que se usaría | Autor |
| Criterio de éxito: gana el modelo con WAPE total menor que la deriva y no peor que el ingenuo en tramos mediano y pequeño | Declarado antes de ver resultados. Se exige también ganar en los tramos donde la deriva pierde | Propuesta |
| Objetivo: crecimiento logarítmico `ln(y[t+1]/y[t])` | Hace comparables los centros de distinto tamaño y el modelo parte del ingenuo (crecimiento 0) | Propuesta |
| Informar también de los cursos objetivo desde 2021 (`RECENT_TARGET_FROM`) | Los primeros orígenes entrenan con un centenar de ejemplos. Descriptivo, no sustituye al total | Propuesta |
| scikit-learn y no LightGBM | Una dependencia menos y el algoritmo es el mismo en lo que importa aquí | Criterio |
| Sin identificador de universidad ni de centro | Alta cardinalidad con pocos ejemplos: dejaría al modelo memorizar series. Coste: no puede aprender particularidades de un centro | Criterio |
| `RIDGE_ALPHA = 10,0`; `GBM_PARAMS`: `max_iter` 100, `learning_rate` 0,05, `max_depth` 3, `min_samples_leaf` 20, `l2_regularization` 1,0, `random_state` 0 | Conservadores, fijados antes de ver resultados | Criterio, confirmado por el autor |
| `MIN_FEATURE_HISTORY = 3` y `MIN_TRAIN_EXAMPLES = 30` | Hacen falta 3 cursos para `g1` y `g2`; con menos de 30 ejemplos el ajuste no es fiable y se prefiere un error | Criterio |
| Error explícito (`ValueError`) si un origen tiene pocos ejemplos o falta una fila de variables, y nunca rellenar con otro modelo | Un ajuste silencioso con casi nada o un par rellenado con otro modelo falsearían la comparación | Criterio |
| La tabla se recorta al último curso visible antes de calcular variables (`up_to`, `origin`) | La garantía de no-fuga sale de la construcción y no de recordar filtrar. Efecto: una matrícula 0 en un curso futuro tampoco rompe el origen actual | Criterio |
| `system_growth` y `region_growth` excluyen la propia serie; la de la región exige al menos 2 más | La propia serie ya está en `g1`; con una sola serie más, la media sería su valor | Criterio |
| La región viene del Excel y no del código de centro | El prefijo del código falla en varias comunidades (28, 39, 07, 19, 46); el Excel la trae en los 144 centros. Corrige lo que se dijo al autor antes | Criterio (corrección) |
| `unify_center_series` lanza error si un centro tiene más de una región | En los datos actuales no ocurre; evita asignar una región al azar si cambia el SIIU | Criterio |
| `model_forecasts.csv` solo con los modelos globales; `model_metrics.csv` con líneas base y modelos juntos | Para que `*_vs_naive` compare con el ingenuo sin duplicar las previsiones de las líneas base | Criterio |

Resultado de la fase: ningún modelo supera el criterio declarado. `gbm` (WAPE 4,04 %) y `ridge` (4,22 %) están por
debajo de la deriva (4,30 %) en el total, pero ambos son peores que el ingenuo en los centros pequeños. Detalle y
límites en `docs/fase-4-modelos.md`.
