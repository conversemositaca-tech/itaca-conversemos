---
paths:
  - "leads/identidad.py"
  - "pacientes/duplicados.py"
  - "pacientes/fusion.py"
  - "pacientes/api_duplicados.py"
  - "frontend/src/Duplicados.jsx"
---
# Identidad de personas, duplicados y fusión

- **Identidad ≠ teléfono.** `leads/identidad.py::numeros_de` devuelve el número propio y el del tutor como *vías de contacto*; el del tutor **nunca identifica por sí solo** (hace falta nombre + sede compatible + un único candidato). Teléfono válido = ≥ `MIN_DIGITOS_TELEFONO` (9).
- **Prevención**: crear paciente busca coincidencias y responde **409** con `posibles_duplicados` (contacto enmascarado). No bloquea: `confirmar_nuevo` crea igual (los homónimos existen).
- **Detector** `pacientes/duplicados.py`: solo lee, nunca fusiona. ALTA = mismo documento, o nombre + teléfono válido + sede compatible sin contradicciones. Descarta documentos válidos distintos, nacimientos distintos, familiares con el mismo celular y expedientes de pareja.
- **Motor** `pacientes/fusion.py`: dry-run 100 % read-only y fusión atómica. Las relaciones salen de `Paciente._meta.get_fields()`, **nunca de una lista a mano**.
- **Fail-safe**: si un modelo tiene unicidad sobre `paciente` y no tiene handler propio, la fusión se detiene antes de tocar nada. Si agregas un modelo con FK a `Paciente` y restricción única, escribe su handler (ver `_handlers()`).
- **Orden no negociable**: resolver choques → mover todo → completar la ficha maestra → `gestion_continuidad.reconciliar()` (el `update()` no dispara señales) → verificar que nada apunta al secundario → `RegistroFusionPaciente` → borrar. Todo en `transaction.atomic()`. El texto clínico de ambas fichas se une.
- **Bloquean**: clínicas distintas, documentos válidos distintos, nacimientos distintos; sede distinta exige `aceptar_sede_distinta`.
- `especialidad_habitual`: manda la ficha con actividad más reciente; si ninguna tiene citas y difieren, no adivinar. `creado_en` no sirve de desempate.
- La vista previa de continuidad llama a `core.continuidad.evaluar_paciente` (la misma regla), no la reimplementa.
- **Permisos** (`core/permisos.py`): `ROLES_REVISAN_DUPLICADOS` y `ROLES_FUSIONAN_PACIENTES` = admin + asistente. El frontend lee `puede_consolidar` de `/api/auth/me/`, no deduce el rol.
- Cada fusión es individual, con confirmación explícita: **no existe ni existirá "fusionar todos"** ni limpieza masiva.
- La sede en la lista de duplicados es un **filtro** (`?sede=`), no un permiso; un valor inválido no acota.

Más contexto: ítems 38, 42 y 44 del archivo histórico (el 38 dice "solo admin fusiona": OBSOLETO).
