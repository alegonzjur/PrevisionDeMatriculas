
# Previsión de matrícula en Enfermería (SIIU)

## Objetivo
Proyecto de MLOps de tamaño reducido: prever el nº de estudiantes matriculados
en Grado en Enfermería, por centro, para el curso siguiente (horizonte: 1 curso).

## Decisiones tomadas
- Unidad de análisis: panel por centro (universidad + centro), no solo total nacional.
- Variable objetivo: matriculados totales (no nuevo ingreso; posible ampliación futura).
- Evaluación: validación de origen móvil, siempre comparada con un modelo ingenuo.
- Datos: SIIU (Ministerio de Ciencia, Innovación y Universidades), cursos 2015-16 a 2025-26.

## Datos
- Fichero original: data/raw/Matriculados.xlsx. NO modificar nunca.
- Hojas relevantes: "Matriculados Grado" y "Matriculados Global por centro".
- Cabecera real en la fila 4; después van pares de columnas Total / % Mujeres por curso.
- 2025-26 es un dato PROVISIONAL (avance) y puede revisarse.
- NaN = titulación sin dato ese curso (no hay ceros).

## Reglas de limpieza (documentar cada una)
- Quedarse solo con "Graduado o Graduada en Enfermería".
- Excluir Diplomado en Enfermería y programas conjuntos (PCEO / dobles grados).
- Algunas series se parten por cambios de código (p. ej. Granada, Almería):
  unificar por universidad + centro y dejar constancia de la regla aplicada.
- Cambio de adscripción conocido: Centro de Enfermería San Juan de Dios (Univ. Sevilla)
  pasa a EUEF San Juan de Dios (Univ. Pontificia Comillas). Tratar como caso especial.

## Entorno
- Windows, conda (entorno: matricula-enf), Python 3.11.
- Tests con pytest. Control de versiones con git (una rama por tarea).

## Cómo quiero trabajar
- Explica el razonamiento ANTES de implementar y espera mi conformidad en cambios grandes.
- Diagnostica antes de arreglar: no apliques parches sin entender la causa.
- Documenta los límites y errores reales; no embellezcas los resultados.
- Documentación y comentarios en español; nombres de variables y funciones en inglés.
- Entrega ficheros completos y listos para usar, de uno en uno.