# Clínica SaaS — Contexto del proyecto

> Documento de contexto para Claude Code. Se lee al inicio de cada sesión.
> Mantenerlo actualizado a medida que el proyecto avanza.

## 1. Qué es

Sistema de **gestión para clínicas médicas**, pensado para venderse como **SaaS
multitenant** a varias clínicas. La primera clínica es **multiespecialidad, en
Piura, Perú**, e incluye **psicología**.

- Ubicación: `C:\projects\clinica-saas`
- Estado: arranque. Definiendo el modelo de datos.
- Dueño del producto / negocio: mismo entorno que **NOWA** (motor de contenido de
  Instagram de la psicóloga Mirai Nishimura, en `C:\projects\nowa`). **NOWA es un
  proyecto SEPARADO**: no compartir código ni base de datos con él.

## 2. Principios innegociables

### Multitenant desde el día uno
- Varias clínicas conviven en la misma plataforma con **datos totalmente aislados**.
- **Toda** tabla con datos de una clínica lleva `clinica_id` y **siempre** se filtra
  por él. Nunca una consulta sin scope de clínica.
- Sin claves foráneas que crucen clínicas.
- Son **datos de salud** → aplica la **Ley 29733 (Perú)** de Protección de Datos
  Personales. El aislamiento entre clínicas es un requisito legal, no solo técnico.

### Ritmo de trabajo (importante)
- **Una tarea a la vez.** No construir de más ni adelantarse al alcance pedido.
- **Antes de escribir código nuevo de modelo/migraciones, mostrar el plan o el
  esquema para revisarlo juntos.** Equivocarse en la base de datos es lo más caro.
- Revisar cada paso antes de pasar al siguiente.

### Fuera de alcance por ahora (NO construir todavía)
- Finanzas / reportes
- Marketing / captación
- IA

Estos vienen después. El prototipo los muestra solo como referencia de a dónde vamos.

## 3. Stack

| Pieza | Tecnología |
|---|---|
| Backend / framework | **Django 5.2 + Django REST Framework** (API REST bajo `/api/`) |
| Base de datos | **PostgreSQL 17** |
| Frontend | **React + Vite** en `frontend/`. Es el prototipo `clinica-mvp.jsx` portado, consumiendo la API. |
| Despliegue | Nube simple para empezar (a definir: Railway / Render / Fly). |

### Cómo correr en desarrollo (dos procesos)
- **Backend:** `.\.venv\Scripts\python.exe manage.py runserver` (puerto 8000).
- **Frontend:** `cd frontend; npm run dev` (puerto 5173). Vite reenvía `/api` a 8000 (sin CORS).
- Atajo: `./dev.ps1` levanta ambos.
- Datos de ejemplo: `python manage.py seed_demo` (usa `--reset` para recrearlos).

### Autenticación y roles
- Login con **sesión de Django** (endpoints bajo `api/auth/`: login, logout, me).
  La API exige usuario autenticado (`IsAuthenticated`); el tenant sale del usuario.
- El frontend envía el token **CSRF** (`X-CSRFToken`) en las peticiones que modifican
  datos. `CSRF_TRUSTED_ORIGINS` incluye el origen de Vite (5173).
- Roles: `admin` · `medico` · `asistente`. Regla aplicada: **solo médico/admin
  registran atenciones** (la asistente agenda y gestiona pacientes, pero no escribe
  en la historia clínica). Ampliar reglas de rol según haga falta.
- Cuentas demo (contraseña `demo1234`): `castro@sanrafael.pe` (médico),
  `admin@sanrafael.pe` (admin), `asistente@sanrafael.pe` (asistente).

### Mensajería WhatsApp (Evolution API)
- Envío vía **Evolution API** (self-hosted en EasyPanel del usuario). Config por
  entorno: `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`. La
  instancia puede ir por clínica en `Clinica.whatsapp_instance` (si vacío, usa la
  del entorno). Código en `mensajes/evolution.py` (endpoint `/message/sendText/`).
- Si Evolution no está configurado o falla, se devuelve un **enlace wa.me** de
  respaldo y el frontend abre WhatsApp para enviar a mano. Todo queda en la
  **bitácora** (`mensajes.Mensaje`: tipo, estado, paciente/cita, enviado_por).
- Flujos: recordatorio de cita (editable) y mensaje de seguimiento desde la ficha.

Decisión multitenant: **base y esquema compartidos, con `clinica_id` por fila**
(row-level). Reforzar el aislamiento en la capa de aplicación (manager + middleware
que fija la clínica del usuario logueado) y, como endurecimiento, evaluar **Row Level
Security de Postgres**.

## 4. Referencia de diseño — `clinica-mvp.jsx`

Prototipo React que define **estética y flujos**. Estilo: **limpio y calmado tipo
Notion, verde salvia, sin saturar**. Espacios amplios, bordes redondeados suaves,
nada estridente.

### Tokens de color (del prototipo)
```
--bg:        #FBFAF8   (fondo crema muy claro)
--surface:   #FFFFFF
--ink:       #32302C   (texto principal)
--ink-soft:  #6B6760
--muted:     #9B968D
--line:      #ECE8E1   (bordes)
--accent:    #4F8A77   (verde salvia — color de marca)
--accent-soft:#E9F1ED
--hover:     #F3F1EC
--wa:        #2F8F5B   (verde WhatsApp, para recordatorios)
```
- Tipografía: **Inter**, `letter-spacing:-0.01em`, antialiased.
- Radios: ~8–14px. Tags tipo pastel por especialidad y por estado de cita.

### Flujos que muestra el prototipo
- **Hoy**: resumen del día (agenda, finanzas, marketing, retención) — vistazo rápido.
- **Agenda**: citas del día con estado (Confirmada / Por confirmar / Atendida),
  recordatorio por WhatsApp, botón "Atender".
- **Pacientes**: lista con búsqueda + filtro por especialidad; ficha con historia
  clínica (timeline de atenciones); crear/editar paciente.
- **Atender**: nota de atención con plantilla por especialidad → se guarda en la
  historia clínica.
- **Marketing** y **Finanzas**: solo referencia visual; fuera de alcance por ahora.

## 5. Especialidades de la primera clínica (del prototipo)
Medicina General, Pediatría, Psicología, Cardiología, Dermatología, Nutrición.
Cada clínica configurará las suyas; no hardcodear globalmente.

## 6. Reglas de español
Español peruano (tú/tienes/puedes), nunca voseo argentino. Considerar la cultura y
los feriados de Perú. Zona horaria por defecto: `America/Lima` (GMT-5).

## 7. Plan por etapas

1. ✓ Modelo de datos multitenant + migraciones + base local.
2. ✓ API REST + frontend con el diseño del prototipo (Hoy, Agenda, Pacientes).
3. ✓ Login con sesión y roles (médico / asistente / admin).
4. ✓ Mensajería WhatsApp (Evolution API real, funcionando) + bitácora.
5. ✓ Recordatorios automáticos (`enviar_recordatorios` + `recordatorios.ps1`) +
   identidad real: **Mont' Sinai - Centro Médico** (Piura) con sus especialidades.
6. ✓ Módulo de Leads / Captación (app `leads`): embudo, cierre por doctor y por
   fuente, captar/mover/convertir. La sección "Captación" reemplaza el Marketing demo.
7. ✓ Historia clínica mejorada:
   - **Antecedentes** en `Paciente` (alergias, antecedentes/condiciones, medicación
     habitual). Se editan desde el modal de paciente; se ven arriba en la ficha
     (alergias en rojo cuando hay).
   - **Atención estructurada** en `Atencion` (todo opcional menos que llegue al menos
     un campo de texto): motivo, signos vitales (presión, FC, temperatura, peso,
     talla), diagnóstico, indicaciones/receta y la nota/evolución libre con plantillas.
     `registrado_por` guarda quién la cargó. Sigue siendo **append-only** (Ley 29733).
   - **Adjuntos** (`pacientes.Adjunto`): subir laboratorios, ecografías, PDFs e
     imágenes (FileField en `MEDIA_ROOT`, aislado por `clinica_id`/paciente en disco).
     Descarga SIEMPRE por endpoint autenticado y con scope de clínica
     (`/api/adjuntos/{id}/descargar/`, `as_attachment`); **no** hay URL pública de
     media. Máx. 25 MB y lista blanca de extensiones. Subir: cualquier rol; eliminar:
     solo médico/admin (borra también el archivo del disco).
8. ✓ Agenda a futuro. `Cita.inicio` ya guardaba fecha+hora (sin migración). Crear
   cita acepta `fecha` (YYYY-MM-DD; si falta, hoy); el serializer expone `fecha` ISO.
   Acciones `mover` (reagenda y vuelve a "Por confirmar", limpia recordatorio) y
   `cancelar` (estado CANCELADA, no se borra). Frontend: componente `Agenda` con
   navegación ‹ Hoy › + selector de fecha y dos vistas — **Día** (lista con Atender/
   Recordar/Mover/Cancelar) y **Semana** (grilla calendario, 7 columnas; clic en un
   día/cita salta a Día). "Hoy" ahora cuenta SOLO las citas del día. `HOY_FECHA` del
   front se calcula (antes estaba hardcodeado). El filtrado por día es en cliente
   (la app ya carga las citas); si el volumen crece, mover a filtro por rango en API.
9. ✓ Ingreso automático de leads. Cada clínica tiene un **token de captación**
   (`Clinica.token_captacion`, generado al primer uso) que da dos URLs públicas
   (sin sesión, identificadas por el token; se fija `clinica=` al crear el lead):
   - **Web/campañas** `POST /api/captacion/<token>/` (nombre, telefono, fuente,
     es_pauta, campania, especialidad, mensaje) → crea Lead estado=NUEVO. Para
     formularios web, landings, Meta Lead Ads vía Zapier/Make.
   - **WhatsApp** `POST /api/captacion/whatsapp/<token>/` = webhook de Evolution:
     el primer mensaje de un número desconocido crea un Lead fuente=whatsapp
     (ignora salientes/grupos; siempre responde 200). Código en `leads/captacion.py`.
   - **Anti-duplicados** por teléfono (lead abierto reciente o ya paciente → no
     duplica, suma nota). Throttle `captacion` 60/min. Endpoints autenticados
     `config` (token + rutas) y `regenerar` (solo admin). Frontend: panel "Recibir
     leads automáticamente" en Captación (URLs + copiar + regenerar + **Probar con
     un lead de ejemplo**, que ya funciona local). El ingreso real "en vivo" requiere
     desplegar (hoy corre local) o un túnel.
10. ✓ Panel de Gerencia (rol admin / dueño). Tablero ejecutivo **solo lectura** con
   datos REALES del período (Hoy / Semana / Mes): operación (citas, atendidas,
   canceladas, % asistencia/cancelación, recordatorios), captación (leads, % pauta,
   cierres, tasa, mejor fuente/campaña), pacientes (total, nuevos, sin próxima cita)
   y productividad por médico (citas, atenciones, leads, cierres). Sin cambios de
   modelo (agrega `GET /api/gerencia/resumen/` en `core/gerencia.py`). Ingresos =
   tarjeta "por activar" (esperan Finanzas reales). En el frontend, el ítem "Gerencia"
   del menú aparece solo para admin; componente `Gerencia` con selector de período.
11. ✓ Finanzas reales (app `finanzas`). Modelos **Servicio** (catálogo de precios por
   especialidad) y **Cobro** (paciente, atención/cita opcional, concepto, monto S/.,
   estado Pagado/Pendiente/Anulado, medio Efectivo/Yape/Plin/Tarjeta/Transferencia,
   registrado_por). API: `servicios` (editar solo admin), `cobros` (+`marcar_pagado`,
   `resumen` con KPIs y por medio). **Dos caminos de cobro**: opcional al **Atender**
   (campos `cobro_*`) y botón **Cobrar** en la cita atendida de la Agenda + pantalla
   **Finanzas** (KPIs reales, lista, registrar, marcar pagado, catálogo de precios).
   `CitaSerializer.cobrada` evita doble cobro. El panel de **Gerencia** ya muestra
   ingresos reales (`finanzas_activas=True`). Seed `seed_finanzas` (precios + cobros).
12. ✓ Tanda de mejoras (sesión autónoma 2026-06-12):
   - **Equipo/usuarios** (app `usuarios`): `UsuarioViewSet` admin-only (crear con
     contraseña, editar rol/especialidad, activar/desactivar [soft], resetear clave;
     no puede auto-desactivarse). Pantalla "Equipo" (nav solo admin).
   - **"Hoy" real** (`GET /api/hoy/`): citas del día, leads nuevos, sin próxima cita,
     e ingresos del día (solo admin). Reemplaza las tarjetas demo (FIN/MKT).
   - **Estado de cuenta + próxima cita** en `PacienteSerializer` (`cuenta`={cobrado,
     pendiente,items}, `proxima`). Se ven en la ficha y en la lista (tag "Debe S/").
   - **Exportar CSV** (cliente, con BOM) de cobros, leads y pacientes.
   - **Retención**: filtro "Sin próxima cita" en Pacientes + búsqueda por teléfono.
     La tarjeta de retención de "Hoy" abre ese filtro.
   - **Gráficos** sin librerías: barras de ingresos por día (Finanzas, `resumen.por_dia`)
     y sparkline de evolución de peso en la ficha.
   - **Config de la clínica** (`GET/PATCH /api/clinica/`, editar solo admin): nombre y
     ciudad, en la pantalla Equipo.
   - **Tendencias** en Gerencia (`resumen.anterior`: compara con el período previo).
   - **Aviso de choque de horario** al agendar (no bloqueante) + acción `confirmar`
     cita (estado CONFIRMADA).
13. ✓ Batch 2 (misma sesión autónoma): **confirmar** cita desde la agenda (acción
   `confirmar` → estado CONFIRMADA), **cumpleaños del día** en "Hoy" (calculado en el
   front), **imprimir** historia clínica / guardar PDF (ventana nueva, `imprimirHistoria`),
   **lead → asignar médico** desde Captación (PATCH lead.medico), **agendar cita desde
   la ficha** (AgendarModal con `pacienteFijo`) y **filtro por médico** en la Agenda.
14. ✓ Finanzas completa (egresos + caja). Modelo **Egreso** (concepto, categoría
   [insumos/sueldos/alquiler/equipos/marketing/otro], monto, medio de pago, proveedor,
   registrado_por); **todo el módulo de egresos es solo admin** (`EgresoViewSet.initial`).
   **Caja** `GET /api/finanzas/caja/?periodo=` (admin): Ingresos (cobrado) − Egresos =
   **Utilidad**, flujo por día y egresos por categoría. La pantalla **Finanzas** suma,
   para admin, la "Caja del período" (Ingresos/Egresos/Utilidad/Pendiente) y la sección
   **Egresos** (agregar/eliminar); la asistente sigue viendo solo cobros. **Gerencia**
   cambia la tarjeta "Ingresos" por **Dinero** (Ingresos/Egresos/Utilidad/Pendiente).
   Fuera de alcance (a propósito): comprobantes electrónicos/SUNAT e IGV. Referencia
   tomada del sistema actual de la clínica, **Medlink** (módulo Finanzas: Egresos/Caja).
15. ✓ Ficha de paciente completa (estilo peruano / Medlink). `Paciente` += `tipo_documento`
   (DNI/CE/Pasaporte/RUC, default DNI), `numero_documento`, `direccion`, `genero`
   (Femenino/Masculino/Otro, opcional). Serializer expone `tipo_documento_label` y
   `genero_label`. En el modal de paciente hay sección **Identificación**; la ficha y la
   lista muestran el documento; **se busca por número de documento** (además de nombre/
   teléfono) y el CSV de pacientes incluye documento/género/dirección. Migración aditiva.
   Pendiente afín: reporte demográfico (género/edad) en Gerencia, como el de Medlink.
16. ✓ Reporte demográfico en Gerencia (estilo Medlink). `GET /api/gerencia/resumen/`
   suma `demografia`: pacientes **por género** (Femenino/Masculino/Otro/Sin registro) y
   **por rango de edad** (0-24, 25-35, 36-45, 46-55, +56, Sin registro), sobre toda la
   base. Sin cambios de modelo (usa `genero` y `fecha_nacimiento`). Frontend: componente
   `BarrasH` (barras horizontales sin librerías) en el panel de Gerencia, en grilla de
   dos columnas (`.ca-demo`). Probado: ambas sumas cuadran con el total de pacientes.
17. ✓ Reportes visuales (gráficos sin librerías). Nuevo componente `MiniBarsDuo`
   (doble serie). **Finanzas**: gráfico de **Flujo de caja** (ingresos vs egresos por
   día, admin, desde `caja.por_dia`); el de "Ingresos por día" simple queda solo para
   no-admin. **Gerencia**: gráfico de **Citas por día** (operación, `operacion.por_dia`
   nuevo en `GerenciaResumenView`). `MiniBars` ahora acepta `fmt` (default money) para
   reusarlo con conteos. Probado: ambas series llegan al front.
18. ✓ Usuarios y roles más completos. `Usuario` += `telefono`. Nuevo endpoint
   `POST /api/auth/cambiar-password/` para que **cualquier** usuario cambie SU propia
   contraseña (pide la actual; `update_session_auth_hash` mantiene la sesión). Frontend:
   botón llave en el pie de la barra lateral → `CambiarPasswordModal` (todos los roles).
   Pantalla **Equipo** ahora con **buscador** (nombre/correo/teléfono), **filtros por rol**
   (Todos/Médicos/Asistentes/Administradores/Inactivos), teléfono en el modal y la lista, y
   tarjeta **"¿Qué puede hacer cada rol?"** (explica admin/médico/asistente). Probado
   end-to-end (incl. validaciones y que el reset de claves de otros sigue siendo solo admin).
19. ← Próximo (sin definir). Requiere acción del usuario / permisos: **desplegar**
   (Railway/Render/Fly) para captación y recordatorios en vivo; conectar la línea
   WhatsApp oficial (+51 941 697 769) a Evolution; programar la Tarea de Windows de
   `enviar_recordatorios`. Otras ideas sin desplegar: notas internas del paciente,
   receta imprimible aparte, gráficos por médico, recordatorios masivos (¡envía
   WhatsApp real! pedir permiso antes), confirmación bidireccional por webhook.
