"""Panel de Gerencia: tablero ejecutivo con datos REALES del período.

Solo lectura (suma lo que ya existe en agenda, captación y pacientes). Visible
solo para el rol admin (el gerente/dueño). Todo con scope de la clínica activa.
Los ingresos NO se calculan aquí: no hay datos de dinero todavía (van cuando se
construya 'Finanzas reales').
"""
from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Max, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

from core import continuidad as continuidad_mod
from core.permisos import (
    PuedeContactarPacientes,
    PuedeGestionarContinuidad, es_solo_lectura, puede_gestionar_continuidad, ve_finanzas,
)
from core.tenant import get_clinica_actual
from finanzas.models import Cobro, Egreso
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes.models import Atencion, Cita, Paciente


def _rango(periodo):
    hoy = timezone.localdate()
    if periodo == "semana":
        desde = hoy - timedelta(days=hoy.weekday())  # lunes
        return desde, desde + timedelta(days=6), "Esta semana"
    if periodo == "mes":
        desde = hoy.replace(day=1)
        prox = desde.replace(year=desde.year + 1, month=1) if desde.month == 12 else desde.replace(month=desde.month + 1)
        return desde, prox - timedelta(days=1), "Este mes"
    if periodo == "7d":
        return hoy - timedelta(days=6), hoy, "Últimos 7 días"
    if periodo == "30d":
        return hoy - timedelta(days=29), hoy, "Últimos 30 días"
    return hoy, hoy, "Hoy"


def _bounds(desde, hasta):
    ini = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta, time.min)) + timedelta(days=1)
    return ini, fin


def _rango_anterior(periodo, desde, hasta):
    """Rango del período inmediatamente anterior (para comparar tendencias)."""
    if periodo == "mes":
        ant = desde.replace(year=desde.year - 1, month=12) if desde.month == 1 else desde.replace(month=desde.month - 1)
        prox = ant.replace(year=ant.year + 1, month=1) if ant.month == 12 else ant.replace(month=ant.month + 1)
        return ant, prox - timedelta(days=1)
    dias = (hasta - desde).days + 1
    return desde - timedelta(days=dias), desde - timedelta(days=1)


class ClinicaConfigView(APIView):
    """GET/PATCH de los datos de la clínica. Editar solo admin.

    Incluye los textos legales que firma el paciente (consentimiento y políticas):
    devuelve el texto EFECTIVO (el propio si lo cargaron, si no el borrador por
    defecto) y `personalizado_*` indica si ya lo escribieron ellos.
    """

    def _payload(self, c):
        from pacientes.models import texto_consentimiento_default
        from core.gamificacion import config_efectiva as _gamificacion_efectiva
        return {
            "nombre": c.nombre, "ciudad": c.ciudad, "zona_horaria": c.zona_horaria,
            "meta_min_mes": float(c.meta_min_mes or 0),
            "meta_ideal_mes": float(c.meta_ideal_mes or 0),
            "metas_sede": c.metas_sede or {},
            "texto_consentimiento": texto_consentimiento_default(c, "consentimiento"),
            "texto_politicas": texto_consentimiento_default(c, "politicas"),
            "personalizado_consentimiento": bool((c.texto_consentimiento or "").strip()),
            "personalizado_politicas": bool((c.texto_politicas or "").strip()),
            "mof": c.mof or "",
            "pilares": c.pilares or "",
            "mentalidad": c.mentalidad or {},
            "gamificacion": _gamificacion_efectiva(c),
        }

    def get(self, request):
        c = get_clinica_actual()
        if c is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(c))

    def patch(self, request):
        if getattr(request.user, "rol", None) != "admin":
            return Response({"detail": "Solo un administrador puede editar los datos de la clínica."},
                            status=status.HTTP_403_FORBIDDEN)
        c = get_clinica_actual()
        if c is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        campos = ["nombre", "ciudad"]
        nombre = (request.data.get("nombre") or "").strip()
        if nombre:
            c.nombre = nombre[:200]
        if "ciudad" in request.data:
            c.ciudad = (request.data.get("ciudad") or "").strip()[:120]
        for campo in ("meta_min_mes", "meta_ideal_mes"):
            if campo in request.data:
                try:
                    setattr(c, campo, Decimal(str(request.data.get(campo) or 0)))
                    campos.append(campo)
                except (InvalidOperation, ValueError, TypeError):
                    return Response({"detail": f"«{campo}» debe ser un número."},
                                    status=status.HTTP_400_BAD_REQUEST)
        # Metas por sede: {"lima": {"min": .., "ideal": ..}, "piura": {...}}.
        if "metas_sede" in request.data:
            ms = request.data.get("metas_sede") or {}
            limpio = {}
            if isinstance(ms, dict):
                for sede, v in ms.items():
                    if sede in ("lima", "piura") and isinstance(v, dict):
                        try:
                            limpio[sede] = {"min": float(v.get("min") or 0), "ideal": float(v.get("ideal") or 0)}
                        except (ValueError, TypeError):
                            return Response({"detail": "Las metas por sede deben ser números."},
                                            status=status.HTTP_400_BAD_REQUEST)
            c.metas_sede = limpio
            campos.append("metas_sede")
        # Textos legales: guardar vacío = volver al borrador por defecto.
        if "texto_consentimiento" in request.data:
            c.texto_consentimiento = (request.data.get("texto_consentimiento") or "").strip()
            campos.append("texto_consentimiento")
        if "texto_politicas" in request.data:
            c.texto_politicas = (request.data.get("texto_politicas") or "").strip()
            campos.append("texto_politicas")
        for campo in ("mof", "pilares"):
            if campo in request.data:
                setattr(c, campo, (request.data.get(campo) or "").strip())
                campos.append(campo)
        if "mentalidad" in request.data:
            m = request.data.get("mentalidad")
            c.mentalidad = m if isinstance(m, dict) else {}
            campos.append("mentalidad")
        if "gamificacion" in request.data:
            g = request.data.get("gamificacion")
            c.gamificacion = g if isinstance(g, dict) else {}
            campos.append("gamificacion")
        c.save(update_fields=campos)
        return Response(self._payload(c))


class HoyResumenView(APIView):
    """GET /api/hoy/ — números reales del día para el panel de inicio (todos los roles).
    Los ingresos solo se incluyen para el admin."""

    def get(self, request):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        hoy = timezone.localdate()
        ini, fin = _bounds(hoy, hoy)

        leads_nuevos = Lead.objects.del_tenant_actual().filter(estado=Lead.Estado.NUEVO).count()
        leads_hoy = Lead.objects.del_tenant_actual().filter(creado_en__gte=ini, creado_en__lt=fin).count()

        # Sin las fichas provisionales: agendar una consulta abre una ficha para
        # colgar la cita, pero esa persona todavía no es paciente.
        total_pac = Paciente.objects.del_tenant_actual().filter(provisional=False).count()
        con_futura = set(
            Cita.objects.del_tenant_actual().filter(inicio__gte=timezone.now())
            .exclude(estado=Cita.Estado.CANCELADA).values_list("paciente_id", flat=True)
        )
        sin_proxima = max(total_pac - len(con_futura), 0)

        es_admin = getattr(request.user, "rol", None) == "admin"
        # Ve las cifras de dinero del día (gerencia y la analista); distinto de
        # es_admin, que además da la bandeja de eliminaciones (auditoría).
        ve_dinero = ve_finanzas(request.user)
        out = {
            "leads_nuevos": leads_nuevos, "leads_hoy": leads_hoy,
            "sin_proxima": sin_proxima, "es_admin": es_admin, "ve_dinero": ve_dinero,
            # El frontend ajusta textos que sugieren acciones (p. ej. "mándalos a
            # mano desde la agenda") que el rol de solo lectura no tiene.
            "solo_lectura": es_solo_lectura(request.user),
        }

        # `rol` también lo usa, más abajo, el bloque de captación/comercial.
        rol = getattr(request.user, "rol", None)

        # --- Continuidad terapéutica: riesgo de abandono (S3) y fin de bloque
        # sin decisión registrada. El psicólogo ve solo SUS pacientes; la
        # coordinadora (asistente) solo los de SU sede; admin y analista
        # (Dirección Clínica), ambas sedes.
        pac_cont = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)

        # La sesión real sale de las CITAS asistidas/atendidas, no del contador
        # manual del paciente (`Paciente.n_sesion`): ese solo se mueve si alguien
        # usa a propósito "Registrar sesión", y en producción se quedaba en 0
        # para la mayoría — filtrar por `n_sesion__gt=0` aquí mismo los sacaba
        # de esta pantalla antes de siquiera evaluar la alerta. Se agrega en una
        # sola consulta agrupada (no una por paciente) para no perder rendimiento.
        base = list(pac_cont.exclude(frecuencia__in=["alta", "en_pausa"])
                    .values("id", "nombre", "sesiones_proceso"))
        ids_base = [r["id"] for r in base]
        reales = continuidad_mod.sesion_real_por_pacientes(ids_base)
        filas = [{**r, "n_sesion": reales[r["id"]]} for r in base if reales.get(r["id"], 0) > 0]
        ids = [r["id"] for r in filas]

        con_futura_ids = set(
            Cita.objects.del_tenant_actual().filter(paciente_id__in=ids, inicio__gte=timezone.now())
            .exclude(estado=Cita.Estado.CANCELADA).values_list("paciente_id", flat=True)
        )
        # Última decisión (DP-08..DP-12) registrada en una cita ya realizada de
        # cada paciente — para no avisar de un fin de bloque que coordinación
        # ya resolvió.
        ultima_decision = {}
        citas_realizadas = (
            Cita.objects.del_tenant_actual()
            .filter(paciente_id__in=ids, estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.ASISTIO])
            .order_by("paciente_id", "-inicio").values("paciente_id", "decision")
        )
        for c in citas_realizadas:
            ultima_decision.setdefault(c["paciente_id"], c["decision"])  # la 1ra por paciente = la más reciente

        riesgo_abandono = []
        for r in filas:
            n = r["n_sesion"] or 0
            alertas = continuidad_mod.evaluar(
                n, r["sesiones_proceso"] or 0, r["id"] in con_futura_ids,
                ultima_decision.get(r["id"], ""), None,  # frecuencia ya excluida en el queryset
            )
            if continuidad_mod.RIESGO_ABANDONO_S3 in alertas:
                riesgo_abandono.append({"id": r["id"], "nombre": r["nombre"], "n_sesion": n})
        riesgo_abandono.sort(key=lambda x: x["nombre"])
        out["riesgo_abandono"] = riesgo_abandono[:30]
        out["riesgo_abandono_total"] = len(riesgo_abandono)

        # El Centro de Continuidad ya no es una lista de todos los cierres sin
        # decisión de la historia (eran 391, y 303 de ellos llevaban más de 90
        # días sin venir): es una cola priorizada por la FECHA real del cierre.
        # La tarjeta muestra el resumen y como mucho cinco casos; el resto vive
        # en "ver todos" (/api/continuidad/pendientes/).
        indicadores = {}
        cola = continuidad_mod.cola_de_continuidad(pac_cont, indicadores=indicadores)
        conteo = continuidad_mod.resumen_de_cola(cola)
        # Procesos anteriores sin cierre registrado: calidad de registro, no
        # acción. Va en el resumen para la línea "Calidad" de la tarjeta.
        conteo[continuidad_mod.EstadoCierre.PROCESO_ANTERIOR] = indicadores.get("procesos_anteriores_sin_cierre", 0)
        # Se copian TODOS los estados del resumen, no una lista escrita a mano:
        # cuando se agregó "riesgo_s3" la tarjeta se quedó sin él y mostraba
        # cero aunque el Centro de Continuidad sí lo contara. Derivarlo de
        # `conteo` evita que las dos pantallas vuelvan a desalinearse.
        out["continuidad"] = {
            **{estado: conteo[estado] for estado in continuidad_mod.GRUPOS},
            # Alias histórico: el frontend ya usaba estos dos nombres en plural.
            "vencidos": conteo[continuidad_mod.EstadoCierre.VENCIDO],
            "proximos": conteo[continuidad_mod.EstadoCierre.PROXIMO],
            "accionables": conteo["accionables"],
            # Selección híbrida: un caso por categoría accionable y el resto por
            # urgencia global, para que ninguna categoría quede invisible.
            "prioritarios": continuidad_mod.prioritarios_para_tarjeta(cola),
            "dias_proximos": continuidad_mod.DIAS_PROXIMOS,
        }

        # --- NPS (satisfacción del paciente) de los últimos 90 días ---
        # Promedio + índice NPS estándar (% promotores − % detractores).
        from pacientes.models import RespuestaNPS

        nps_qs = RespuestaNPS.objects.del_tenant_actual().filter(fecha__gte=hoy - timedelta(days=90))
        if rol == "medico":
            nps_qs = nps_qs.filter(paciente__profesional=ficha) if ficha else nps_qs.none()
        elif rol == "comercial":
            nps_qs = nps_qs.none()
        puntajes = list(nps_qs.values_list("puntaje", flat=True))
        if puntajes:
            n_nps = len(puntajes)
            promotores = sum(1 for x in puntajes if x >= 9)
            detractores = sum(1 for x in puntajes if x <= 6)
            out["nps"] = {
                "promedio": round(sum(puntajes) / n_nps, 1),
                "n": n_nps,
                "indice": round((promotores - detractores) / n_nps * 100),
                "dias": 90,
            }
        else:
            out["nps"] = {"promedio": None, "n": 0, "indice": None, "dias": 90}

        # --- Meta comercial del mes (la ve gerencia y coordinación) ---
        # Gaby: "que les salga a diario cuánto vienen generando y el % de meta,
        # para que tengan presente cobrar y cerrar procesos".
        if rol in ("admin", "asistente", "analista"):
            clinica = get_clinica_actual()
            mes_ini = hoy.replace(day=1)
            dias_mes = monthrange(hoy.year, hoy.month)[1]
            m_ini, m_fin = _bounds(mes_ini, hoy)
            metas_sede = clinica.metas_sede or {}
            sede_labels = dict(Paciente.Sede.choices)

            def _meta_de(sede_scope):
                """Meta del mes para una sede (o total si sede_scope vacío)."""
                cobros_mes = (Cobro.objects.del_tenant_actual()
                              .filter(estado=Cobro.Estado.PAGADO, fecha__gte=m_ini, fecha__lt=m_fin))
                if sede_scope:
                    cobros_mes = cobros_mes.filter(paciente__sede=sede_scope)
                generado = float(cobros_mes.aggregate(s=Sum("monto"))["s"] or 0)
                m_sede = metas_sede.get(sede_scope) if sede_scope else None
                # Meta de la sede si está configurada; si falta un valor, cae al general
                # (evita dividir entre 0 en el frontend).
                if isinstance(m_sede, dict):
                    meta_min = float(m_sede.get("min") or 0) or float(clinica.meta_min_mes or 0)
                    meta_ideal = float(m_sede.get("ideal") or 0) or float(clinica.meta_ideal_mes or 0)
                else:
                    meta_min = float(clinica.meta_min_mes or 0)
                    meta_ideal = float(clinica.meta_ideal_mes or 0)
                esperado = round(meta_min * hoy.day / dias_mes) if meta_min else 0
                return {
                    "generado": generado, "meta_min": meta_min, "meta_ideal": meta_ideal,
                    "pct_min": round(generado / meta_min * 100) if meta_min else 0,
                    "pct_ideal": round(generado / meta_ideal * 100) if meta_ideal else 0,
                    "esperado_hoy": esperado, "en_ritmo": generado >= esperado,
                    "dia": hoy.day, "dias_mes": dias_mes,
                    "sede": sede_scope,
                    "sede_label": sede_labels.get(sede_scope, "") if sede_scope else "Total",
                }

            if rol == "asistente":
                # La coordinadora ve SOLO la meta de su sede (o el total si no tiene sede).
                out["meta"] = _meta_de(getattr(request.user, "sede", "") or "")
            elif rol == "analista":
                # Dirección Clínica ve la meta TOTAL de la clínica (ambas sedes
                # sumadas): su trabajo es el gap global, no el de un local.
                out["meta"] = _meta_de("")
            else:
                # Gerencia: una meta POR SEDE (no sumadas), cada una hacia su objetivo.
                out["metas"] = [_meta_de(s) for s, _ in Paciente.Sede.choices]

        # Recordatorios del día. El envío corre desde una tarea programada FUERA del
        # servidor, así que si un día no se dispara —el equipo apagado, un error— hoy
        # nadie se entera hasta que un paciente no llega. Esto lo pone a la vista de
        # coordinación, pero solo a media mañana: antes de las 9 es normal que aún no
        # hayan salido y avisar sería ruido.
        if rol in ("admin", "asistente", "analista"):
            pendientes = (
                Cita.objects.del_tenant_actual()
                .filter(inicio__gte=ini, inicio__lt=fin, recordatorio_enviado=False)
                .exclude(estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.CANCELADA])
                .exclude(paciente__telefono="")   # sin teléfono no hay nada que enviar
                .count()
            )
            out["recordatorios"] = {
                "pendientes": pendientes,
                "avisar": pendientes > 0 and timezone.localtime().hour >= 9,
            }

        if ve_dinero:
            cobros = Cobro.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin)
            out["ingresos_hoy"] = float(cobros.filter(estado=Cobro.Estado.PAGADO).aggregate(s=Sum("monto"))["s"] or 0)
            out["pendiente_hoy"] = float(cobros.filter(estado=Cobro.Estado.PENDIENTE).aggregate(s=Sum("monto"))["s"] or 0)

        if es_admin:
            # Eliminaciones recientes (citas/pagos) — solo gerencia: es auditoría
            # con nombre de paciente y de quién borró. La analista NO la recibe
            # aunque sí vea el dinero del día (por eso este `if` va aparte).
            from pacientes.models import RegistroEliminacion
            elim_qs = (RegistroEliminacion.objects.del_tenant_actual()
                       .filter(revisado=False,
                               creado_en__gte=timezone.now() - timedelta(days=7)))
            # Total pendiente ANTES del recorte: si hay más de 12, el frontend lo
            # dice ("mostrando 12 de N") y ofrece "OK a todo" — antes parecía que
            # los avisos "volvían" porque cada OK revelaba el siguiente.
            out["eliminaciones_total"] = elim_qs.count()
            elim = elim_qs.select_related("usuario")[:12]
            out["eliminaciones"] = [{
                "id": e.id,
                "tipo": e.tipo, "tipo_label": e.get_tipo_display(),
                "descripcion": e.descripcion, "paciente": e.paciente_nombre,
                "usuario": str(e.usuario) if e.usuario_id else "",
                "cuando": timezone.localtime(e.creado_en).strftime("%d/%m %H:%M"),
            } for e in elim]
        return Response(out)


class ContinuidadPendientesView(APIView):
    """GET /api/continuidad/pendientes/ — la cola completa de cierres de bloque
    sin decisión registrada, para trabajarla como lista.

    La tarjeta de "Hoy" solo muestra el resumen y cinco casos; aquí está todo,
    con filtros. Respeta el mismo alcance por rol que la tarjeta: el psicólogo
    ve solo sus pacientes, la coordinadora los de su sede, admin y analista
    ambas sedes, el comercial nada.

    Filtros (todos opcionales, se combinan):
      estado=vencido|hoy|riesgo_s3|sin_agendar|proximo|continuo_sin_decision
             |dato_incompleto|backlog
             |accionables   (por defecto: lo que pide acción esta semana)
             |accion|seguimiento|calidad   (grupos completos)
             |todos
      sede=lima|piura · medico=<id del profesional> · bloque=6|12|18|24
      dias_proximos=<n>  (ventana hacia adelante; por defecto 7)
    """

    def get(self, request):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        qs = continuidad_mod.pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)

        sede = (request.query_params.get("sede") or "").strip()
        if sede:
            qs = qs.filter(sede=sede)
        medico = (request.query_params.get("medico") or "").strip()
        if medico.isdigit():
            qs = qs.filter(profesional_id=int(medico))

        try:
            dias_proximos = int(request.query_params.get("dias_proximos") or continuidad_mod.DIAS_PROXIMOS)
        except (TypeError, ValueError):
            dias_proximos = continuidad_mod.DIAS_PROXIMOS

        indicadores = {}
        cola = continuidad_mod.cola_de_continuidad(qs, dias_proximos=dias_proximos,
                                                   con_contexto=True, indicadores=indicadores)
        conteo = continuidad_mod.resumen_de_cola(cola)
        # Calidad de registro · procesos anteriores sin cierre registrado. No
        # son la cola de acción (el paciente ya está en otro proceso): se
        # cuentan y se listan aparte, y solo entran con su propio filtro.
        anteriores = indicadores.get("filas_procesos_anteriores", [])
        conteo[continuidad_mod.EstadoCierre.PROCESO_ANTERIOR] = len(anteriores)
        conteo[continuidad_mod.GRUPO_CALIDAD] += len(anteriores)
        conteo["numeracion_inconsistente"] = indicadores.get("numeracion_inconsistente", 0)

        estado = (request.query_params.get("estado") or "accionables").strip()
        grupos = (continuidad_mod.GRUPO_ACCION, continuidad_mod.GRUPO_SEGUIMIENTO,
                  continuidad_mod.GRUPO_CALIDAD)
        if estado == "accionables":
            filas = [f for f in cola if f["estado"] in continuidad_mod.EstadoCierre.ACCIONABLES]
        elif estado == continuidad_mod.EstadoCierre.PROCESO_ANTERIOR:
            filas = list(anteriores)
        elif estado in grupos:
            filas = [f for f in cola if f["grupo"] == estado]
            if estado == continuidad_mod.GRUPO_CALIDAD:
                filas = filas + anteriores
        elif estado and estado != "todos":
            filas = [f for f in cola if f["estado"] == estado]
        else:
            filas = cola + anteriores

        bloque = (request.query_params.get("bloque") or "").strip()
        if bloque.isdigit():
            filas = [f for f in filas if f["meta"] == int(bloque)]

        # Gestión operativa por fila (una consulta para toda la cola). Se
        # superpone: la fila sigue saliendo de la fuente oficial aunque alguien
        # la haya marcado "resuelto" — en ese caso lleva `alerta`.
        from core import gestion_continuidad as gc
        from pacientes.models import GestionContinuidad
        por_paciente = {}
        for g in GestionContinuidad.objects.filter(paciente_id__in=[f["id"] for f in cola]):
            por_paciente.setdefault(g.paciente_id, []).append(g)
        for f in filas:
            f["gestion"] = gc.resumen(gc.gestion_de(f, por_paciente.get(f["id"], [])), f)

        revision = (request.query_params.get("revision") or "").strip()
        if revision == "sin_revisar":
            filas = [f for f in filas if not f["gestion"] or f["gestion"]["estado_revision"] == "sin_revisar"]
        elif revision in ("en_seguimiento", "resuelto"):
            filas = [f for f in filas if f["gestion"] and f["gestion"]["estado_revision"] == revision]
        elif revision == "atencion":
            # "Requiere mi atención": sin revisar, o resuelto pero todavía
            # detectado, o asignado al responsable que corresponde a mi rol.
            mio = gc.RESPONSABLE_DE_ROL.get(getattr(request.user, "rol", None))
            filas = [f for f in filas if (not f["gestion"])
                     or f["gestion"]["estado_revision"] == "sin_revisar"
                     or f["gestion"]["alerta"]
                     or (mio and f["gestion"]["responsable"] == mio
                         and f["gestion"]["estado_revision"] != "resuelto")]

        # "Resueltos" también lista lo que el sistema o una persona cerró y ya
        # no está en la cola (últimos 30 días): es la única forma de ver que
        # un caso se resolvió de verdad, no solo que desapareció.
        if revision == "resuelto":
            filas = filas + self._cerradas_fuera_de_cola(qs, cola, por_paciente)

        return Response({
            "filas": filas,
            "total": len(filas),
            "conteo": conteo,
            "dias_proximos": dias_proximos,
            "dias_backlog": continuidad_mod.DIAS_BACKLOG,
        })

    DIAS_CERRADAS = 30

    def _cerradas_fuera_de_cola(self, qs, cola, por_paciente):
        from core import gestion_continuidad as gc
        from pacientes.models import GestionContinuidad
        en_cola = {(f["id"], f["evento"]["tipo"], f["evento"]["meta"]) for f in cola}
        desde = timezone.now() - timedelta(days=self.DIAS_CERRADAS)
        cerradas = (GestionContinuidad.objects
                    .filter(paciente__in=qs, resuelto_en__gte=desde)
                    .select_related("paciente", "paciente__profesional")
                    .order_by("-resuelto_en"))
        filas, vistos = [], set()
        for g in cerradas:
            clave = (g.paciente_id, g.tipo, g.meta)
            if clave in en_cola or clave in vistos:
                continue
            vistos.add(clave)
            filas.append({
                "id": g.paciente_id,
                "paciente": g.paciente.nombre,
                "sede": g.paciente.sede or "",
                "psicologo": getattr(g.paciente.profesional, "nombre", "") or "",
                "n_sesion": None, "meta": g.meta,
                "fecha_cierre": None, "origen_fecha": "", "estado": "cerrado", "grupo": "cerrado",
                "dias": None, "tiene_proxima": None, "proxima_fecha": None, "ultima_sesion": None,
                "faltantes": [], "evento": {"tipo": g.tipo, "meta": g.meta},
                "anteriores_sin_decision": [], "contexto": "", "contexto_claves": [], "avisos": [],
                "que_confirmar": "Sin pendiente: la condición ya no se detecta.",
                "resuelto_en": gc._iso(g.resuelto_en),
                "gestion": gc.resumen(g, None),
            })
        return filas


class ContinuidadCasoView(APIView):
    """GET /api/continuidad/caso/<paciente_id>/ — el detalle de UN caso, para
    revisarlo sin salir del Centro de Continuidad.

    Devuelve lo mismo que la fila de la cola más lo que no cabe en una tabla:
    las notas de agenda que sustentan el contexto y el historial corto de
    sesiones. Todo se recalcula en el momento desde las fuentes oficiales
    (citas y decisiones), así que si la Agenda ya arregló el caso —se agendó la
    próxima cita, se registró el DP— este endpoint responde `en_cola: false` y
    la pantalla lo refleja sola. No hay copia del estado en ninguna parte.

    Respeta el alcance por rol: si el caso no está dentro de lo que ese usuario
    puede ver, responde 404 (no "prohibido": no se confirma que exista).
    """

    # Cuántas sesiones del historial se devuelven. Suficiente para entender el
    # caso; la historia completa vive en la ficha del paciente.
    MAX_HISTORIAL = 8

    @staticmethod
    def payload(request, paciente, visibles):
        """El detalle completo de un caso. Lo usan GET y el PATCH de gestión,
        para que la pantalla reciba lo mismo después de guardar."""
        from core import contacto_continuidad as cc
        from core import gestion_continuidad as gc

        cola = continuidad_mod.cola_de_continuidad(
            visibles.filter(pk=paciente.pk), con_contexto=True)
        fila = cola[0] if cola else None

        citas = list(Cita.objects.filter(paciente=paciente)
                     .order_by("-inicio")
                     .values("id", "inicio", "estado", "n_sesion", "decision", "notas")
                     [:ContinuidadCasoView.MAX_HISTORIAL])
        historial = [{
            "id": c["id"],
            "fecha": timezone.localtime(c["inicio"]).date().isoformat(),
            "estado": c["estado"],
            "n_sesion": c["n_sesion"],
            "decision": c["decision"] or "",
            "notas": (c["notas"] or "").strip(),
        } for c in citas]

        # La gestión operativa se superpone al leer: nunca cambia la fila.
        gestion = gc.gestion_de(fila) if fila is not None else gc.ultima_gestion(paciente)

        return {
            "paciente": {
                "id": paciente.id,
                "nombre": paciente.nombre,
                "sede": paciente.sede or "",
                "psicologo": getattr(paciente.profesional, "nombre", "") or "",
                "frecuencia": paciente.frecuencia or "",
            },
            "en_cola": fila is not None,
            "fila": fila,
            "historial": historial,
            # Las notas son texto de coordinación, no historia clínica; se muestran
            # a quien ya puede ver el caso. La bandera queda explícita para poder
            # restringirlo por rol más adelante sin tocar el frontend.
            "notas_visibles": True,
            "gestion": gc.serializar(gestion, fila),
            "historial_gestion": gc.serializar_historial(gestion),
            "puede_gestionar": puede_gestionar_continuidad(request.user),
            # Contacto por WhatsApp del caso: por qué línea saldría, qué se
            # envió ya y qué contestó el paciente. Solo lectura: enviar es un
            # POST aparte. Ver core/contacto_continuidad.py.
            "contacto": cc.serializar_contacto(paciente, gestion, request.user),
        }

    def get(self, request, pk):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        visibles = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)
        paciente = visibles.filter(pk=pk).first()
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.payload(request, paciente, visibles))


class ContinuidadGestionView(APIView):
    """PATCH /api/continuidad/caso/<paciente_id>/gestion/ — "Guardar seguimiento".

    Acepta SOLO los cuatro campos operativos (estado_revision,
    resultado_operativo, responsable, observacion_operativa); cualquier otra
    clave se ignora. No toca citas, decisiones ni datos clínicos: eso vive en
    la Agenda y aquí ni se lee para escribir.

    Permisos propios (reemplazan a los globales solo en esta vista): admin,
    coordinación, psicólogo y analista. El alcance sigue siendo el de
    `pacientes_del_rol`: coordinación no sale de su sede, el psicólogo no toca
    pacientes ajenos (404, no 403: no se confirma que existan).
    """

    permission_classes = [IsAuthenticated, PuedeGestionarContinuidad]

    def patch(self, request, pk):
        from core import gestion_continuidad as gc

        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        visibles = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)
        paciente = visibles.filter(pk=pk).first()
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)

        datos = {c: request.data.get(c) for c in gc.CAMPOS_EDITABLES if c in request.data}
        if not datos:
            return Response({"detail": "Nada que guardar."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            gc.guardar(paciente, request.user, datos)
        except gc.SinCondicion as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ContinuidadCasoView.payload(request, paciente, visibles))


class ContinuidadWhatsappView(APIView):
    """El contacto por WhatsApp de un caso del Centro de Continuidad.

    GET  /api/continuidad/caso/<paciente_id>/whatsapp/ — qué se enviaría (motivo,
         línea de la sede, plantilla ya rellenada, contactos anteriores). No
         escribe ni envía nada.
    POST /api/continuidad/caso/<paciente_id>/whatsapp/ — envía. Acepta `texto`
         (editado por quien escribe), `observacion` y `confirmado` (para volver
         a escribirle antes de las 24 h).

    Permisos propios: coordinación y gerencia. El psicólogo y la analista
    gestionan el caso pero no contactan pacientes (ver ROLES_CONTACTAN_PACIENTES).
    El alcance sigue siendo `pacientes_del_rol`.

    Enviar nunca deja el caso "resuelto": como mucho "en seguimiento". Y el
    envío sale siempre desde el sistema por la línea de la sede: no se abre
    WhatsApp Web ni se devuelven enlaces wa.me.
    """

    permission_classes = [IsAuthenticated, PuedeContactarPacientes]

    def _paciente(self, request, pk):
        visibles = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)
        return visibles.filter(pk=pk).first(), visibles

    def get(self, request, pk):
        from core import contacto_continuidad as cc
        from core import gestion_continuidad as gc

        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        paciente, _ = self._paciente(request, pk)
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        fila = gc.fila_de(paciente)
        gestion = gc.gestion_de(fila) if fila is not None else gc.ultima_gestion(paciente)
        return Response(cc.preview(paciente, request.user, fila, gestion))

    def post(self, request, pk):
        from core import contacto_continuidad as cc
        from core import gestion_continuidad as gc

        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        paciente, visibles = self._paciente(request, pk)
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        texto = str(request.data.get("texto") or "")
        try:
            _, resultado = cc.enviar(
                paciente, request.user, texto=texto,
                observacion=str(request.data.get("observacion") or ""),
                confirmado=bool(request.data.get("confirmado")),
                plantilla_clave=str(request.data.get("plantilla_clave") or ""),
            )
        except cc.ContactoBloqueado as e:
            # 422: la petición es válida, pero falta un dato o la línea. Cuando
            # lo que falta es la línea, se devuelve el texto listo para que la
            # coordinadora lo copie y lo mande a mano — sin abrir WhatsApp Web ni
            # enlaces wa.me: el sistema no escribe desde otro número.
            cuerpo = {"detail": str(e), "bloqueo": e.codigo}
            if e.codigo == "sin_linea":
                cuerpo["texto_para_copiar"] = texto.strip() or cc.texto_sugerido(
                    paciente.clinica, paciente, request.user, gc.fila_de(paciente))[0]
            return Response(cuerpo, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except gc.SinCondicion as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except ValueError as e:
            return Response({"detail": str(e), "requiere_confirmacion": True},
                            status=status.HTTP_400_BAD_REQUEST)
        datos = ContinuidadCasoView.payload(request, paciente, visibles)
        # Lo que el modal muestra al terminar: por dónde salió y con qué id, para
        # que la coordinadora vea el resultado sin ir a buscarlo a la bitácora.
        ultimo = (datos.get("contacto") or {}).get("ultimo") or {}
        datos["envio"] = {
            "estado": resultado.get("estado"),
            "detalle": resultado.get("detalle", ""),
            "proveedor": ultimo.get("proveedor", ""),
            "instancia": resultado.get("instancia") or ultimo.get("instancia", ""),
            "external_message_id": ultimo.get("external_message_id", ""),
            "fecha": ultimo.get("fecha", ""),
        }
        return Response(datos)


class ContinuidadCopiadoView(APIView):
    """POST /api/continuidad/caso/<paciente_id>/whatsapp/copiado/

    La sede no tiene línea conectada y la coordinadora copió el mensaje para
    mandarlo desde su propio WhatsApp. Aquí solo queda el rastro (quién, cuándo,
    qué plantilla): el sistema no envió nada. Es el respaldo temporal hasta que
    las líneas de Lima y Piura estén conectadas.
    """

    permission_classes = [IsAuthenticated, PuedeContactarPacientes]

    def post(self, request, pk):
        from core import contacto_continuidad as cc
        from core import gestion_continuidad as gc

        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        visibles = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)
        paciente = visibles.filter(pk=pk).first()
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            cc.registrar_copia_manual(paciente, request.user)
        except gc.SinCondicion as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ContinuidadCasoView.payload(request, paciente, visibles))


class ContinuidadRespuestaView(APIView):
    """POST /api/continuidad/caso/<paciente_id>/whatsapp/respuesta/

    La coordinadora clasifica lo que contestó el paciente (continua /
    mas_adelante / no_continua / sin_respuesta). El sistema NO interpreta el
    texto: solo guarda lo que una persona decidió que significaba.

    Ninguna respuesta cierra el caso. "No continuará" queda como resultado
    operativo y el caso sigue en seguimiento hasta que la Agenda registre el DP
    de cierre — ahí `reconciliar` lo cierra solo.
    """

    permission_classes = [IsAuthenticated, PuedeContactarPacientes]

    def post(self, request, pk):
        from core import contacto_continuidad as cc
        from core import gestion_continuidad as gc

        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        visibles = continuidad_mod.pacientes_del_rol(
            Paciente.objects.del_tenant_actual(), request.user)
        paciente = visibles.filter(pk=pk).first()
        if paciente is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            cc.registrar_respuesta(paciente, request.user,
                                   str(request.data.get("respuesta") or ""))
        except gc.SinCondicion as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ContinuidadCasoView.payload(request, paciente, visibles))


class EliminacionRevisarView(APIView):
    """POST /api/eliminaciones/<pk>/revisar/ — la gerencia marca una alerta de
    eliminación (cita/pago borrado) como revisada y conforme: deja de salir en el
    inicio. El registro se conserva para trazabilidad; solo se oculta el aviso."""

    def post(self, request, pk):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(request.user, "rol", None) != "admin":
            return Response({"detail": "Solo gerencia/coordinación puede revisar eliminaciones."},
                            status=status.HTTP_403_FORBIDDEN)
        from pacientes.models import RegistroEliminacion
        reg = RegistroEliminacion.objects.del_tenant_actual().filter(pk=pk).first()
        if reg is None:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if not reg.revisado:
            reg.revisado = True
            reg.revisado_en = timezone.now()
            reg.revisado_por = request.user
            reg.save(update_fields=["revisado", "revisado_en", "revisado_por"])
        return Response({"ok": True, "id": reg.id})


class EliminacionesRevisarTodasView(APIView):
    """POST /api/eliminaciones/revisar-todas/ — marca TODAS las alertas de
    eliminación pendientes como revisadas de una vez (botón "OK a todo"). Los
    registros se conservan para trazabilidad; solo dejan de salir en el inicio."""

    def post(self, request):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(request.user, "rol", None) != "admin":
            return Response({"detail": "Solo gerencia/coordinación puede revisar eliminaciones."},
                            status=status.HTTP_403_FORBIDDEN)
        from pacientes.models import RegistroEliminacion
        n = (RegistroEliminacion.objects.del_tenant_actual()
             .filter(revisado=False)
             .update(revisado=True, revisado_en=timezone.now(), revisado_por=request.user))
        return Response({"ok": True, "revisadas": n})


class GerenciaResumenView(APIView):
    """GET /api/gerencia/resumen/?periodo=hoy|7d|semana|30d|mes — resumen del negocio."""

    def get(self, request):
        from usuarios.models import Usuario

        # Gerencia y la analista (Dirección Clínica): son sus indicadores. Es
        # solo lectura, así que abrirlo no da ningún poder de edición.
        if getattr(request.user, "rol", None) not in (Usuario.Rol.ADMIN, Usuario.Rol.ANALISTA):
            return Response({"detail": "Solo gerencia y Dirección Clínica pueden ver este panel."},
                            status=status.HTTP_403_FORBIDDEN)
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)

        periodo = request.query_params.get("periodo", "mes")
        desde, hasta, label = _rango(periodo)
        ini, fin = _bounds(desde, hasta)

        # --- Filtro por sede (Total / Lima / Piura) ---
        sede = (request.query_params.get("sede") or "").strip().lower()
        if sede not in ("lima", "piura"):
            sede = ""  # "" = todas las sedes (Total)

        def fpac(qs):
            """Acota por la sede del paciente (citas, atenciones, cobros…)."""
            return qs.filter(paciente__sede=sede) if sede else qs

        def fsede(qs):
            """Acota por el campo sede directo (pacientes, leads)."""
            return qs.filter(sede=sede) if sede else qs

        # --- Operación (agenda) ---
        E = Cita.Estado
        citas = list(fpac(Cita.objects.del_tenant_actual().filter(inicio__gte=ini, inicio__lt=fin)).select_related("medico"))
        atendidas = sum(1 for c in citas if c.estado == E.ATENDIDA)
        canceladas = sum(1 for c in citas if c.estado == E.CANCELADA)
        cerradas = atendidas + canceladas
        recordatorios = Mensaje.objects.del_tenant_actual().filter(
            tipo=Mensaje.Tipo.RECORDATORIO, estado=Mensaje.Estado.ENVIADO,
            creado_en__gte=ini, creado_en__lt=fin,
        ).count()
        cit_dia = {}
        for c in citas:
            k = timezone.localtime(c.inicio).date().isoformat()
            cit_dia[k] = cit_dia.get(k, 0) + 1
        por_dia_citas = [{"fecha": k, "citas": v} for k, v in sorted(cit_dia.items())]
        operacion = {
            "citas": len(citas),
            "atendidas": atendidas,
            "canceladas": canceladas,
            "confirmadas": sum(1 for c in citas if c.estado == E.CONFIRMADA),
            "por_confirmar": sum(1 for c in citas if c.estado == E.POR_CONFIRMAR),
            "asistencia_pct": round(atendidas / cerradas * 100) if cerradas else 0,
            "cancelacion_pct": round(canceladas / cerradas * 100) if cerradas else 0,
            "recordatorios": recordatorios,
            "por_dia": por_dia_citas,
        }

        # --- Captación (leads del período) ---
        LE = Lead.Estado
        leads = list(fsede(Lead.objects.del_tenant_actual().filter(creado_en__gte=ini, creado_en__lt=fin)).select_related("medico"))
        recibidos = len(leads)
        de_pauta = sum(1 for l in leads if l.es_pauta)
        cierres = sum(1 for l in leads if l.estado == LE.GANADO)
        por_fuente, por_campania = {}, {}
        for l in leads:
            por_fuente[l.fuente] = por_fuente.get(l.fuente, 0) + 1
            if l.campania:
                por_campania[l.campania] = por_campania.get(l.campania, 0) + 1
        fuente_label = dict(Lead.Fuente.choices)
        top_fuente = max(por_fuente, key=por_fuente.get) if por_fuente else None
        top_campania = max(por_campania, key=por_campania.get) if por_campania else None
        captacion = {
            "recibidos": recibidos,
            "pauta": de_pauta,
            "pauta_pct": round(de_pauta / recibidos * 100) if recibidos else 0,
            "cierres": cierres,
            "tasa_cierre": round(cierres / recibidos * 100) if recibidos else 0,
            "top_fuente": fuente_label.get(top_fuente, "—") if top_fuente else "—",
            "top_campania": top_campania or "—",
        }
        leads_dia = {}
        for l in leads:
            k = timezone.localtime(l.creado_en).date().isoformat()
            leads_dia[k] = leads_dia.get(k, 0) + 1
        captacion["por_dia"] = [{"fecha": k, "leads": v} for k, v in sorted(leads_dia.items())]

        # --- Pacientes ---
        # Solo pacientes de verdad: las fichas provisionales (consulta agendada,
        # proceso no iniciado) no cuentan ni en el total ni en la demografía.
        reales = Paciente.objects.del_tenant_actual().filter(provisional=False)
        total_pac = fsede(reales).count()
        nuevos_pac = fsede(reales.filter(creado_en__gte=ini, creado_en__lt=fin)).count()
        con_futura = set(
            fpac(Cita.objects.del_tenant_actual()
                 .filter(inicio__gte=timezone.now())
                 .exclude(estado=E.CANCELADA))
            .values_list("paciente_id", flat=True)
        )
        pacientes = {
            "total": total_pac,
            "nuevos": nuevos_pac,
            "sin_proxima": max(total_pac - len(con_futura), 0),
        }

        # --- Demografía (sobre toda la base de pacientes) ---
        gen = {"femenino": 0, "masculino": 0, "otro": 0, "sin": 0}
        ed = {"0-24": 0, "25-35": 0, "36-45": 0, "46-55": 0, "+56": 0, "sin": 0}
        for p in fsede(reales).only("genero", "fecha_nacimiento"):
            gen[p.genero if p.genero in gen else "sin"] += 1
            e = p.edad
            if e is None:
                ed["sin"] += 1
            elif e <= 24:
                ed["0-24"] += 1
            elif e <= 35:
                ed["25-35"] += 1
            elif e <= 45:
                ed["36-45"] += 1
            elif e <= 55:
                ed["46-55"] += 1
            else:
                ed["+56"] += 1
        demografia = {
            "genero": [
                {"label": "Femenino", "valor": gen["femenino"]},
                {"label": "Masculino", "valor": gen["masculino"]},
                {"label": "Otro", "valor": gen["otro"]},
                {"label": "Sin registro", "valor": gen["sin"]},
            ],
            "edad": [
                {"label": "0-24", "valor": ed["0-24"]},
                {"label": "25-35", "valor": ed["25-35"]},
                {"label": "36-45", "valor": ed["36-45"]},
                {"label": "46-55", "valor": ed["46-55"]},
                {"label": "+56", "valor": ed["+56"]},
                {"label": "Sin registro", "valor": ed["sin"]},
            ],
        }

        # --- Retención (semáforo por días desde la última sesión) ---
        # Regla de la clínica (hoja SEG): verde <8 días, amarillo 8–15, rojo >15
        # (abandono → llamar). Sobre los pacientes con al menos una atención.
        hoy_d = timezone.localdate()
        ret = {"verde": 0, "amarillo": 0, "rojo": 0}
        ultimas = (
            fpac(Atencion.objects.del_tenant_actual())
            .values("paciente_id").annotate(ultima=Max("fecha"))
        )
        for row in ultimas:
            dias = (hoy_d - timezone.localtime(row["ultima"]).date()).days
            if dias < 8:
                ret["verde"] += 1
            elif dias <= 15:
                ret["amarillo"] += 1
            else:
                ret["rojo"] += 1
        con_sesiones = ret["verde"] + ret["amarillo"] + ret["rojo"]
        retencion = {
            "con_sesiones": con_sesiones,
            "verde": ret["verde"], "amarillo": ret["amarillo"], "rojo": ret["rojo"],
            "rojo_pct": round(ret["rojo"] / con_sesiones * 100) if con_sesiones else 0,
        }

        # --- Productividad por médico ---
        prod = {}

        def fila(medico_id, nombre):
            return prod.setdefault(medico_id or 0, {
                "medico": nombre, "citas": 0, "atenciones": 0, "leads": 0, "cierres": 0,
            })

        for c in citas:
            fila(c.medico_id, str(c.medico) if c.medico_id else "Sin asignar")["citas"] += 1
        atenciones = list(fpac(Atencion.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin)).select_related("medico"))
        for a in atenciones:
            fila(a.medico_id, str(a.medico) if a.medico_id else "Sin asignar")["atenciones"] += 1
        for l in leads:
            f = fila(l.medico_id, str(l.medico) if l.medico_id else "Sin asignar")
            f["leads"] += 1
            if l.estado == LE.GANADO:
                f["cierres"] += 1
        productividad = sorted(prod.values(), key=lambda x: (-x["atenciones"], -x["citas"], -x["leads"]))

        # --- Finanzas (ingresos, egresos y utilidad reales del período) ---
        cobros = fpac(Cobro.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin))
        cobrado = cobros.filter(estado=Cobro.Estado.PAGADO).aggregate(s=Sum("monto"))["s"] or 0
        pendiente = cobros.filter(estado=Cobro.Estado.PENDIENTE).aggregate(s=Sum("monto"))["s"] or 0
        # Los egresos no están etiquetados por sede: solo se muestran en la vista Total.
        if sede:
            finanzas = {"cobrado": float(cobrado), "pendiente": float(pendiente),
                        "egresos": None, "utilidad": None}
        else:
            egresos = Egreso.objects.del_tenant_actual().filter(
                fecha__gte=ini, fecha__lt=fin
            ).aggregate(s=Sum("monto"))["s"] or 0
            finanzas = {
                "cobrado": float(cobrado),
                "pendiente": float(pendiente),
                "egresos": float(egresos),
                "utilidad": float(cobrado) - float(egresos),
            }
        cobrado_dia = {}
        for c in cobros.filter(estado=Cobro.Estado.PAGADO).only("fecha", "monto"):
            k = timezone.localtime(c.fecha).date().isoformat()
            cobrado_dia[k] = cobrado_dia.get(k, 0) + float(c.monto)
        finanzas["por_dia"] = [{"fecha": k, "monto": v} for k, v in sorted(cobrado_dia.items())]

        # --- Diagnóstico: ¿se está USANDO lo que el sistema ya tiene para decidir? ---
        # No repite los bloques de arriba: mide adopción de proceso (motivo de
        # cierre, leads resueltos, medio de pago) y dónde se concentra el abandono
        # temprano. Son las brechas que un tablero de "cuánto entra/sale" no muestra.
        estado_label = dict(Lead.Estado.choices)
        por_estado = {}
        for l in leads:
            por_estado[l.estado] = por_estado.get(l.estado, 0) + 1
        ganados = por_estado.get(LE.GANADO, 0)
        perdidos = por_estado.get(LE.PERDIDO, 0)
        resueltos_n = ganados + perdidos
        embudo = {
            "total": recibidos,
            "ganados": ganados,
            "perdidos": perdidos,
            "resueltos": resueltos_n,
            "en_curso": recibidos - resueltos_n,
            "resueltos_pct": round(resueltos_n / recibidos * 100) if recibidos else 0,
            "por_estado": [
                {"label": estado_label.get(k, k), "valor": v}
                for k, v in sorted(por_estado.items(), key=lambda kv: -kv[1])
            ],
        }

        # Curva de continuidad: de TODOS los pacientes con historia clínica (no
        # depende del período elegido, igual que Retención más arriba), cuántas
        # atenciones acumula cada uno. Muestra dónde se concentra el abandono.
        conteo_atenciones = (
            fpac(Atencion.objects.del_tenant_actual())
            .values("paciente_id").annotate(n=Count("id"))
        )
        buckets = {"1": 0, "2": 0, "3": 0, "4": 0, "5+": 0}
        for row in conteo_atenciones:
            clave = str(row["n"]) if row["n"] <= 4 else "5+"
            buckets[clave] += 1
        con_historia = sum(buckets.values())
        continuidad_curva = {
            "con_historia": con_historia,
            "por_sesiones": [{"label": k, "valor": v} for k, v in buckets.items()],
            "abandono_1_2_pct": round((buckets["1"] + buckets["2"]) / con_historia * 100) if con_historia else 0,
        }

        # Adopción del motivo de cierre (Cita.decision): de las citas del período
        # que ya tuvieron un desenlace, ¿cuántas quedaron con el motivo registrado?
        # Sin este dato nadie puede saber DESPUÉS por qué se perdió a un paciente.
        TERMINALES = {E.ATENDIDA, E.ASISTIO, E.NO_ASISTIO, E.CANCELADA}
        citas_terminales = [c for c in citas if c.estado in TERMINALES]
        con_decision = sum(1 for c in citas_terminales if c.decision)
        decision_adopcion = {
            "citas_terminadas": len(citas_terminales),
            "con_motivo": con_decision,
            "pct": round(con_decision / len(citas_terminales) * 100) if citas_terminales else 0,
        }

        # Medio de pago: cuánto de lo cobrado queda sin trazabilidad de cómo llegó
        # (control de caja).
        medio_label = dict(Cobro.Medio.choices)
        medio_rows = list(
            cobros.filter(estado=Cobro.Estado.PAGADO).values("medio_pago").annotate(s=Sum("monto"))
        )
        total_medio = sum(float(r["s"] or 0) for r in medio_rows)
        sin_medio = sum(float(r["s"] or 0) for r in medio_rows if not r["medio_pago"])
        medio_pago = {
            "total": total_medio,
            "sin_medio": sin_medio,
            "sin_medio_pct": round(sin_medio / total_medio * 100) if total_medio else 0,
            "por_medio": [
                {
                    "label": medio_label.get(r["medio_pago"], "Sin registrar") if r["medio_pago"] else "Sin registrar",
                    "valor": float(r["s"] or 0),
                }
                for r in sorted(medio_rows, key=lambda r: -(float(r["s"] or 0)))
            ],
        }

        diagnostico = {
            "embudo": embudo,
            "continuidad": continuidad_curva,
            "decision": decision_adopcion,
            "medio_pago": medio_pago,
        }

        # --- Comparativa con el período anterior (tendencias) ---
        a_desde, a_hasta = _rango_anterior(periodo, desde, hasta)
        a_ini, a_fin = _bounds(a_desde, a_hasta)
        anterior = {
            "citas": fpac(Cita.objects.del_tenant_actual().filter(inicio__gte=a_ini, inicio__lt=a_fin)).count(),
            "atenciones": fpac(Atencion.objects.del_tenant_actual().filter(fecha__gte=a_ini, fecha__lt=a_fin)).count(),
            "leads": fsede(Lead.objects.del_tenant_actual().filter(creado_en__gte=a_ini, creado_en__lt=a_fin)).count(),
            "cobrado": float(
                fpac(Cobro.objects.del_tenant_actual()
                     .filter(fecha__gte=a_ini, fecha__lt=a_fin, estado=Cobro.Estado.PAGADO))
                .aggregate(s=Sum("monto"))["s"] or 0
            ),
        }

        return Response({
            "periodo": {"clave": periodo, "label": label, "desde": desde.isoformat(), "hasta": hasta.isoformat()},
            "sede": sede,
            "operacion": operacion,
            "captacion": captacion,
            "pacientes": pacientes,
            "demografia": demografia,
            "retencion": retencion,
            "atenciones": len(atenciones),
            "productividad": productividad,
            "finanzas": finanzas,
            "finanzas_activas": True,
            "diagnostico": diagnostico,
            "anterior": anterior,
        })
