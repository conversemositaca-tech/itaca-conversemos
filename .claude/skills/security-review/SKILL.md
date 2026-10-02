---
name: security-review
description: Revisión de seguridad de un cambio en un proyecto de la Ítaca Software Factory (datos de salud, menores, dinero, multitenant). Úsala cuando el diff toque api.py, serializers, permisos, modelos con datos personales, integraciones, settings o pagos. Busca fugas por rol y por clínica, tokens, PII en logs, decisiones clínicas automáticas y carreras de dinero; cada hallazgo lleva escenario concreto y test que lo fija.
---

# Revisión de seguridad

Corre sobre el diff (`git diff origin/main...HEAD`). Para revisiones grandes, delega en el subagente `security-data-reviewer` y quédate con su lista.

## Lista de control (cada punto con evidencia archivo:línea)
1. **Alcance por rol**: todo queryset nuevo pasa por `acotar_*` de `core/politicas.py`. ¿Un rol recibe filas de otro dueño? → fila nueva en la matriz.
2. **Alcance por organización (tenant)**: `.del_tenant_actual()` o `organizacion=...`; FK escribibles con `RelacionesDelTenant` (si no, aceptan ids de otra organización).
3. **Campos sensibles**: teléfono, correo, documento, diagnóstico, notas clínicas, tokens, montos. ¿Quién los recibe dentro de un 200? → tabla de campos por rol.
4. **Tokens y secretos**: nunca en respuestas a roles que no los usan, ni en logs, ni en auditoría; comparación con `hmac.compare_digest`; alcance por integración.
5. **Entrada**: serializer + `validar()`; enums cerrados; relaciones del mismo dueño; nada de `request.data.get` suelto en endpoints P0.
6. **Dinero y contadores**: idempotencia (doble clic, reintento), `select_for_update(of=("self",))`, 409 en estados no válidos, auditoría.
7. **IA**: una salida de LLM nunca escribe un campo clínico oficial ni comunica algo a pacientes/familias sin revisión humana (sugerencia → revisión).
8. **Archivos**: sin URL pública; descarga por endpoint con alcance.
9. **Endpoints públicos**: throttle propio y organización fijada desde el token, no desde el body.
10. **Hosts/CSRF**: sin comodines de dominios compartidos.

## Severidad
- **CRÍTICO**: fuga de datos de salud/menores, escritura en nombre de otro, cruce de organización, dinero duplicado. Bloquea el PR.
- **ALTO**: fuga de contacto, falta de auditoría en dinero/permisos, IA sin revisión.
- **MEDIO/BAJO**: endurecimiento.

## Salida
Lista ordenada por severidad: hallazgo, escenario concreto de explotación, archivo:línea, arreglo propuesto y **test que lo fija** (matriz, campos por rol o test específico). Sin hallazgos: dilo y lista lo que revisaste.
