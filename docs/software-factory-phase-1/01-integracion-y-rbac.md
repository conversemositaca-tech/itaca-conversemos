# 01 · Integración y RBAC

## Estado real encontrado al iniciar la Fase 1 (1 oct 2026, ~20:30)

| Elemento | Estado |
|---|---|
| Fase 0 | 15 commits locales en `chore/software-factory-phase-0` sobre `ae759b8`, sin push |
| `origin/main` | Avanzó a `9ed776c`: #141 (cierre de Email 1.0) y **#138** (Railway con comodín `*.up.railway.app`) mergeados |
| Dirección Clínica / Continuidad 1.5 y fase 2 | En `origin/feat/direccion-clinica` (#127 abierto, #128 y #139 mergeados en esa rama), 16 commits fuera de `main` |
| Integración de DC con `main` | **Otra sesión de Claude la está haciendo**: worktree `C:\projects\itaca-continuidad-2`, rama `integrar-main`, merge a medias con conflictos en `CLAUDE.md`, `settings.py`, `urls.py` |
| Email | Cerrado en `main` (#141) |
| CI | 4 jobs en la rama (backend, seguridad, Postgres, frontend); `main` sigue con 1 job |
| RBAC | 3 mecanismos (`core/permisos.py`, helpers copiados, comparaciones en línea) |

## Integración

- **Fase 0 rebasada sobre `9ed776c`.** Único conflicto: `config/settings.py` (Railway). Se resolvió a favor del dominio exacto (`RAILWAY_DOMINIO_SERVICIO`) y se adaptó `core/tests_hosts.py` (que llegó con #138 y exigía el comodín) para que exija lo contrario: `atacante.up.railway.app` rechazado.
- Como #138 ya está en `main`, el commit de Railway de esta rama **endurece** lo que hoy corre en producción.
- **Dirección Clínica: no se integró aquí, a propósito.** Hay una integración en curso en otro worktree; hacerla en paralelo duplicaría el trabajo y generaría conflictos entre dos sesiones. Cuando esa rama llegue a `main`, esta rama deberá:
  - conservar `"correo", "continuidad"` en `core/respaldo.APPS`; si no, lo atrapa el test nuevo `RespaldoCubreTodaAppTests`;
  - mover los ítems 46–48 del `CLAUDE.md` viejo a `docs/historial/`;
  - sumar sus endpoints a la matriz.
- Otras ramas abiertas no tocadas: #118 (sede normalizada en `instancia_para`), #120 (favicon), #102 (docs).

## RBAC: arquitectura

```text
autenticación  → DRF (sesión) ............................ sin cambios
rol            → core.politicas.rol_de / es_admin / es_psicologo / es_comercial
propiedad      → core.politicas.ficha_de / es_paciente_propio
alcance        → core.politicas.acotar_clinico(qs, user, campo)
campos         → core.politicas.ve_contacto / ve_token_consentimiento / ve_finanzas / ve_cobros_de_la_clinica
acciones       → core.politicas.puede_editar_historia / puede_resolver_sugerencia_ia / puede_registrar_pago / puede_anular_pago
declarativo    → core.politicas.SoloRoles.de("admin", "asistente")
listas de roles y clases DRF → core.permisos (sin cambios)
contrato       → core/tests_matriz_permisos.py (210 celdas) + core/tests_campos_por_rol.py
```

Son funciones cortas con nombre de dominio, no un helper gigante. Cada una responde una pregunta concreta sobre un usuario y un recurso.

## Qué se migró

| Antes | Después |
|---|---|
| 6 `_es_admin` idénticos (`core/buzon.py`, `core/recursos.py`, `core/whatsapp_cloud.py`, `espacios/api.py`, `finanzas/api.py`, `mensajes/monitor_evolution.py`) | `core.politicas.es_admin` |
| 5 `_solo_admin` con su mensaje | `exigir(es_admin(user), mensaje)`; mismo mensaje |
| `_solo_admin` de plantillas (admin + coordinación) | `exigir(puede_contactar_pacientes(user), …)` |
| 5 bloques "comercial nada / psicólogo su ficha" en `pacientes/api.py` | `acotar_clinico(qs, user, campo=…)` |
| 3 `_solo_clinico` | `exigir(puede_editar_historia(user), …)` |
| Alcance de adjuntos, consentimientos, sugerencias de IA, mensajes y cobros | `acotar_clinico` |
| `_ficha_de` hacía 1 consulta por llamada | `ficha_de` la cachea en el usuario |

**Comparaciones de rol en línea** (patrón `getattr(user, "rol") ==/in` y `.rol ==/in`, sin tests ni migraciones): 45 en `ae759b8` → **32**. De esas, 8 son las propias definiciones de `core/permisos.py`; fuera de ese archivo pasaron de 37 a 24. Las que quedan expresan reglas propias de cada vista (gerencia, correo, nota de voz) y se migran por grupos en fases siguientes, con la matriz como red.

## Brechas cerradas en esta fase

| Brecha | Arreglo |
|---|---|
| FK escribibles sin tenant: cita (`pacienteId`, `medicoId`), cobro, paquete, lead (`medico`), consentimiento (`paciente`) | Mixin `RelacionesDelTenant` (`core/serializadores.py`) |
| Cobros visibles y editables por cualquier rol | Alcance por rol; escribir solo caja; corregir monto solo gerencia |
| Vender paquete (crea un cobro pagado) por cualquier rol | Solo caja |
| Anular paquete por cualquier rol | Solo caja |
| Contacto de leads hacia el psicólogo; `contacto_telefono` hacia la analista | Enmascarado por `ve_contacto` |
| Consentimiento editable o borrable (texto firmado alterable) | API solo GET/POST |
| Faro: cualquier psicólogo ve todas las alertas | **No cambiado:** decisión D1 en [04-decisiones-para-max.md](04-decisiones-para-max.md) |
