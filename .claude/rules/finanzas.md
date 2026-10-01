---
paths:
  - "finanzas/**"
  - "core/soto.py"
  - "core/gerencia.py"
---
# Finanzas

Verificado en `finanzas/api.py` y `core/permisos.py`:

- **Multitenant**: todo queryset sale de `.del_tenant_actual()`; paciente, servicio, cita y atención de un cobro se buscan con ese mismo scope (nunca por `pk` a secas).
- **Egresos**: leer = `admin` y `analista` (`ROLES_VEN_FINANZAS`); crear/editar/borrar = **solo `admin`** (`EgresoViewSet.initial`).
- **Servicios** (catálogo y precios): editar solo `admin`. Los precios públicos (sitio, FAQ, respuestas automáticas) salen de `Servicio` activos y reservables: no los escribas a mano en textos.
- **Cobros**: eliminar solo `asistente`/`admin` y siempre deja `RegistroEliminacion`. El `medio_pago` solo se guarda si el estado es `pagado`. Monto > 0.
- `CitaSerializer.cobrada` evita el doble cobro de una cita; no lo saltes con un camino nuevo de cobro (una sola vía por acción).
- **Valores por defecto honestos**: ningún campo que alimente dinero nace con un valor "probable" (medio de pago, estado pagado). Vacío y obligatorio.
- Bloqueo de doble envío en formularios de cobro, paquete, pago y egreso (botón `disabled` mientras se guarda).
- Integración con la hoja externa (`core/soto.py`): best-effort; **jamás** debe tumbar un cobro o egreso.
- `analista` es solo lectura (`BloqueoEscrituraAnalista`): ve finanzas, no escribe nada.
- Reportes por período usan `Cobro.fecha` (rangos en `America/Lima`); `marcar_pagado` la mueve al momento real del pago y exige medio de pago.
- Fuera de alcance a propósito: comprobantes electrónicos SUNAT e IGV.
- La fuente de dinero histórica importada son los cobros de LEADS; no reimportes hojas de "ingresos" (subconjunto, doble conteo).

Más contexto: ítems 11, 14, 21 del archivo histórico; `docs/software-factory-audit/04-human-factors.md` (F-R4, F-R8).
