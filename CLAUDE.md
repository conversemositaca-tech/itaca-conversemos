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
- Roles: `admin` · `medico` · `asistente` · `comercial` · `analista`. Regla aplicada:
  **solo médico/admin registran atenciones** (la asistente agenda y gestiona
  pacientes, pero no escribe en la historia clínica). `analista` (Dirección
  Clínica) es **solo lectura**: `core/permisos.py` bloquea toda escritura desde
  `DEFAULT_PERMISSION_CLASSES`, ve ambas sedes (sede vacía), indicadores y
  finanzas en lectura, y no ve contacto de pacientes (como el médico).
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
20. ✓ Importación de datos REALES de Conversemos Lima (2026-06-19). Comando
   `pacientes/management/commands/importar_lima.py`: lee el Excel operativo
   ("LEADS LIMA-CONVER.xlsx", hoja LEADS, 6126×151) con librería estándar (un .xlsx
   es un zip de XML; sin openpyxl) y reparte cada fila en `Lead` (embudo),
   `Paciente` (si convirtió) y `finanzas.Cobro` (consulta + pagos de hasta 12
   procesos). **Reemplaza SOLO la sede Lima** (Piura queda intacta); flags `--dry-run`
   y `--keep`. Parsea fechas-serie de Excel y montos sucios (tope S/5000 → descarta
   fechas mal tipeadas en celdas de monto; limpia nombres tipo "(30 años)" y basura
   "20 años"). Los psicólogos del Excel que no estaban en el directorio se crean como
   fichas **INACTIVAS** (activo=False) para no perder el vínculo. Resultado: **710
   pacientes, 3680 leads, 2655 cobros (S/439 358)** en Lima. Backup previo en
   `C:\projects\db-itaca-backup-2026-06-19-pre-importlima.sqlite3`. **Pendiente**: las
   otras 7 hojas del Excel (ingresos, Atenciones, SEG. DE PACIENTES…) y los datos de
   Piura. (El archivo Excel tiene PII real — Ley 29733 — NO subirlo al repo.)
21. ✓ Historial de SESIONES de Lima (línea de tiempo clínica; antes había 0) →
   `pacientes/management/commands/importar_atenciones_lima.py`. Lee y **combina dos
   hojas** del Excel, deduplicando por (paciente, fecha): "Atenciones" (bloques por
   psicólogo con N° de sesión, ~feb 2024–mar 2025, 4 psicólogos) + "Atenc de pacientes"
   (pares Fecha/Paciente, ~nov 2025–feb 2026). Crea `Atencion` **sin cobros** (el dinero
   ya vino de LEADS → evita doble conteo). Empareja por nombre exacto y nombre+apellido;
   los no hallados se crean como paciente nuevo de Lima. Resultado: **1352 atenciones
   (2024–2026)** + 93 pacientes nuevos → **863 pacientes Lima**. Cobros intactos: 2655 /
   S/439 358. (1 atención sin fecha cayó a hoy; artefacto menor.) `limpiar_nombre` quita
   notas de agenda pegadas ("- reprogramada"). Backup previo en
   `C:\projects\db-itaca-backup-2026-06-19-pre-atenciones.sqlite3`.
   - **Decidido por los datos**: la hoja `ingresos` (S/56 800, oct 2024–dic 2025) es un
     **subconjunto**, NO el ledger completo → la fuente de dinero sigue siendo LEADS;
     `ingresos` NO se importó (evita doble/sub-conteo).
   - **Pendiente**: `pagos adelantados a ps` (egresos a psicólogos; vienen en N° de
     sesiones, no en S/), y todos los datos de **Piura**.
22. ✓ Indicador de RETENCIÓN en Gerencia + fecha de registro real (2026-06-19).
   - `core/gerencia.py`: el resumen incluye el bloque `retencion` (semáforo por días
     desde la última atención — regla de la clínica/hoja SEG: verde <8, amarillo 8–15,
     rojo >15), calculado de las atenciones **sin cambios de modelo**. Frontend: bloque
     "Retención" en el componente `Gerencia` (App.jsx), guardado por `data.retencion`.
   - Nuevo comando `fijar_fechas_registro`: pone `Paciente.creado_en` = primera
     actividad real (lead/cobro/atención) en vez de la fecha del import → corrige el
     "nuevos este mes = todos" en Gerencia (bajó de 925 a 78). Idempotente; solo mueve
     la fecha hacia atrás.
   - Nuevo comando `fusionar_duplicados`: fusiona pacientes duplicados de Lima creados
     por las distintas importaciones (un registro "delgado" solo-atenciones cuyos tokens
     ⊆ un registro "rico" con cobros/leads/teléfono y mismo primer nombre; salta los
     ambiguos). Fusionó **84** (863→**779** pacientes Lima); atenciones/cobros intactos.
     Backup en `C:\projects\db-itaca-backup-2026-06-19-pre-fusion.sqlite3`.
   - Con datos históricos (sesiones hasta feb 2026) la retención sale casi toda "roja":
     en la práctica es la lista de pacientes a reactivar; en uso en vivo será real.
   - OJO: el backend corre con `--noreload` (puerto 8001) → tras cambiar código Python
     hay que reiniciarlo para que tome los cambios.
23. ✓ Integración de PIURA + import genérico por sede (2026-06-19). `importar_lima`,
   `importar_atenciones_lima` y `fusionar_duplicados` ahora aceptan `--sede {lima|piura}`
   y `--archivo`. `importar_lima` pasó a **header-driven** (ubica columnas por NOMBRE de
   encabezado, no por posición): el Excel de Piura tiene otro layout (sin INVITADOS,
   pagos sin MEDIO, hasta 5 pagos por proceso). En `importar_atenciones_lima` la fila de
   psicólogos se toma de la primera fila (Piura intercala una fila de mes) y se **omiten
   las sesiones sin fecha** (antes caían a "hoy" y ensuciaban la retención). Regresión
   Lima: idéntica (779/3680/2655/S439 358/1352).
   - Piura importado de "LEADS PIURA - CONVERSEMOS (1).xlsx": **1095 pacientes, 3996
     leads, 3187 cobros (S/463 755), 1481 atenciones**; +3 psicólogos inactivos; 76
     duplicados fusionados. Backup `C:\projects\db-itaca-backup-2026-06-19-pre-piura.sqlite3`.
   - **TOTAL del sistema (Lima+Piura)**: 1874 pacientes · 7677 leads · 5842 cobros
     (**S/903 113**) · 2833 atenciones. Retención: 802 en rojo = lista de reactivación.
   - Sigue **pendiente**: egresos a psicólogos (`pagos adelantados a ps`, falta tarifa
     por sesión) y conectar WhatsApp/desplegar.
24. ✓ Editor tipo Excel (2026-06-19). Vista **"Editar (Excel)"** (nav solo admin):
   grillas con **edición en celda** para los formatos editables — Pacientes, Leads,
   Cobros, Servicios, Egresos, Profesionales. (Atención: editable a pedido — ver item 25.)
   - Componentes `HojasExcel` + `HojaEditable` en `frontend/src/App.jsx`, con una config
     `FORMATOS` por entidad (columnas tipo text/num/fecha/select/fk/check/ro). Cada celda
     se guarda sola al salir (Enter o blur) vía PATCH; "Nueva fila" hace POST con
     defaults válidos; FK (psicólogo/médico) son selects cargados de
     profesionales/medicos. Borde verde=guardado, rojo=error.
   - Capa genérica nueva en `api.js`: `hojaListar/hojaActualizar/hojaCrear/hojaBorrar`
     (sirven cualquier endpoint del router DRF).
   - Buscador + **tope de 250 filas** renderizadas (las tablas grandes —leads 7677,
     cobros 5842— se traen completas pero se filtran/recortan en cliente para no colgar
     el navegador). Cobros: edición sí, "Nueva fila" no (se crean en Finanzas/Atender).
   - Permisos: la vista es admin-only; egresos/servicios además exigen admin en el
     backend. Probado CRUD end-to-end (crear/editar/borrar).
25. ✓ Historias clínicas editables + edición conectada al resto (2026-06-19, a pedido).
   - Se relajó el append-only de `Atencion` SOLO para **corregir** (no borrar): nuevo
     `AtencionViewSet` (`/api/atenciones/`, registrado en el router) con list/retrieve para
     todos y **PATCH solo médico/admin**; `create`→405 (las atenciones se crean al Atender)
     y `destroy`→405 (Ley 29733). `AtencionSerializer` ahora expone `paciente_nombre` y
     `registrado_por_nombre`; los campos clínicos (motivo, diagnóstico, indicaciones, nota,
     signos vitales, especialidad) son editables. En el editor Excel se agregó el formato
     **"Historias clínicas"** (con aviso, sin "Nueva fila").
   - **Auditoría de correcciones** (implementada): nuevo modelo `pacientes.EdicionAtencion`
     (clinica, atencion, campo, antes, despues, editado_por, creado_en; migración 0007).
     `AtencionViewSet.perform_update` registra una fila por **cada campo que cambió**
     (valor anterior→nuevo, quién, cuándo). El serializer expone `ultima_edicion`
     ("quién · fecha"), visible como columna en el grid. Así la historia clínica se
     **corrige con trazabilidad** (no se pierde el valor previo) · Ley 29733.
   - El editor ahora **refresca el sistema**: al salir de "Editar (Excel)", si hubo cambios,
     llama a `cargarDatos()` (recarga pacientes/citas/servicios compartidos) para que las
     otras pestañas reflejen lo editado. De fondo, todo escribe en la MISMA BD/API: las
     pantallas que recargan al entrar (Gerencia, Finanzas, Pacientes…) ya ven los cambios.
26. ✓ Integración Google Calendar (scaffold, service account) (2026-06-19). `core/gcalendar.py`
   sincroniza las **citas** con Google Calendar usando un **service account**, con degradación
   elegante (no-op si faltan credenciales o la librería — igual patrón que WhatsApp). Hooks en
   `CitaViewSet`: crear/atender/mover/confirmar → upsert del evento; cancelar → borra el evento.
   Evento con id determinístico `itacacita<ID>` (no guarda nada extra en la BD). Calendario por
   sede en settings: `GOOGLE_CALENDAR_CREDENTIALS` (ruta al JSON o el JSON), `GOOGLE_CALENDAR_LIMA`
   / `GOOGLE_CALENDAR_PIURA`, `GOOGLE_CALENDAR_ID` (respaldo). Libs pineadas en requirements
   (google-api-python-client, google-auth). Comando `python manage.py test_gcalendar` para
   verificar credenciales/acceso. `.env.example` documentado.
   - **FALTA (acción del usuario)**: crear el service account en Google Cloud, activar Calendar
     API, compartir cada calendario con su email (permiso editor) y poner las variables. Probado:
     sin credenciales queda no-op y el flujo de citas (crear/cancelar) sigue OK.
   - **Re-auditoría 2026-06-19**: `manage.py check` 0 problemas; 24/24 endpoints responden 200;
     el frontend compila; datos consistentes en ambas sedes. Sin tests automatizados (stubs);
     verificación por smoke-test de la API en vivo.
28. ✓ Ficha clínica estilo AgendaPro (2026-06-20, según capturas de Emma). `Atencion` +=
   `tipo` (evolucion|historia) + `aspectos_historicos`, `objetivos`, `puntos_importantes`,
   `proximos_pasos` (migración 0008). Dos formatos como AgendaPro:
   - **Historia clínica** (una vez): Motivo (`motivo`), Aspectos históricos
     (`aspectos_historicos`), Objetivos (`objetivos`), Impresión dx (`diagnostico`).
   - **Ficha de evolución** (cada sesión): Resumen (`nota`), Puntos importantes
     (`puntos_importantes`), Próximos pasos (`proximos_pasos`), Tratamiento/tareas
     (`indicaciones`).
   `AtenderModal` rediseñado: selector de tipo + esos campos (se quitaron los signos
   vitales, no aplican a psicología). El dictado por voz llena el set activo según el tipo
   (`estructurar_nota` usa prompt por tipo; listas → viñetas). Endpoint atender, serializer,
   auditoría (CAMPOS_AUDIT) y editor Excel incluyen los campos nuevos. Las atenciones
   importadas quedan `tipo=evolucion` con su texto en `nota` (Resumen).
27. ✓ Notas clínicas por VOZ (Whisper, dentro del sistema) (2026-06-20, a pedido de Emma).
   En el modal **Atender**, el psicólogo sube/graba un audio de la sesión → `POST
   /api/transcribir/` (`TranscribirView`, solo médico/admin) lo transcribe con **Whisper
   local** (faster-whisper, `core/transcripcion.py`, gratis; tamaño por `WHISPER_MODEL`,
   default `small`) y —si hay `OPENAI_API_KEY`— lo **estructura** en motivo/diagnóstico/
   indicaciones/nota (`core/estructurar_nota.py`, vía `requests` a OpenAI; opcional, con
   degradación elegante: sin clave la transcripción cae a la nota). El endpoint NO guarda:
   devuelve `{transcripcion, estructura}`, el front pre-llena los campos y el terapeuta
   revisa y guarda con el flujo normal → queda en la historia clínica editable + auditada.
   Frontend: botón "Dictar / subir audio" en `AtenderModal` + `api.transcribirAudio`.
   `faster-whisper==1.2.1` pineado (corre en Python 3.14). Resuelve el problema histórico
   de adherencia (idea de Emma: "no pedirles que escriban"). Pendiente opcional: clave de
   OpenAI para el auto-estructurado; grabar en el navegador (hoy se sube archivo / audio WA).
29. ✓ Captación por WhatsApp automática (corrección #3 de Gaby, 2026-08-11). El mensaje de
   bienvenida solo pedía el número y la conversación se trababa cuando la persona respondía
   otra cosa (preguntas de terapia/costos, "quiero cita en Miraflores, Lima").
   - Nuevo `leads/whatsapp_auto.py` (sin IA, sin servicios externos): `analizar(texto)` saca
     **ubicación** (distrito → sede; gana el distrito más específico y se compara palabra
     exacta para no confundir "Ate" con "atención"), **tipo de consulta**
     (`Lead.TipoServicio`: pareja/niños/adolescentes/familia/lenguaje/evaluación/adultos),
     **modalidad** (online/presencial) y si **pide cita**; `armar_respuesta(...)` contesta las
     **preguntas frecuentes** (tipos de terapia, precios, ubicación, cómo agendar) y agrega el
     enlace de **auto-agendamiento** (`/agendar/<token>`) cuando pide cita.
   - Textos editables como **plantillas** (`mensajes.PlantillaMensaje`, claves `faq_servicios`,
     `faq_precios`, `faq_ubicacion`, `faq_agenda`); si no existen, se usa el texto por defecto
     del módulo y los **precios salen del catálogo real** (`Servicio` activos y reservables).
     La respuesta pide solo los datos que faltan y se envía por la vía normal
     (`mensajes.services.registrar_y_enviar`, tipo nuevo `Mensaje.Tipo.AUTOMATICO` → queda en
     la bitácora). Tope: una respuesta automática por lead cada `VENTANA_RESPUESTA_HORAS` (12).
   - `Lead` += `ubicacion`, `pide_cita`, `auto_respondido_en` (migración 0012, aditiva) y el
     serializer expone `espera_respuesta` (llegó por chat, estado nuevo, sin seguimiento y de los
     últimos `DIAS_BANDEJA`=30 días, para que el histórico importado no llene la bandeja).
     Enganchado en el webhook de Evolution (`IntakeWhatsappView`, también cuando el lead ya
     existe y vuelve a escribir) y en `core.whatsapp_cloud._capturar_leads`.
   - Frontend: bandeja **"Solicitudes por WhatsApp"** al inicio de Captación (pendientes
     ordenados por *pide cita* y días esperando, con ubicación/tipo/mensaje, botones Responder
     (wa.me) · Atendido · Editar, y contadores "piden cita" / "esperan 2+ días"), campo
     **Distrito** en el modal de lead, columnas Distrito/Pide cita en el editor Excel y
     `POST /api/leads/probar-whatsapp/` con su panel **"Probar respuesta automática"** (muestra
     lo detectado y el texto, sin crear lead ni enviar nada).
   - Pruebas: `leads/tests.py` cubre los casos reales de las capturas (`python manage.py test leads`).
   - **Pendiente (fuera de alcance)**: `core.whatsapp_cloud._capturar_leads` sigue **sin
     enganchar** al webhook de Meta (`WhatsappWebhookView.post` solo registra en log, como
     antes); mientras la línea oficial viva en Cloud API hay que conectarla ahí.
30. ✓ Centro de Continuidad (2026-09-09; **desplegado**, PR #92 y siguientes).
   "Evaluar continuidad" pasa a ser una herramienta de gestión para Analista + Coordinación.
   - **Cola** (`core/continuidad.py`): 8 estados en 3 grupos — Acción (vencido, cierra hoy,
     **riesgo_s3**, pre-cierre sin cita), Seguimiento (próximo), Calidad (continuó sin decisión,
     **dato_incompleto** = ninguna cita numerada, backlog). `ACCIONABLES` ya no incluye próximo.
     **La decisión de cada cierre se evalúa contra la cita de ESE bloque** (`cita_de_sesion`,
     `metas_cerradas`), no contra la última cita: S6 con DP + S7 sin DP no reclama nada; S6 sin
     DP + S7 = "continuó" con meta 6. Cada fila trae `evento` = identidad estable (tipo, meta,
     `cita_referencia` que sale de la condición, `anclas`) y `anteriores_sin_decision`.
   - **Contexto de notas** (`core/notas_operativas.py`): resume `Cita.notas` en señales
     operativas; NUNCA decide nada clínico (una mención de alta/derivación solo produce
     "verificar registro formal"). `que_confirmar()` da la frase operativa.
   - **Gestión** (`pacientes.GestionContinuidad` + `HistorialContinuidad`, migración 0034;
     lógica en `core/gestion_continuidad.py`): estado de revisión / resultado / responsable /
     observación + auditoría. Una gestión abierta por (paciente, tipo, meta); se crea en el
     primer "Guardar seguimiento" (abrir el panel no escribe). **Resuelto no silencia la
     cola**: si la fuente oficial sigue detectando el caso, se muestra la alerta. Señales en
     `pacientes/signals.py` reconcilian al guardar/borrar citas: cierre automático con
     historial, reapertura si la corrección se revierte; una resolución manual nunca se pisa.
   - **Permisos**: `PuedeGestionarContinuidad` (admin, asistente, medico, **analista**) SOLO en
     `PATCH /api/continuidad/caso/<id>/gestion/`; el analista sigue solo lectura en todo lo
     demás (tests en `core/tests_gestion_continuidad.py`). Alcance por `pacientes_del_rol`.
   - **Tarjeta Hoy**: `prioritarios_para_tarjeta` (un caso por categoría accionable + relleno).
   - **Reinicio de proceso resuelto (2026-09-10, alternativa A)**: `core/continuidad.py` parte
     la historia en TRAMOS (`segmentar_procesos` / `proceso_actual`). Una bajada de `n_sesion`
     es solo candidato a reinicio; se acepta con respaldo estructurado (nueva sesión = 1; DP de
     cierre 04/09/10/11/12 en el tramo anterior; consulta o DP-01/02/03 entre medias; cambio de
     etapa en `SeguimientoSesion`; lead convertido). El tiempo (60 días) solo refuerza una
     bajada a 1 o 2, nunca decide solo. Sin respaldo (S1…S6, S5) = continuidad + marca
     `numeracion_inconsistente`. `sesion_real` = máximo del tramo actual (ya no el histórico);
     toda la cola, anclas y `anteriores_sin_decision` trabajan solo con el tramo. Los procesos
     previos sin DP van a **"Calidad de registro · Procesos anteriores sin cierre"**
     (`EstadoCierre.PROCESO_ANTERIOR`, filas aparte vía `indicadores`), nunca a la acción.
     Portado de PR #71: `MARCADOR_IMPORTADO_AGENDAPRO` → `migrado_sin_actividad`, "Falta
     agendar", y sus 8 tests (`core/tests_proceso.py`, 40 tests). Frontend: "P2 · S3" en Centro,
     ficha y lista; `PacienteSerializer.proceso_actual`. PR #71 queda superado (cerrar).
     WhatsApp desde Continuidad: iteración separada (hueco `contacto` en el detalle).
   - Dev: el preview corre contra una base demo aislada (`DATABASE_URL` → sqlite en el
     scratchpad); `db.sqlite3` local tiene 3 migraciones pendientes (0033, 0034, usuarios 0012).
31. ✓ Agendamiento público como página del sitio (rama `feature/agendar-pagina-sitio`,
   2026-09-11). `/agendar/<token>` lleva ahora el **marco de conversemos.itaca.com.pe**:
   cabecera fija con el logo y el menú real del sitio (Quienes Somos · Psicólogos · Terapias
   Online · Preguntas · Blog; abren en pestaña nueva para no perder una reserva a medias), pie
   claro con sedes, contacto, redes y los test, y los botones flotantes de WhatsApp del sitio, uno
   por sede (`agendaWhatsapp`, con el teléfono de `AGENDA_SEDES`). Las **Preguntas frecuentes** del sitio (texto del equipo, `agendaFaq`)
   van como `<details>`: las que frenan en cada paso, al pie de ese paso (`AgendaDudas`); la
   lista completa, solo en la portada. El precio de la primera consulta sale del catálogo real
   (`Servicio` reservable cuyo nombre contenga consulta/inicial/primera); si no hay, S/ 50 (el
   del sitio). Portada con tres señas de confianza (colegiados, confidencial, 30-45 min) y sin
   logo propio (la cabecera ya lleva la marca). El endpoint público expone `colegiatura` y se
   muestra como "C.Ps.P. N°" en tarjeta y perfil. Título de pestaña e idioma propios. Todo en
   `frontend/src/App.jsx` (`AGENDA_SITIO`, `AgendaTop`, `AgendaPie`, `AgendaWa`);
   `#root:has(.ag)` anula el padding del panel para que cabecera y pie corran de borde a borde.
   - **Acción del usuario**: apuntar los botones "Pide tu terapia" / "Pedir tu cita" del
     WordPress al enlace de Railway, y **renovar el certificado SSL del sitio** (venció el
     6 ene 2026: el navegador marca "No seguro" y nadie deja su DNI ahí). RESUELTO (15 sep 2026): el sitio derivaba
     todo a un celular personal, que terminaba repartiendo los leads a mano. Ahora cada
     enlace lleva al WhatsApp de su sede y la FAQ da esos mismos dos números.
   - Verificado: `manage.py check`, 11/11 tests de `pacientes` (nuevo `AgendamientoPublicoTests`),
     build de Vite, ESLint sin errores y recorrido completo con Playwright (escritorio y móvil)
     contra una base demo aislada en el scratchpad.

32. ⏳ Biblioteca de imágenes del compositor de WhatsApp (rama
   `feature/contactabilidad-continuidad`, 2026-09-11, SIN desplegar). Coordinación puede
   adjuntar varias imágenes reales al mensaje del Centro de Continuidad, subir piezas
   nuevas y poner emojis sin depender del teclado del sistema.
   - **Modelo** `mensajes.Material` (migración 0010): nombre, archivo, categoría (8),
     sede, mime REAL, tamaño, ancho/alto, hash SHA-256, subido_por, activo. Es la
     biblioteca **compartible** de la clínica (ubicaciones, horarios, tarifas, medios de
     pago, sesiones online, políticas, material para pacientes, otros) y está **separada
     a propósito** de `pacientes.Adjunto`, que es material clínico de UN paciente: así una
     ecografía no puede aparecer nunca en el selector del compositor. Dedupe por
     `UniqueConstraint(clinica, hash)` sobre `activo=True`; retirar es baja lógica y
     volver a subir la misma pieza la reactiva. `Mensaje` += `grupo_envio` (UUID),
     `orden`, `material`, y el estado nuevo `pendiente`.
   - **Almacenamiento**: `FileField` en `MEDIA_ROOT` (el volumen persistente de Railway
     que ya usan los adjuntos), ruta `material/clinica_<id>/<uuid>.<ext>` — el nombre del
     archivo del usuario NO decide la ruta. Se sirve solo por
     `GET /api/materiales/<id>/imagen/`, autenticado y con scope de clínica; **no** hay
     URL pública de media. Sin dependencias nuevas: el tipo real y las dimensiones se
     leen de la **cabecera binaria** (`mensajes/materiales.py::inspeccionar`, firmas de
     PNG/JPEG/WEBP), así que un PDF renombrado a `.png` se rechaza y no hace falta Pillow.
     Límites de esta versión: **2 MB** (provisional, falta medir EasyPanel), 4000 px por
     lado, 10 imágenes por comunicación.
   - **Envío** (`mensajes/services.py::enviar_comunicacion`): Evolution 2.3.7 **no tiene
     álbum** —sus 13 rutas de envío mandan un archivo por petición—, así que una imagen
     sola viaja con el texto como `caption` (un mensaje, como lo mandaría una persona) y
     varias van como N `sendMedia` sin pie + el texto al final, con ~1 s entre partes para
     conservar el orden. `mensajes/evolution.py::enviar_media` manda el archivo en
     **base64**: una URL obligaría a publicar media sin sesión. Las imágenes salen
     siempre por Evolution, nunca por Meta (formato distinto; el paciente recibiría la
     comunicación desde dos números). Un mensaje sin imágenes conserva intacta la cascada
     Meta → Evolution de siempre.
   - **Fallo parcial**: las partes se crean ANTES de enviar (estado `pendiente`), el
     despacho **se detiene en el primer fallo** y no hay reintento automático.
     `external_message_id` es la prueba de que esa parte salió —lo pone WhatsApp— y una
     parte que lo tiene **nunca** se reenvía: eso es lo que impide que "Reintentar lo que
     falta" (`POST …/whatsapp/reintentar/`) le duplique una imagen al paciente.
   - **Frontend** (`App.jsx`): biblioteca con multiselección por checkbox y numeración,
     buscador, filtros por categoría, contador, "Agregar N imágenes", subida real
     (validada también en el navegador), lista de adjuntos reordenable con ↑ ↓, quitar
     individual, y preview de WhatsApp con **todas** las piezas en su orden. **Selector
     de emojis propio** (`SelectorEmoji`): ~250 emojis Unicode curados con nombres en
     español (busca "corazon" sin tilde), 9 categorías + Recientes en `localStorage`
     (máx. 20, solo los caracteres — ningún dato del paciente), inserción en la posición
     del cursor conservando el foco. Sin librería: emoji-mart y similares pesan cientos
     de kB y solo buscan en inglés. El popover va en su propio portal con posición fija
     (las columnas del compositor tienen overflow y lo recortarían) y en móvil se abre
     como panel inferior. El verde de WhatsApp sigue confinado al preview.
   - Verificado: 36 tests nuevos (`mensajes/tests_materiales.py`), `manage.py check`,
     build de Vite y ESLint limpio en el bloque del compositor. **Sin desplegar y sin
     ningún envío real.** `vite.config.js` acepta `VITE_API_TARGET` para levantar una
     segunda instancia sin tocar la que ya corre.
   - **Pendiente**: medir qué tamaño de payload aguanta EasyPanel/Railway antes de subir
     el límite de 2 MB; la prueba manual controlada con la línea `vibery`.
33. ✓ El sitio web vive en la misma app (rama `feature/sitio-publico`, 2026-09-12).
   Las cinco páginas principales de conversemos.itaca.com.pe se rehicieron dentro del
   frontend que ya corre en Railway, con el marco y el sistema visual del agendamiento:
   `/` · `/quienes-somos` · `/psicologos` · `/terapias-online` · `/preguntas`. El catch-all
   de `config/urls.py` ya las servía; `main.jsx` las enruta con `esRutaSitio()`.
   - **Backend**: `core/sitio.py` = `GET /api/sitio/` (público, sin token en la URL) con
     clínica, `token_agenda`, servicios reservables y equipo; y `GET /api/sitio/foto/<pk>/`
     para las fotos (Django sigue sin publicar /media · Ley 29733). La clínica sale de
     `SITIO_CLINICA_TOKEN`; con una sola clínica activa se resuelve sola y **con varias
     responde 404 en vez de adivinar** (aislamiento). Tests: `core/tests_sitio.py` (6).
   - **Frontend**: `Sitio.jsx` (páginas + estilos `.st-*`), `rutas.js` (menú, navegación sin
     recarga con `history.pushState`, `propsEnlace`) y `sitio-textos.js` (los textos del
     equipo, copiados del WordPress; solo se corrigieron tildes). En `App.jsx` el marco
     (`AgendaTop`/`AgendaPie`/`AgendaWa`/`agendaFaq`/`AGENDA_CSS`) pasó a exportarse y el
     menú dejó de apuntar al WordPress: ahora navega por dentro, marca la página actual y
     suma el botón "Pide tu cita". Blog y los tres test siguen en WordPress, marcados como
     enlaces externos (no se migran todavía).
   - **La página de Psicólogos sale de la base**: 15 activos con foto, colegiatura, enfoque
     y frase, con filtro por sede. La web vieja mostraba 7, tres de ellos ya inactivos
     (Katia Briones, Verónica León, Pamela Revilla). Los precios de "Terapias online" y el
     de la primera consulta en el FAQ salen del catálogo (`Servicio` reservable).
   - **Datos NO publicados a propósito**: las cifras de la portada del WordPress ("300+
     vidas cambiadas", "2,000+ personas", "21,600+ horas conversando") contradicen la base
     (2.833 atenciones registradas), así que quedaron fuera; sí se conservaron las frases
     que las acompañaban. El teléfono de Piura del pie del WordPress (947709108) **no
     coincide** con el del sistema (983 292 173): se usó el del sistema.
   - Verificado con Playwright (escritorio 1366 y móvil 390, las 5 páginas): sin errores de
     consola, sin peticiones fallidas, sin enlaces rotos, un solo `<h1>` por página, foco
     visible, menú navegable en móvil y sin desborde horizontal. `manage.py check` limpio,
     46 tests (sitio + pacientes) OK, build de Vite OK y ESLint sin avisos nuevos en los
     archivos nuevos (App.jsx suma 3 advertencias de `react-refresh`, solo de desarrollo).
   - **Pendiente (acción del usuario)**: apuntar el dominio conversemos.itaca.com.pe a
     Railway (y renovar su certificado, vencido el 6 ene 2026), decidir si se migran el blog
     (10 entradas, la última de enero de 2022) y los tres test psicológicos, y confirmar qué
     número de Piura es el vigente.
34. ✓ `/gestion`: el sistema interno recuperó su puerta (2026-09-13, corrección).
   Al publicar el sitio (ítem 33), `/` pasó a servir la portada pública y el panel
   interno —que se abría justo ahí— quedó SIN ruta: seguía montado como último
   recurso, pero el equipo no podía entrar. Ahora `frontend/src/main.jsx` enruta en
   este orden: `/consentimiento/<token>` · `/agendar/<token>` · **`/gestion[/...]`
   → `<App />`** · rutas del sitio · resto → `<App />`. `esRutaSitio()` consulta
   primero `esRutaReservada()` (`/gestion`, `/agendar`, `/consentimiento`, `/api`,
   `/admin`, `/static`, `/media`), así que añadir una página al sitio no puede
   volver a tapar el panel. El catch-all de Django ya servía la SPA en `/gestion`:
   no hizo falta tocar `config/urls.py`. El pie de la web lleva un enlace discreto
   "Acceso interno" (`/gestion`, navegación real, no del SPA).
   - Verificado local (16/16): `/` y `/quienes-somos` públicas; `/gestion` sin sesión
     muestra el login de siempre; login real con cuenta existente entra al sistema;
     Agenda, Pacientes y Continuidad accesibles; recargar `/gestion` y `/gestion/x`
     no da 404; cerrar sesión deja el login en `/gestion`; `/agendar/<token>` y
     `/consentimiento/<token>` siguen; `/api/` responde JSON y `/admin/` HTML de
     Django (React no los intercepta).
   - **Bug aparte encontrado y corregido**: `GET /api/hoy/` devolvía 500 para el rol
     médico (`NameError: name 'ficha' is not defined` en `core/gerencia.py`, bloque
     de NPS del commit 9fba2fb). Se reusa `continuidad_mod.pacientes_del_rol(...)`,
     que es la regla de alcance del resto de la vista, en vez de repetirla a mano.
     Sin cambios de modelo ni de permisos. 258 tests de core+pacientes en verde.
35. ⏳ Dirección visual del sitio · FASE 1 (rama `feature/sitio-diseno`, 2026-09-13,
   SIN desplegar). El contenido ya estaba, pero el resultado se leía como un wireframe
   técnico. Esta fase rehace SOLO cabecera, pie y "Quiénes somos"; las otras cuatro
   páginas siguen intactas (clases `st-*`) hasta que se apruebe el sistema.
   - **Paleta** (tokens `--t-*` en `.ag`, junto a los del agendamiento, que no se
     tocan): turquesa profundo #0A7D92, petróleo #085E71, turquesa vivo #00B8D8 solo
     como superficie, celeste #D7F4FA, fondo clínico #F4FBFD, crema #F7F5F1, texto
     #26373A y #5C6E71. **Cuatro valores se oscurecieron respecto a lo pedido para
     cumplir AA**: el secundario #66777A daba 4.47 sobre el clínico; el turquesa como
     texto sobre celeste, 4.18 (ahí se usa `--t-sobre-suave`); los números 01/02/03 en
     turquesa vivo, 2.37; los rótulos del pie al 55% de blanco, 3.41.
   - **Tipografía**: Inter para interfaz y lectura; **Fraunces** (serif humana) solo en
     titulares y frases emocionales. H1 máx. 56px, lectura 17-18.5px a 63 caracteres.
   - **Cabecera** (`AgendaTop`): una fila de 80px, logo 44px, menú a la derecha con
     "Inicio", CTA "Pide tu cita" al extremo que nunca se envuelve; página actual como
     pastilla celeste. Bajo 1000px la navegación pasa a un panel con botón hamburguesa
     accesible (`aria-expanded`/`aria-controls`, cierra con Escape) y el CTA se queda.
   - **Pie** (`AgendaPie`): franja petróleo con el logo blanco de la marca
     (`public/sitio/itaca-logo-blanco.png`), columnas sedes/navegación/contacto y redes
     discretas. Conserva el enlace "Acceso interno" del ítem 34, adaptado al fondo.
   - **Quiénes somos** (`qs-*` en `Sitio.jsx` + `sitio-textos.js`): hero 52/48 con la
     foto REAL del equipo, servicios 3×2 con iconos lineales, las tres áreas como
     pilares numerados, modelo integrativo con foto real y cita destacada, franja
     turquesa de principios y cierre con las sedes en segundo plano. Las fotos salen
     del propio WordPress (`somos-3` y `000011`), no de IA ni de bancos.
   - **Ojo**: las descripciones de una línea de los seis servicios NO existían en el
     WordPress; se redactaron describiendo qué es cada uno (duración y modalidad salen
     de sus FAQ; la grupal, de su Círculo de Aliados), sin prometer resultados.
   - Verificado: cabecera de 80px con el CTA en su fila, nada tapado al cargar, saltar a
     un título lo deja visible (`scroll-margin-top`), sin desborde en 390px, menú móvil
     accesible, consola limpia, build de Vite y ESLint sin avisos.
   - **FASE 2 (aprobada y aplicada)**: el sistema se replicó a las cuatro páginas
     restantes y el prefijo pasó de `qs-` a **`sw-`** (sitio web), porque ya no es "el
     de Quiénes somos". El tema se aplica a todo el sitio (`.ag sw-sitio sw-tema`) y el
     **sistema viejo `st-*` se eliminó entero** (CSS y helpers `Foto`/`BotonReservar`):
     0 referencias restantes, nada de CSS muerto en el bundle.
     · **Inicio**: hero con mosaico de 9 caras reales del equipo, proceso en cuatro
       pasos numerados en serif, tira de psicólogos sobre celeste, testimonios en dos
       columnas y dudas clave.
     · **Psicólogos**: ficha con foto de 76px, colegiatura destacada, frase en serif,
       enfoque recortado a 3 líneas y "Ver perfil completo" plegable.
     · **Terapias online**: paquetes con el precio real en serif, temas y públicos como
       pastillas, Círculo de Aliados en tarjetas y el cierre emocional sobre petróleo.
     · **Preguntas**: hero propio y acordeón a 17px (se reestiliza `.ag-duda` solo
       dentro de `.sw-tema`, así que el agendamiento no cambia).
   - Verificado en las 5 páginas × escritorio y móvil: 0 errores de consola, 0 peticiones
     fallidas, 0 enlaces rotos, un `<h1>` por página, menú móvil accesible y sin desborde.
   - **Pendiente**: publicar (sin desplegar todavía).
36. ✓ Navegación: una sola fuente de verdad para las rutas (2026-09-13).
   Cada componente escribía sus destinos a mano y el enlace de reservas dependía del
   token que devolvía la API, así que convivían `/preguntas` y `/preguntas-frecuentes`,
   tokens distintos según el entorno y enlaces al WordPress.
   - **`SITE_ROUTES`** (en `frontend/src/rutas.js`, `Object.freeze`) es ahora el único
     lugar donde vive un destino interno: inicio · quienesSomos · psicologos · terapias ·
     preguntas · **agendar** (con el token público `PmFaG9KH…`, fijo: si se regenera
     desde Captación hay que actualizarlo AHÍ) · gestion. `MENU_SITIO`, `RUTAS_SITIO`,
     los títulos, la cabecera, el pie, el FAQ y todos los CTA salen de ella.
   - **La canónica de preguntas pasó a `/preguntas-frecuentes`**; `/preguntas` queda como
     **alias** (`ALIAS_RUTAS`) porque era la dirección ya publicada. `rutaCanonica()`
     resuelve alias y barra final, y la URL se normaliza con `replaceState` al entrar.
   - **Blog y los tres test del WordPress quedaron OCULTOS** (`MOSTRAR_WORDPRESS = false`):
     el certificado de conversemos.itaca.com.pe venció el 6 ene 2026 y enviar visitantes
     ahí es mandarlos a una advertencia de sitio no seguro. Se reactivan poniendo esa
     constante en true cuando se renueve el certificado.
   - Los externos (Instagram, Facebook, WhatsApp) llevan `rel="noopener noreferrer"`;
     correo y teléfonos conservan `mailto:`/`tel:`. Ningún enlace interno abre pestaña.
   - **Auditoría automática**: `scratchpad/auditoria_navegacion.py` inventaría cada enlace
     visible de las 6 páginas (34 distintos), marca destinos inertes/WordPress/tokens
     ajenos/rutas desconocidas, hace clic en 13 CTA comprobando el destino contra
     SITE_ROUTES, y repite la navegación en móvil. Resultado: sin errores.
   - Verificado: `manage.py check`, 46 tests (core.tests_sitio + pacientes), build de Vite,
     ESLint sin avisos nuevos (App.jsx bajó de 106 a 105 al quitar una prop sin uso).
37. ✓ Correcciones de Gabriela + fotos reales del consultorio (2026-09-13).
   Revisión de la dueña por WhatsApp sobre el sitio ya publicado:
   - «Que diga solo terapia, no "online"» → la etiqueta del menú es **"Terapias"**
     (la ruta sigue siendo `/terapias-online`, que ya estaba publicada) y el título de
     pestaña pasa a "Terapias · Ítaca Conversemos".
   - «Esos no funcionan, mejor quitarlos» (los 3 test) y «Blog también quitarlo» →
     confirmado: ya estaban ocultos desde el ítem 36 por el certificado vencido.
   - «¿Esa sección también puede salir arriba? En lugar de blog, esta de agendar» →
     el menú estrena **"Agendar"** en el hueco del Blog, apuntando a `SITE_ROUTES.agendar`.
   - `propsEnlace()` ahora detecta las rutas reservadas (`/agendar`, `/gestion`…) y
     devuelve navegación REAL en vez de `pushState`: son otras aplicaciones dentro del
     mismo dominio y un pushState no las montaría.
   - **Seis fotos del consultorio** enviadas por la clínica (`frontend/public/sitio/`,
     1600px, ~100-175 KB): `equipo` (sesión en escritorio) en el hero de Quiénes somos,
     `consulta` (sesión con la pizarra de emociones) en el modelo integrativo, `pareja`
     en Terapias, `sesion` en el hero de Psicólogos, `acompanamiento` en el proceso de
     Inicio y `bienvenida` (recibiendo en la puerta) en el cierre común. Reemplazan a las
     que se habían tomado del WordPress. Nada generado con IA.
   - Verificado: auditoría de navegación **14/14 clics** (incluido el nuevo "Agendar"),
     5 páginas × escritorio y móvil sin errores ni enlaces rotos, las 6 fotos cargan.
     El capturador de pruebas ahora recorre la página antes de la captura: con
     `loading="lazy"` las imágenes salían en blanco y la captura mentía.
38. ✓ Pacientes duplicados: prevención + consolidación (rama
   `feat/consolidar-pacientes-duplicados`, 2026-09-16). Salió de una auditoría
   read-only sobre producción: **65 grupos de confianza ALTA, 76 fichas de más sobre
   1.646 pacientes**, 34 personas con su próxima cita en la ficha que Coordinación no
   mira, 16 con las sesiones repartidas, 10 con el cierre de bloque inconsistente y
   **3 alertas de Continuidad objetivamente innecesarias** (la cita ya existía en la
   otra ficha). La causa dominante NO fue el emparejamiento automático: de las 76,
   **57 tenían el mismo nombre y teléfono que una ficha existente** y 48 nacieron al
   crear la cita desde la Agenda → el culpable era `PacienteViewSet.perform_create`,
   un `save()` sin comprobación. (El hueco de `tutor_telefono` es real pero solo
   afecta a 1 ficha hoy: es riesgo prospectivo de infantojuvenil, no el problema.)
   - **Prevención**: `PacienteViewSet.create` busca coincidencias antes de guardar y
     devuelve **409** con `posibles_duplicados` (contacto enmascarado). No bloquea:
     con `confirmar_nuevo` se crea igual, porque los homónimos existen. En el front,
     modal `AvisoDuplicado` con "nuevo registro" vs "ya existe" y dos salidas: **usar
     la ficha existente** o **crear persona distinta**.
   - **Detector** `pacientes/duplicados.py` (solo lee, nunca fusiona). ALTA = mismo
     documento, o mismo nombre + teléfono válido (≥9 dígitos) + sede compatible, sin
     contradicciones. MEDIA = sugerente sin identificador fuerte (incluye el teléfono
     del tutor como PISTA, jamás como identidad). BAJA = solo el nombre se parece.
     **Descarta**: documentos válidos distintos, nacimientos distintos, familiares con
     el mismo celular y nombre distinto, y expedientes de pareja ("A y B").
   - **Motor** `pacientes/fusion.py`: `analizar_fusion` (dry-run 100 % read-only) y
     `fusionar_pacientes` (atómico). Las relaciones salen de
     `Paciente._meta.get_fields()`, no de una lista a mano —así fue como el viejo
     `fusionar_por_telefono` se quedó sin `GestionContinuidad` y reventaba con
     ProtectedError—. **Fail-safe**: si un modelo tiene una restricción de unicidad
     sobre `paciente` y no tiene manejo propio, la fusión **se detiene antes de tocar
     nada**. Eso descubrió `SeguimientoSesion` (`uniq_seg_paciente_semana`), que nadie
     había previsto. Manejo propio: GestionContinuidad (cierra la gestión repetida
     conservando su historial), SeguimientoSesion (une la semana quedándose con la
     sesión más alta) y RevisionDuplicado (se limpia).
   - **Atención vigente**: `especialidad_habitual` NO se hereda "solo si falta": manda
     la ficha con actividad más reciente (última cita), porque el dato viejo no es un
     conflicto sino una etapa superada —"Consulta psicológica" en la antigua vs
     "Terapia individual" en la reciente—. Si ninguna tiene citas y los valores
     difieren, **no se adivina**: bloquea pidiendo revisión. La regla NO se extiende a
     documento, nacimiento ni teléfono: ahí dos valores distintos son un conflicto de
     identidad. `creado_en` no sirve de desempate (los importadores lo reescribieron).
   - Orden **no negociable**: resolver choques → mover todo → completar la ficha
     maestra → `gestion_continuidad.reconciliar()` (el `update()` no dispara señales)
     → verificar que NADA sigue apuntando al secundario → dejar constancia → borrar.
     Todo en `transaction.atomic()`. El texto clínico de las dos fichas se **une**, no
     se descarta. **Bloquean**: clínicas distintas, documentos válidos distintos,
     nacimientos distintos; la sede distinta exige `aceptar_sede_distinta` explícito.
   - **Auditoría sin conservar el duplicado**: `RegistroFusionPaciente` (ids, nombres,
     usuario, motivo, relaciones movidas, conflictos, continuidad antes/después). No
     es un Paciente y no entra en ningún conteo. `RevisionDuplicado` guarda los "no son
     la misma persona" para no reofrecerlos. Migración 0037.
   - **Refactor clave**: `core/continuidad.py` expone `evaluar_paciente(...)`, extraído
     de `cola_de_continuidad`. El dry-run proyecta la continuidad llamando a ESA misma
     función con la historia unida — no reimplementa la regla, así que lo que muestra
     la vista previa es lo que se verá después.
   - **Permisos**: `ROLES_REVISAN_DUPLICADOS` = admin + asistente (ver, comparar,
     descartar); `ROLES_FUSIONAN_PACIENTES` = **solo admin** (consolidar elimina una
     ficha). El psicólogo y la analista quedan fuera. Cada fusión es individual y con
     confirmación explícita: **no existe "fusionar todos"**.
   - Frontend `Duplicados.jsx`: pestañas Alta/Revisar/Descartados, tarjeta por grupo
     con el impacto en Continuidad, comparación lado a lado, elección explícita del
     principal, dry-run en pantalla (campos, relaciones, continuidad antes/después) y
     confirmación que dice qué id sobrevive y cuál desaparece.
   - Verificado: **60 tests nuevos** (`pacientes/tests_duplicados.py`), 669 de la suite
     completa, `manage.py check`, `makemigrations --check`, build de Vite y ESLint
     limpio en el archivo nuevo. Desplegado en Railway con la migración aplicada.
   - **Primera consolidación real ejecutada el 2026-09-16**, sobre el único caso que
     se había validado con dry-run y con autorización explícita de gerencia: 12
     relaciones movidas (4 citas, 5 mensajes, 1 cobro, 1 lead, 1 gestión de
     continuidad), **cero filas huérfanas**, ficha secundaria eliminada y
     `RegistroFusionPaciente` #1 como constancia. Verificado al día siguiente: una
     sola ficha, **una sola evaluación en la cola** y el detector ya no propone ese
     par. La `especialidad_habitual` quedó en la de la ficha reciente, que es lo que
     la regla de atención vigente venía a arreglar.
   - **El resto del histórico sigue SIN tocar** (a set. 2026: ~51 grupos ALTA, 31 en
     Revisar, 19 descartados). Se limpia **caso por caso**, con dry-run y aprobación
     de gerencia por cada par: no hay ni habrá limpieza masiva.
39. ✓ De dónde vino la reserva (PR #95, 2026-09-17, **desplegado**). La auditoría del flujo público confirmó que la reserva ya crea y enlaza
   Lead + Cita + Paciente, pero que **toda reserva entra con `fuente = WEB`**: una
   consulta traída por un anuncio pagado y otra que llegó buscando en Google son la
   misma fila. No se puede saber qué campaña trae consultas que inician proceso.
   - **`leads/atribucion.py`**: limpia lo que llega del navegador (lista blanca de 10
     claves: las 5 `utm_*`, `gclid`, `fbclid`, `referrer`, `landing`, `variante`),
     recorta longitudes y descarta lo vacío. `es_pagado()` marca `es_pauta` según
     **lo declarado**: si el enlace trae `utm_medium`, decide ese y nada más.
   - **Corrección el mismo día (PR #96)**: la primera versión daba `fbclid` por prueba
     de pauta y estaba mal. Meta lo cuelga de TODO clic que sale de Instagram o
     Facebook, **también de los orgánicos**, así que el enlace de la bio —que no cuesta
     nada— entraba como publicidad pagada, y encima sin campaña ni canal (un clic
     orgánico no trae `utm_source`): el indicador "% de pauta" de Gerencia se inflaba
     con leads que nadie pagó. Ahora, sin medio declarado, el único que prueba el pago
     es **`gclid`**, que Google Ads añade solo a sus anuncios. `fbclid` se sigue
     guardando en `origen_detalle` —sirve para cruzar con el reporte de Meta—, pero
     ya no decide nada. Detectado al preparar los enlaces etiquetados, no por un fallo.
   - **Reutiliza lo que ya existe**: `campania`, `es_pauta` y `subfuente` son los campos
     que el reporte de captación (`leads/reporte.py`) YA lee; se llenan desde aquí en
     vez de abrir un circuito paralelo. `Lead` suma solo `origen_canal`, `origen_medio`,
     `origen_contenido` y `origen_detalle` (JSON para lo que no tiene columna).
     Migración **0017, aditiva**.
   - **Frontend** `origen.js`: recuerda el origen en `sessionStorage` al entrar (la
     reserva ocurre páginas después, cuando la URL ya no lleva los parámetros) y lo
     envía en el POST. **El primer origen manda**: si alguien llega por un anuncio, se
     va a leer las preguntas y vuelve, la consulta sigue siendo del anuncio. Dura solo
     la visita; no sigue a nadie entre sesiones y no guarda dato personal alguno.
   - **La reserva nunca depende de esto**: sin origen, con origen corrupto o con el
     almacenamiento bloqueado, la consulta entra igual (3 tests lo fijan).
   - Verificado: 12 tests nuevos (`leads/tests_atribucion.py`), **220 de leads+pacientes
     sin regresión**, `manage.py check`, `makemigrations --check` limpio, build de Vite,
     ESLint sin avisos, y 7/7 comprobaciones en navegador real (el origen sobrevive a
     navegar entre páginas y al llegar al agendamiento).
   - **Pendiente**: que los enlaces de campaña lleven los parámetros (si no, no hay nada
     que capturar), y mover el dominio a Railway antes de invertir en SEO.

40. ✓ SEO técnico: lo que ven Google y WhatsApp (PR #97, 2026-09-17). El sitio
   aparecía en Google con el **testimonio de una paciente como descripción** (Google
   toma el primer texto que encuentra cuando la página no declara ninguna) y
   cualquier enlace compartido por WhatsApp se veía como "Itaca Conversemos ·
   Gestión", el título del panel interno, sin imagen.
   - **La causa**: la app es una sola página de React. El servidor entregaba siempre
     el mismo `index.html` —`<html lang="en">`, título del sistema, sin descripción—
     y el contenido lo armaba el navegador. **WhatsApp y Facebook no ejecutan
     JavaScript**: el preview sale del HTML crudo. Google sí lo ejecuta, pero indexa
     primero lo que viene en el HTML.
   - **`core/seo.py`**: `SpaView` reemplaza al `TemplateView` genérico y escribe en el
     HTML el título, la descripción, la canónica y las etiquetas Open Graph **según la
     ruta pedida**. `/gestion`, `/agendar/<token>` y `/consentimiento/<token>` salen
     con `noindex` y sin preview: llevan token o son el panel interno.
   - **`/robots.txt` y `/sitemap.xml` existían solo de nombre**: caían en el comodín de
     `config/urls.py` y devolvían la app de React (`text/html`). Ahora son vistas
     propias registradas ANTES del comodín.
   - **Una sola fuente**: los textos viven en `frontend/src/paginas.json`, que leen
     Django (para el HTML) y React (para actualizar el título al navegar sin
     recargar). El bloque `TITULOS` de `Sitio.jsx` se eliminó: en dos sitios habrían
     acabado diciendo cosas distintas.
   - **Las descripciones salen de `sitio-textos.js`** (lo que escribió el equipo), de
     138 a 156 caracteres. No prometen resultados ni citan cifras que la base no
     sostenga —misma regla del ítem 33—.
   - **Ojo con la ruta de la imagen del preview**: escrita como `/sitio/foto.jpg` el
     comodín devuelve el HTML del SPA y WhatsApp muestra el enlace **sin foto**. Va
     por `static()`, que resuelve el prefijo real (`/static/sitio/foto.jpg`).
   - **`SITIO_URL_PUBLICA`** (settings, vacía por defecto): con el sitio en Railway las
     direcciones absolutas salen del host de la visita; en cuanto
     conversemos.itaca.com.pe apunte aquí hay que **fijarla**, o la misma página se
     anuncia con dos direcciones y el buscador reparte la reputación.
   - Vite conserva intactas las etiquetas `{{ }}` y `{% if %}` del `index.html` al
     construir (verificado sobre el `dist` real). En desarrollo Vite sirve el archivo
     tal cual y las llaves se ven literales un instante; React corrige el título al
     montar.
   - Verificado: **15 tests nuevos** (`core/tests_seo.py`; el CI corre Django ANTES de
     construir el frontend, así que añaden `frontend/` a los directorios de
     plantillas para usar el archivo fuente), suite de core+leads+pacientes sin
     regresión, build de Vite, ESLint limpio y 8/8 comprobaciones en navegador real
     (el sitio monta, el título y la descripción siguen a la navegación, sin errores
     de consola).
   - **Pendiente**: registrar el sitio en Google Search Console y pedir reindexación
     (lo desbloquea el dominio); el subdominio `itacaconversemos.site.agendapro.com`
     sigue rankeando y **redirige a la portada de AgendaPro**, no a Ítaca: decisión
     de negocio pendiente.

41. ⏳ Embudo web: cuánta gente llega y dónde se pierde (rama `feat/embudo-web`,
   2026-09-17, SIN desplegar). El ítem 39 dejó saber **de dónde viene quien
   reserva**. Faltaba la otra mitad: cuántos llegaron y NO reservaron. Sin eso,
   una campaña con 100 visitas y 1 reserva se ve idéntica a otra con 10 y 1, y
   la segunda es diez veces mejor.
   - **`leads.EventoSitio`** (migración 0018, aditiva): tipo del paso, página,
     canal/medio/campaña —los MISMOS ejes que el `Lead`, para poder cruzarlos sin
     traducir nada— y un `sesion` efímero. El recorrido medido es
     **vio → hizo clic en reservar → abrió el formulario → reservó**; el cuarto
     paso NO se guarda aquí: ya está en `Lead`, y duplicarlo daría dos cifras que
     con el tiempo dejarían de coincidir.
   - **Privacidad como requisito, no como añadido**: sin IP, sin user-agent, sin
     cookies, sin fingerprinting, sin servicios externos (nada de GA ni Pixel), y
     **sin relación con el `Lead`**. Es una web de psicología: que alguien mirara
     "terapia de pareja" o "duelo" es dato sensible en cuanto se puede atar a un
     nombre. Se pierde el recorrido individual a propósito. `sesion` es un número
     al azar que vive en la pestaña y muere al cerrarla; solo evita contar cinco
     veces a quien mira cinco páginas. Un test lo fija: `EventoSitio` no puede
     tener campos ip/user_agent/lead/paciente/telefono/email/nombre.
   - **Dónde se engancha**: la visita en el efecto de ruta de `Sitio.jsx`; el clic
     en **`propsEnlace()`** (`rutas.js`), por donde pasan TODOS los enlaces —así
     un botón nuevo queda medido sin acordarse de nada—; y "abrió el formulario"
     en `main.jsx`, **no** dentro de `App.jsx`, para no tocar ese archivo por una
     medición. El envío usa `navigator.sendBeacon`: un `fetch` normal se cancela a
     medias cuando la página ya se está yendo, que es justo el caso del clic.
   - **Dos fallos que solo aparecieron al probar**, y valen como aviso:
     · El `ordering` del modelo se colaba en el `distinct()` y, como cada visita
       tiene su hora, las cuatro páginas de una persona contaban como cuatro
       personas: **toda tasa de conversión salía dividida por las páginas vistas**.
       Se arregla con un `order_by()` vacío antes del `values(...).distinct()`.
     · `PASOS` ya existía en `Sitio.jsx` (los cuatro pasos del proceso de terapia,
       de `sitio-textos.js`); los del embudo van con alias.
   - **En Gerencia** la clave es **`embudo_web`**, no `embudo`: dentro de
     `diagnostico` ya hay un `embudo`, que es el de estados del lead
     (nuevo → ganado). Son dos lecturas distintas y confundirlas sería caro.
     El bloque **no se acota por sede**: quien visita la web todavía no eligió
     sede —eso pasa en el formulario—, así que repartir las visitas entre Lima y
     Piura sería inventar un dato. Mientras no haya visitas medidas, la pantalla
     **lo dice** en vez de mostrar un 0 % que sería mentira.
   - Los rastreadores (Google, Meta, monitores) se descartan por user-agent: sí
     ejecutan JavaScript y sin filtro inflarían las visitas, haciendo que cada
     campaña pareciera convertir peor de lo que convierte. Ritmo máximo del
     endpoint público: `embudo` a 120/min.
   - Verificado: **12 tests nuevos** (`leads/tests_embudo.py`), suite de
     core+leads+pacientes sin regresión, build de Vite, ESLint sin avisos nuevos
     (App.jsx queda igual que en `main`, comparado regla por regla), y el circuito
     completo en navegador real contra una base aislada: **8/8**, con los eventos
     comprobados EN LA BASE y no en el tráfico —`sendBeacon` manda el cuerpo como
     Blob y la herramienta lo ve vacío aunque el dato haya llegado bien—.
   - **Pendiente**: desplegar; después, medir los pasos internos del formulario
     (eligió psicólogo, eligió horario) y cruzar con el gasto de `MetricaMensual`
     para tener costo por consulta.
42. ✓ Identidad del menor y teléfono corto (PR #99, 2026-09-17, **desplegado**).
   Dos huecos que la auditoría de duplicados había dejado señalados y que se
   cerraron juntos porque son el mismo error: creer que una persona se identifica
   por *su* número.
   - **`leads/identidad.py`**: `numeros_de(paciente)` devuelve los números por los
     que se llega a esa persona —el suyo **y el de su tutor**— y `ficha_que_calza`
     busca contra ese conjunto. Un menor cuya ficha solo tiene el celular de la
     madre era invisible al reconocimiento: volvía a agendar y nacía una ficha
     nueva. Esto NO relaja la regla de identidad: el teléfono del tutor sigue sin
     identificar por sí solo (hace falta nombre + sede compatible + un único
     candidato); lo que cambia es que ahora **cuenta como vía de contacto**.
   - **`pacientes/agendamiento.py`**: el formulario público aceptaba teléfonos de
     6 dígitos, por debajo del mínimo con el que el sistema reconoce a alguien
     (`identidad.MIN_DIGITOS_TELEFONO` = 9). Resultado: la reserva entraba, pero
     la ficha no se podía emparejar nunca con la que ya existía. Ahora el mínimo
     es el mismo en los dos lados —una sola constante— y el mensaje dice qué
     hace falta: "Necesitamos tu nombre y un celular de 9 dígitos."
   - **Estado del histórico a 17 set. 2026**: **20 consolidaciones ejecutadas**,
     todas con dry-run y autorización caso por caso, cero filas huérfanas;
     13 fichas de prueba eliminadas con `RegistroEliminacion`; la base pasó de
     1.646 a **1.615 pacientes** y de 65 a **31 grupos ALTA**. El lote de "fichas
     realmente vacías" **se agotó**: ya no queda ninguna de bajo riesgo.
   - **Por qué se frenó la limpieza, medido**: de los 31 grupos que quedan, **17
     están bloqueados por registro** (sesiones pasadas sin cerrar o cierres de
     bloque sin DP dentro del propio grupo), 13 piden revisión individual y 1
     necesita a un psicólogo porque las dos fichas tienen atenciones clínicas
     escritas. Es decir: **más de la mitad del trabajo restante no lo desbloquea
     código, lo desbloquea un dato**. Dentro de esos grupos hay 18 sesiones
     pasadas sin cerrar y 6 cierres sin decisión.
   - **El tamaño real de ese hábito, en toda la base**: 676 citas cuya fecha ya
     pasó siguen en agendada/confirmada (320 pacientes, 610 en Piura); solo el
     **1,7 %** de las sesiones asistidas lleva DP, y **95,4 %** de las sesiones de
     cierre (6/12/18/24) no tiene decisión registrada. Eso es lo que sostiene los
     419 casos de la cola y los 243 procesos anteriores sin cierre. La consecuencia
     está probada al revés: en una de las consolidaciones la alerta **se apagó
     sola** en cuanto el DP-09 que ya existía llegó a la ficha consolidada.
   - **La prevención aún no tiene muestra suficiente**: desde el despliegue se han
     creado 5 fichas y ninguna cayó en un grupo duplicado, pero 5 en dos días no
     prueba nada todavía. Lo que sí se comprobó es que los pares con ids casi
     consecutivos que asustan en el triaje son **todos anteriores** al despliegue.
   - **Dato sucio conocido**: existe **una** cita con fecha del año 0006 (un año
     mal tecleado al cargar consultas desde Marketing). Es duplicado exacto de
     otra cita real del mismo paciente, misma hora y mismo servicio, y como quedó
     en "agendada" ensucia cualquier conteo de citas pasadas sin cerrar. Es la
     única fecha imposible de todo el sistema: atenciones, cobros y nacimientos
     están limpios. Pendiente de decisión (cancelarla, no borrarla).
   - **Aviso de entorno**: tras un `git pull` que toque `frontend/`, hay que correr
     `npm install && npm run build` antes de la suite. Los tests de `core/tests_seo`
     leen el `index.html` **construido**; con un `dist` viejo fallan 10 pruebas que
     no tienen nada roto detrás, y el rastro lleva horas en la dirección
     equivocada. `--parallel` además puede tapar el fallo real con un
     `TypeError: cannot pickle 'traceback' object`: ante errores raros, correr en
     serie y redirigir a un log (un `| tail` devuelve el código de salida de
     `tail`, no el de Django).


43. ⏳ La lista de reactivación, priorizada (rama `feat/reactivacion-priorizada`,
   2026-09-17, SIN desplegar). Salió de un análisis **solo lectura sobre
   producción**, no de un pedido de funcionalidad.
   - **Lo que mostró el análisis** (set. 2026, datos reales): de 1.358 personas que
     se sentaron alguna vez, **1.243 no tienen próxima cita**. Pero repartidas por
     antigüedad: 105 de menos de un mes, 127 de 1-3 meses, 208 de 3-6, 536 de
     6-12 y 267 de más de un año. **Las ≈232 de los últimos tres meses son la
     oportunidad real**; los 803 de más de seis meses ya cerraron proceso y
     llamarlos es ruido. Una persona que inicia proceso deja **S/ 251** de media.
   - **El filtro "⏰ Sin próxima sesión" YA existía** (ítem 12) y funcionaba, pero
     entregaba las 1.243 fichas **sin ningún orden**: los recientes quedaban
     mezclados con los de hace años y Coordinación no tenía por dónde empezar.
     No se construyó una pantalla nueva: se hizo usable la que había.
   - **`PacienteSerializer.dias_sin_venir`** (sin migración): días desde la última
     **cita asistida**. `ultima` ya daba la fecha, pero como texto para leer
     ("12 set"): sirve para mirar UNA ficha, no para ordenar mil. Devuelve `None`
     cuando la persona nunca vino —"abandonó" y "todavía no tuvo su primera
     sesión" no son lo mismo, y confundirlos metería gente nueva en la lista de
     reactivación—. Una cita cancelada o con inasistencia **no** cuenta como haber
     venido.
   - **`_ultima_sesion()` cachea el cálculo por paciente**: lo piden dos campos y
     esto se serializa sobre más de mil fichas; sin guardarlo, cada lista
     recorría las citas de cada paciente dos veces para llegar al mismo sitio.
   - **Frontend**: con el filtro activo la lista se **ordena por `dias_sin_venir`
     ascendente** (quien nunca vino, al final), cada fila muestra una etiqueta
     "hace 8 días / hace 4 meses" con color por tramo, y aparece un acotador
     "menos de 3 meses / 3-6 / más de 6". **El corte en 90 días sale de los datos**,
     no de una preferencia.
   - **La lista NO sale del sistema**: son personas en tratamiento psicológico
     (Ley 29733). Nada de exportarla a un archivo, pegarla en un chat ni mandarla
     por WhatsApp; se arma dentro, detrás de login y permisos.
   - Verificado: **7 tests nuevos** (`pacientes/tests_reactivacion.py`), suite de
     pacientes+core sin regresión, build de Vite, ESLint **idéntico a `main`**
     (106 avisos en ambos, comparado archivo contra archivo), y **11/11 en
     navegador real** con datos sintéticos: login, filtro, orden correcto
     (8 días → 25 → 120 → 400 → nunca vino), etiquetas y acotador.
   - **Ojo**: el análisis también destapó que **217 citas importadas de AgendaPro
     están marcadas con `agendado_web=True`** sin serlo. Contaminan cualquier
     reporte que separe la web del resto (incluido el embudo del ítem 41): con
     ellas dentro, la web parecía cancelar 7 veces más que el equipo. Limpiar esa
     marca **escribe en producción** y queda pendiente de autorización.
