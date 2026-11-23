# Diseño: previsión de matrícula en Enfermería (SIIU)

Fecha: 2026-11-23. Estado: aprobado por el autor.

Convención: lo marcado **[Decisión]** lo ha decidido el autor. Lo marcado **[Mi propuesta]** es una elección del asistente que el autor debe revisar.

## 1. Intención y motivo

- Prever el nº de matriculados totales en Grado en Enfermería, por centro (universidad + centro), para el curso siguiente (horizonte: 1 curso). **[Decisión]**
- Es un proyecto personal. Debe poder enseñarse en el futuro y ampliarse con datos del centro del autor (EUEF San Juan de Dios). **[Decisión]**
- Prioridad: la calidad del modelo y de su evaluación. El aprendizaje de MLOps es el segundo objetivo, porque el autor tiene poca experiencia y quiere adquirirla. **[Decisión]**

## 2. Objetivos, no objetivos y antiobjetivos

**Objetivos**
- Un modelo evaluado con validación de origen móvil, comparado siempre con el modelo ingenuo.
- Una previsión para el curso 2026-27 por centro, con su incertidumbre.
- Un repositorio reproducible y presentable: datos limpios con reglas documentadas, tests, experimentos registrados y una app de demostración.
- Documentación honesta de los límites y errores reales.

**No objetivos (por ahora)**
- Prever nuevo ingreso (posible ampliación futura, según `CLAUDE.md`).
- Horizontes de más de un curso.
- Infraestructura en la nube, orquestadores pesados, despliegue en producción.
- Usar `Egresados.xlsx` en la primera versión **[Mi propuesta]**. El fichero existe en `data/raw/` pero `CLAUDE.md` no lo menciona.

**Antiobjetivos (fracaso aunque "funcione")**
- Un modelo complejo que no supera al ingenuo y se presenta como éxito.
- Fuga de información del futuro en la validación.
- Infraestructura MLOps mayor que el problema que gestiona.
- Reglas de limpieza no documentadas o que alteren `data/raw/`.

## 3. Restricciones

- Windows, conda (entorno `matricula-enf`), Python 3.11, pytest, git con una rama por tarea.
- `data/raw/Matriculados.xlsx` no se modifica nunca.
- Hojas relevantes: "Matriculados Grado" y "Matriculados Global por centro". Cabecera en la fila 4, con pares de columnas Total / % Mujeres por curso.
- 2025-26 es un dato provisional y puede revisarse. NaN significa titulación sin dato ese curso (no hay ceros).
- Unos 11 cursos por serie. Es el límite principal: la señal es corta y la evaluación tiene pocos orígenes.
- Documentación y comentarios en español, nombres de variables y funciones en inglés.

## 4. Enfoque elegido: modelo primero, MLOps por capas **[Decisión]**

Alternativas descartadas:
- **MLOps desde el principio:** la infraestructura pesaría más que el modelo y lo dejaría en segundo plano.
- **Notebooks y MLOps al final:** obliga a reescribir y enseña MLOps de forma superficial.

Cada herramienta MLOps entra cuando resuelve un problema que ya ha aparecido.

## 5. Fases

Cada fase es una rama de git y se entrega fichero a fichero. En los cambios grandes se explica el razonamiento antes y se espera conformidad.

**Fase 1: carga y limpieza**
- Cargar las dos hojas desde la fila 4 y pasar de formato ancho a largo (centro, curso, matriculados, % mujeres).
- Reglas, cada una documentada y con test:
  - Quedarse con "Graduado o Graduada en Enfermería".
  - Excluir Diplomado en Enfermería y programas conjuntos (PCEO / dobles grados).
  - Unificar series partidas por cambio de código (p. ej. Granada, Almería) por universidad + centro.
  - Tratar el caso especial San Juan de Dios: Univ. Sevilla → Univ. Pontificia Comillas.
- Marcar 2025-26 como provisional y NaN como "sin dato".
- Salida en `data/processed/`. Registro de cada regla con el nº de filas afectadas.

**Fase 2: exploración y calidad de series**
- Longitud y huecos por centro, saltos bruscos, centros que aparecen o desaparecen.
- Decidir con datos qué centros entran en el modelo (p. ej. un mínimo de cursos).
- Comprobar que la suma de centros cuadra con el total nacional.

**Fase 3: líneas base**
- Ingenuo (último valor), ingenuo con deriva, media móvil.
- Marco de evaluación de origen móvil: cada origen entrena con los cursos hasta t y predice t+1. Métricas: MAE, y MAPE/WAPE para comparar entre centros de distinto tamaño.
- El resto de modelos se comparan con estas líneas base.

**Fase 4: modelos**
- Candidatos **[Mi propuesta]**, de más simple a más complejo, parando cuando no aporte:
  1. Suavizado exponencial / tendencia amortiguada por centro.
  2. Regresión con efectos por centro (panel).
  3. Un modelo global tipo gradient boosting con retardos y variables del panel.
- Evaluar por centro y agregado, incluyendo el centro del autor. Informar de dónde falla cada modelo.
- Intervalos de predicción, si el método lo permite con series tan cortas.

**Fase 5: MLOps por capas** (cada capa en su rama, cuando haga falta)
1. MLflow para registrar experimentos, en cuanto haya más de un modelo que comparar.
2. DVC o un pipeline reproducible (p. ej. Makefile) para datos y entrenamiento.
3. CI con GitHub Actions: tests en cada push.
4. App de demostración con Streamlit: previsión por centro, ingenuo frente a modelo, aviso del dato provisional.

**Fase 6: previsión 2026-27 y documentación**
- Generar la previsión del curso siguiente. Redactar el README con resultados, límites y errores reales.

## 6. Criterios de éxito

- Las reglas de limpieza son reproducibles, testeadas y están documentadas.
- La evaluación es de origen móvil, sin fuga, y siempre incluye el ingenuo.
- Se informa de forma clara de si el modelo supera al ingenuo, en qué centros y por cuánto. Si no lo supera, eso es un resultado válido y se documenta.
- Un tercero puede clonar el repositorio y reproducir los resultados con unos pocos comandos.

## 7. Riesgos conocidos

- Series muy cortas: poca potencia estadística y pocos orígenes de validación.
- Dato provisional 2025-26: puede cambiar al revisarse y afecta al último origen de evaluación. Se evalúa con y sin él.
- Reglas de unión de centros: un error silencioso contamina series enteras. Mitigación: tests y control de totales.
- Cambios de adscripción o de oferta no modelables (apertura/cierre de centros, límites de plazas).

## 8. Preguntas resueltas

1. `Egresados.xlsx` queda fuera en la primera versión. **[Decisión]**
2. No hay criterio previo de mínimo de cursos por centro: se decide en la fase 2 con los datos. **[Decisión]**
3. Este documento se guarda en `main`. **[Decisión]**

## 8b. Flujo de trabajo (decidido por el autor)

- Cada fase va en una rama de git distinta, para llevar orden y aprender git. **[Decisión]**
- En `docs/` hay un documento por fase que explica lo realizado en ella. **[Decisión]**

## 9. Pendiente para quien construya

- Elección final de librerías (pandas, statsmodels, scikit-learn, MLflow, DVC, Streamlit) y estructura de `src/`.
- Detalle de las métricas por centro y de la agregación.
- Estructura de tests y de la configuración del entorno.
