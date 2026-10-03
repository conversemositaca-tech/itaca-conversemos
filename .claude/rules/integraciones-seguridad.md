---
paths:
  - "core/integraciones.py"
  - "core/permisos.py"
  - "core/tenant.py"
  - "core/middleware.py"
  - "**/api.py"
  - "**/api_*.py"
  - "**/serializers.py"
  - "config/settings.py"
---
# Integraciones, permisos y seguridad

- **Tenant**: todo queryset con `.del_tenant_actual()` (o filtro por `clinica`); objetos referenciados por id en el body se buscan con el mismo scope. Nunca `Model.objects.get(pk=...)` suelto.
- **Permisos**: globales `IsAuthenticated` + `BloqueoEscrituraAnalista`. Las reglas por rol viven en `core/permisos.py` (constantes `ROLES_*`); no repitas `rol == "..."` a mano en vistas nuevas ni en el frontend (exponer el permiso en `/api/auth/me/`).
- **Matriz** `core/tests_matriz_permisos.py` (168 celdas rol × endpoint) = la política. Cambiar una celda es cambiar política: requiere aprobación de la dirección. Un endpoint nuevo entra a la matriz.
- **Regresión P0** `core/tests_seguridad_p0.py`: no la debilites para que pase un cambio.
- **Contacto**: `medico` y `analista` no ven teléfono (`oculta_contacto`). Solo admin/asistente contactan pacientes y reciben el token de firma de consentimiento (oculto también en la bitácora).
- **Datos clínicos** (atenciones, adjuntos, sugerencias de riesgo): comercial nada; psicólogo solo sus pacientes.
- **Integraciones** (`/api/integraciones/*`): cabecera `X-Integracion-Token` comparada con `hmac.compare_digest`; token por alcance `ITACA_TOKEN_ELI` / `ITACA_TOKEN_TAREAS` / `ITACA_TOKEN_RESPALDO`. Vacío = ese alcance acepta el compartido `ITACA_INTEGRACION_TOKEN`; con token propio, el compartido deja de abrirlo. Sin ninguno, apagado. Throttle `integracion`. Vista nueva = declarar `alcance_integracion`.
- **IA**: nunca escribe `Paciente.riesgo` (crea `SugerenciaRiesgo`) ni decide altas, derivaciones o DP.
- **Hosts**: `RAILWAY_DOMINIO_SERVICIO` (por defecto el dominio de producción) explícito; **nunca** comodines `*.up.railway.app` en `ALLOWED_HOSTS` ni en CSRF.
- El hasher barato (MD5) solo bajo `manage.py test`; producción usa PBKDF2 (`core/tests_hasher.py` lo fija).
- Endpoints públicos (captación, agendar, sitio, embudo) con token en la URL o sin sesión: siempre con throttle propio y fijando `clinica` desde el token, nunca desde el body.
- Secretos solo por variables de entorno; **no leas `.env`**; `.env.example` documenta nombres, no valores.

- **Políticas** en `core/politicas.py`: `acotar_clinico`, `ficha_de`, `ve_contacto`, `puede_registrar_pago`, `exigir(...)`, `SoloRoles.de(...)`. No escribas `rol == "..."` en vistas nuevas.
- **Entrada**: endpoints que escriben validan con un serializer vía `core.serializadores.validar()`; FK escribibles con `RelacionesDelTenant` (si no, aceptan ids de otra clínica).
- **Auditoría**: acciones sensibles (dinero, estados de cita, consentimiento, riesgo, archivos, roles) llaman `core.auditoria.auditar(actor, accion, objeto, {campo: [antes, después]})`.
- **Visibilidad por campo**: `core/tests_campos_por_rol.py`; un campo sensible nuevo entra a esa tabla.

Más contexto: `docs/software-factory-audit/` (01, 13, 15) y ítems 9, 12, 18 del archivo histórico.
