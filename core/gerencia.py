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

from core import continuidad as continuidad_mod
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
        out = {
            "leads_nuevos": leads_nuevos, "leads_hoy": leads_hoy,
            "sin_proxima": sin_proxima, "es_admin": es_admin,
        }

        # --- Continuidad terapéutica: riesgo de abandono (S3) y fin de bloque
        # sin decisión registrada. El psicólogo ve solo SUS pacientes; la
        # coordinadora (asistente) solo los de SU sede; admin, todos.
        rol = getattr(request.user, "rol", None)
        ficha = None
        if rol == "medico":
            from usuarios.models import Profesional
            ficha = Profesional.objects.filter(usuario=request.user).first()
        pac_cont = Paciente.objects.del_tenant_actual()
        if rol == "medico":
            pac_cont = pac_cont.filter(profesional=ficha) if ficha else pac_cont.none()
        elif rol == "comercial":
            pac_cont = pac_cont.none()
        elif rol == "asistente":
            # Antes veía pacientes de TODAS las sedes en esta tarjeta (Yazmín en
            # Piura veía también los de Lima, y viceversa con Ayvi) aunque el
            # resto del panel (la meta comercial, más abajo) ya escopa por sede.
            sede_usuario = getattr(request.user, "sede", "") or ""
            if sede_usuario:
                pac_cont = pac_cont.filter(sede=sede_usuario)

        filas = list(pac_cont.filter(n_sesion__gt=0)
                     .exclude(frecuencia__in=["alta", "en_pausa"])
                     .values("id", "nombre", "n_sesion", "sesiones_proceso"))
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

        continuidad, riesgo_abandono = [], []
        for r in filas:
            n = r["n_sesion"] or 0
            alertas = continuidad_mod.evaluar(
                n, r["sesiones_proceso"] or 0, r["id"] in con_futura_ids,
                ultima_decision.get(r["id"], ""), None,  # frecuencia ya excluida en el queryset
            )
            if continuidad_mod.RIESGO_ABANDONO_S3 in alertas:
                riesgo_abandono.append({"id": r["id"], "nombre": r["nombre"], "n_sesion": n})
            if continuidad_mod.FIN_BLOQUE_SIN_DECISION in alertas:
                meta = continuidad_mod.proxima_meta(n, r["sesiones_proceso"] or 0)
                continuidad.append({"id": r["id"], "nombre": r["nombre"], "n_sesion": n, "meta": meta})
        continuidad.sort(key=lambda x: (x["meta"] - x["n_sesion"], x["nombre"]))
        riesgo_abandono.sort(key=lambda x: x["nombre"])
        out["por_continuidad"] = continuidad[:30]
        out["por_continuidad_total"] = len(continuidad)
        out["riesgo_abandono"] = riesgo_abandono[:30]
        out["riesgo_abandono_total"] = len(riesgo_abandono)

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
        if rol in ("admin", "asistente"):
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
            else:
                # Gerencia: una meta POR SEDE (no sumadas), cada una hacia su objetivo.
                out["metas"] = [_meta_de(s) for s, _ in Paciente.Sede.choices]

        # Recordatorios del día. El envío corre desde una tarea programada FUERA del
        # servidor, así que si un día no se dispara —el equipo apagado, un error— hoy
        # nadie se entera hasta que un paciente no llega. Esto lo pone a la vista de
        # coordinación, pero solo a media mañana: antes de las 9 es normal que aún no
        # hayan salido y avisar sería ruido.
        if rol in ("admin", "asistente"):
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

        if es_admin:
            cobros = Cobro.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin)
            out["ingresos_hoy"] = float(cobros.filter(estado=Cobro.Estado.PAGADO).aggregate(s=Sum("monto"))["s"] or 0)
            out["pendiente_hoy"] = float(cobros.filter(estado=Cobro.Estado.PENDIENTE).aggregate(s=Sum("monto"))["s"] or 0)

            # Eliminaciones recientes (citas/pagos) — la gerencia se entera.
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

        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            return Response({"detail": "Solo el gerente (admin) puede ver este panel."},
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
