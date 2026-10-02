---
paths:
  - "mensajes/**"
  - "core/whatsapp_cloud.py"
  - "leads/whatsapp_auto.py"
  - "leads/captacion.py"
---
# Mensajería (WhatsApp Meta / Evolution) y bitácora

Verificado en `mensajes/services.py` y `mensajes/serializers.py`:

- **Cascada por la SEDE del paciente**, nunca por la de otra: 1) Cloud API de Meta si la sede tiene número; 2) Evolution si Meta no está configurado **o rechazó explícitamente**; 3) enlace `wa.me` de respaldo.
- **Un corte de red con Meta NO se reintenta** por Evolution: no sabemos si entregó y el paciente recibiría dos mensajes.
- **"Aceptado ≠ entregado"**: un 200 de Evolution es "lo acepté". `_estado_persistido` es la única traducción a estado de la bitácora; no inventes otra.
- Todo envío pasa por `registrar_y_enviar` / `enviar_comunicacion` y queda en `mensajes.Mensaje`. Nada de envíos directos al proveedor.
- Roles de solo lectura nunca contactan pacientes (bloqueo en `registrar_y_enviar`). Un envío automático sale por la línea de captación, nunca por el número de una coordinadora ni por la línea de pruebas.
- **Imágenes**: siempre por Evolution (nunca Meta), en **base64** (una URL obligaría a publicar media). Una imagen = caption con el texto; varias = N envíos + texto al final.
- **Fallo parcial**: las partes se crean `pendiente` antes de enviar, el despacho se detiene en el primer fallo, sin reintento automático. Una parte con `external_message_id` **nunca** se reenvía ("Reintentar lo que falta" no duplica).
- `mensajes.Material` (biblioteca compartible) está separada de `pacientes.Adjunto` (clínico). Tipo real por cabecera binaria (`materiales.py::inspeccionar`); ruta `material/clinica_<id>/<uuid>`; se sirve solo por endpoint autenticado.
- **Token de firma de consentimiento**: solo `admin`/`asistente` lo reciben (`ROLES_ENVIAN_CONSENTIMIENTO`); para el resto se oculta también en el texto de la bitácora. `medico`/`analista` no ven teléfono.
- Respuesta automática de captación (`leads/whatsapp_auto.py`): sin IA, una por lead cada 12 h, textos editables como `PlantillaMensaje`, precios del catálogo.
- Mensajes masivos o reales: **pide permiso antes** de enviar algo a pacientes; en pruebas usa la línea de pruebas.
- Emojis/recientes en `localStorage` solo guardan caracteres, nunca datos del paciente.

Más contexto: ítems 4, 29 y 32 del archivo histórico.
