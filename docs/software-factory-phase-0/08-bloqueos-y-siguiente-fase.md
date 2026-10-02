# 08 · Bloqueos abiertos y candidatos a la fase 1

## Bloqueos abiertos (requieren a Max o acción externa)

| # | Bloqueo | Quién | Qué hacer |
|---|---|---|---|
| B1 | Esta rama no está publicada | Max | Revisar los commits y decidir: push + PR → CI → merge. Nada se desplegó |
| B2 | Tokens de integración por alcance sin configurar | Max (Railway, kira-bot, Eli) | Ver [02-seguridad-p0s.md](02-seguridad-p0s.md) §P0-S3, pasos 1–5. Hasta entonces, el token compartido sigue abriendo el respaldo |
| B3 | PR #138 abierto | Max | Tras desplegar esta rama, cerrar #138 como reemplazado y comprobar `/api/hora/` en la dirección de Railway |
| B4 | Tokens de consentimiento ya expuestos | Max (aprobación de una operación en producción) | Regenerar los tokens de los consentimientos **no aceptados** |
| B5 | Texto de Eli sobre el riesgo | Max / repo de Eli | Que Eli diga "riesgo sugerido, pendiente de revisión en la ficha" |
| B6 | Conflictos con ramas en curso | Quien integre | `feat/direccion-clinica` (#127, #128, #139) también edita `CLAUDE.md` y `core/respaldo.py`; `feat/email-1-cierre` está en otro worktree. Ver más abajo |
| B7 | Procesos detenidos durante la medición | — | Para liberar CPU detuve, filtrando por la línea de comando, 8 procesos que coincidían con `manage.py test` / `verificar`. La mayoría eran míos, pero **no puedo descartar** que alguno fuera un test de otra sesión de Claude que trabajaba en el mismo repo. Si alguna sesión reportó una suite interrumpida a esa hora (~18:17), esa es la causa |

### Conflictos previsibles al integrar `feat/direccion-clinica`

| Archivo | Esta rama | Rama DC | Cómo resolver |
|---|---|---|---|
| `CLAUDE.md` | Reescrito como mapa; bitácora en `docs/historial/` | Agrega ítems 46–48 a la bitácora | Conservar el mapa nuevo. Los ítems 46–48 van a `docs/historial/` (o al doc de Dirección Clínica, que ya existe en esa rama). Si hay invariantes, a `.claude/rules/continuidad.md` |
| `core/respaldo.py` | Sin cambios | `APPS` termina en `"continuidad"` en vez de `"correo"` | **Mantener ambas** (`"correo", "continuidad"`): si gana la rama, el correo sale del respaldo |
| `core/tests_matriz_permisos.py` | Nuevo | — | Añadir filas para los endpoints de Dirección Clínica y continuidad fase 2 |
| `pacientes/migrations` | `0039_sugerencia_riesgo` | Ninguna en `pacientes` | Sin conflicto |

## Deuda registrada, no tocada en la Fase 0

- **ESLint:** 74 errores y 38 avisos heredados (71/38 en `App.jsx`), congelados en `scripts/eslint-baseline.json`. No se hizo autofix.
- **Brechas de permisos** fijadas en la matriz: alertas de Faro para cualquier psicólogo; contacto de leads al psicólogo; cobros visibles a todos los roles.
- **Integraciones:** la identidad del psicólogo en Eli viene del teléfono que manda el cliente; `_psicologo_por_telefono` recorre todas las clínicas; el respaldo incluye hashes y tokens de Meta; los endpoints públicos de consentimiento no tienen throttle.
- **Eli** sigue escribiendo `resumen_clinico`, `objetivo_principal` y objetivos terapéuticos con IA.
- **CI** sobre SQLite (producción es Postgres).
- **Recomendación de uso:** lanzar Claude desde la carpeta del repo para que carguen el Stop hook y las rules.

## Candidatos a la fase 1 (por impacto y riesgo)

1. **Desplegar la Fase 0** y configurar los tokens por alcance (B1–B5). Es lo que convierte MITIGATED en FIXED.
2. **Cerrar las brechas fijadas en la matriz:** Faro, leads y cobros, con aprobación de la política por Max.
3. **RBAC declarativo:** reemplazar los helpers copiados y las comparaciones en línea por un permiso con roles. La matriz ya protege la refactorización.
4. **Tests de campos sensibles por rol** (qué campos ve cada rol dentro de un 200), generalizando lo hecho para consentimiento y bitácora.
5. **Postgres en CI.**
6. **Integrar `feat/direccion-clinica`** con su fila en la matriz y el respaldo correcto.
7. **Skills `qa-navegador` y `pr`** (las dos primeras de la auditoría), ahora que hay `verificar.ps1` sobre el que apoyarse.
8. **Extraer los primeros componentes UI base** (Modal, Confirm, Toast) empezando por la confirmación al cancelar citas, la fricción más grave de factores humanos.
9. **Mismo patrón "sugerencia + revisión"** para los textos clínicos que escribe Eli.
10. **Medir el CI real** tras el primer push y actualizar [07-metricas.md](07-metricas.md).
