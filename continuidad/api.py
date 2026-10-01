"""API de continuidad formal (fase 2).

    GET  /api/continuidad/paciente/<id>/procesos/   estado, historia y acciones
    POST /api/continuidad/paciente/<id>/transicion/ registrar un evento
    GET  /api/continuidad/motivos/                  catálogo activo (+ profesionales)
    GET  /api/continuidad/revision/                 lista para revisión

Sin datos de contacto ni clínicos: nombre del paciente (quien entra aquí ya
lo ve en su ficha), fechas, estados, motivos operativos.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import continuidad as continuidad_mod
from core import direccion_clinica as dc
from core.permisos import (
    ROLES_REVISAN_CONTINUIDAD, ROLES_VEN_CONTINUIDAD, puede_registrar_continuidad,
)
from core.tenant import get_clinica_actual

from . import metricas
from .inferencia import NO_APLICA, ETIQUETAS_OPERATIVAS, desviacion_frecuencia, evaluar_estado_inferido
from .models import Estado, EventoContinuidad, Frecuencia, MotivoContinuidad, ProcesoContinuidad, TipoEvento
from .motivos import asegurar_catalogo
from .reconciliacion import reconciliar_paciente
from .servicios import (
    ConflictoEstado, ErrorTransicion, acciones_disponibles, motivo_vigente, transicionar_proceso,
)

ESTADO_LABEL = dict(Estado.choices)
FRECUENCIA_LABEL = dict(Frecuencia.choices)
FUENTE_LABEL = {dc.FUENTE_FORMAL: "Registrado", dc.FUENTE_LEGACY: "Evidencia anterior (DP o ficha)",
                dc.FUENTE_INFERIDA: "Inferido de la agenda"}


def _rol(request):
    return getattr(request.user, "rol", None)


def _denegado(msg="Tu perfil no puede ver la continuidad de este paciente."):
    return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)


def _paciente(request, pk):
    from pacientes.models import Paciente
    qs = continuidad_mod.pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
    return qs.filter(pk=pk).first()


def _fecha(txt, campo):
    txt = (txt or "").strip() if isinstance(txt, str) else txt
    if not txt:
        return None
    try:
        return date.fromisoformat(txt)
    except (TypeError, ValueError):
        raise ErrorTransicion(f"Fecha inválida en «{campo}» (AAAA-MM-DD).") from None


def _evento(e, correcciones):
    m = motivo_vigente(e, correcciones)
    return {
        "uuid": str(e.uuid), "tipo": e.tipo, "tipo_label": TipoEvento(e.tipo).label,
        "fecha_efectiva": e.fecha_efectiva.isoformat(),
        "estado_anterior": e.estado_anterior, "estado_nuevo": e.estado_nuevo,
        "estado_nuevo_label": ESTADO_LABEL.get(e.estado_nuevo, ""),
        # Fin de pausa: lo representa el evento que SALE de la pausa.
        "finaliza_pausa": e.estado_anterior == Estado.PAUSA and e.estado_nuevo != Estado.PAUSA,
        "motivo": {"codigo": m.codigo, "nombre": m.nombre, "categoria": m.get_categoria_display()} if m else None,
        "motivo_corregido": bool(correcciones.get(e.id)),
        "corrige": str(e.corrige.uuid) if e.corrige_id else None,
        "detalle_operativo": e.detalle_operativo,
        "fecha_revision": e.fecha_revision.isoformat() if e.fecha_revision else None,
        "profesional_anterior": e.profesional_anterior.nombre if e.profesional_anterior_id else None,
        "profesional_nuevo": e.profesional_nuevo.nombre if e.profesional_nuevo_id else None,
        "frecuencia_anterior": FRECUENCIA_LABEL.get(e.frecuencia_anterior, ""),
        "frecuencia_nueva": FRECUENCIA_LABEL.get(e.frecuencia_nueva, ""),
        "intervalo_nuevo_dias": e.intervalo_nuevo_dias,
        "registrado_por": getattr(e.registrado_por, "nombre", "") or ("Sistema" if not e.registrado_por_id else ""),
        "origen": e.get_origen_display(),
    }


def _proceso(p, puede_registrar, dias_abandono=dc.DIAS_ABANDONO):
    fila = p.get("formal")
    formal = p["estado_formal"]
    operativo = evaluar_estado_inferido(
        estado_formal=formal, tiene_proxima=p.get("tiene_proxima"), dias_sin_sesion=p["dias_sin_sesion"],
        dias_abandono=dias_abandono, evidencia_legacy=p.get("fuente_estado") == dc.FUENTE_LEGACY,
    ) if p["actual"] else NO_APLICA
    return {
        "numero": p["numero"],
        "actual": p["actual"],
        "uuid": str(fila.uuid) if fila else None,
        "ancla": p["sesiones"][0]["id"],
        "estado_formal": formal,
        "estado_formal_label": ESTADO_LABEL[formal],
        "fecha_estado": fila.fecha_estado.isoformat() if fila and fila.fecha_estado else None,
        "clasificacion": p["estado"],
        "clasificacion_fuente": FUENTE_LABEL[p["fuente_estado"]],
        "estado_operativo": operativo,
        "estado_operativo_label": ETIQUETAS_OPERATIVAS[operativo],
        "inicio": p["s1"].isoformat(),
        "ultima_sesion": p["ultima"].isoformat(),
        "sesiones": p["n"],
        "dias_sin_sesion": p["dias_sin_sesion"],
        "proxima_cita": timezone.localtime(p["proxima"]).date().isoformat() if p.get("proxima") else None,
        "psicologo_s1": p["psicologo_nombre"],
        "frecuencia": {
            "efectiva": p["frecuencia"], "label": FRECUENCIA_LABEL[p["frecuencia"]],
            "intervalo_dias": p["intervalo"], "fuente": p["frecuencia_fuente"],
            "del_proceso": fila.frecuencia_esperada if fila else Frecuencia.NO_DEFINIDA,
            "intervalo_personalizado": fila.intervalo_personalizado_dias if fila else None,
        },
        "desviacion": desviacion_frecuencia(p["dias_sin_sesion"], p["intervalo"]) if p["actual"] else None,
        "requiere_revision": fila.get_requiere_revision_display() if fila and fila.requiere_revision else "",
        "eventos": [_evento(e, p["correcciones"]) for e in p.get("eventos", [])],
        "acciones": [{"tipo": t, "label": TipoEvento(t).label} for t in acciones_disponibles(
            fila or ProcesoContinuidad(estado=Estado.SIN_REGISTRO))] if puede_registrar else [],
    }


def procesos_de_paciente(paciente, puede_registrar):
    from pacientes.models import Paciente
    procesos = dc.construir_procesos(Paciente.objects.filter(pk=paciente.pk))
    metricas.anotar_eventos(procesos)
    # select_related para nombres en el historial, sin una consulta por evento.
    ids = [e.id for p in procesos for e in p.get("eventos", [])]
    if ids:
        ricos = {e.id: e for e in EventoContinuidad.objects.filter(id__in=ids).select_related(
            "motivo", "registrado_por", "profesional_anterior", "profesional_nuevo", "corrige")}
        for p in procesos:
            p["eventos"] = [ricos[e.id] for e in p["eventos"]]
    procesos.sort(key=lambda p: -p["numero"])
    return [_proceso(p, puede_registrar) for p in procesos]


class ProcesosPacienteView(APIView):
    def get(self, request, pk):
        if _rol(request) not in ROLES_VEN_CONTINUIDAD:
            return _denegado()
        paciente = _paciente(request, pk)
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        puede = puede_registrar_continuidad(request.user)
        return Response({
            "paciente": paciente.pk,
            "puede_registrar": puede,
            "procesos": procesos_de_paciente(paciente, puede),
        })


class TransicionView(APIView):
    def post(self, request, pk):
        from usuarios.models import Profesional

        if not puede_registrar_continuidad(request.user):
            return _denegado("Tu perfil no puede registrar estados de continuidad.")
        paciente = _paciente(request, pk)
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data
        clinica = get_clinica_actual()
        asegurar_catalogo(clinica)
        try:
            with transaction.atomic():
                pares = reconciliar_paciente(paciente.pk)
                uuid_txt, ancla = str(d.get("proceso") or ""), d.get("ancla")
                if uuid_txt:
                    fila = next((f for _, f in pares if str(f.uuid) == uuid_txt), None)
                elif ancla:
                    fila = next((f for _, f in pares if f.cita_inicio_id == int(ancla)), None)
                else:  # sin indicar: el proceso en curso (el más reciente)
                    fila = pares[-1][1] if pares else None
                if fila is None:
                    raise ErrorTransicion("No se encontró ese proceso: recarga la ficha.")
                motivo = None
                if d.get("motivo"):
                    motivo = MotivoContinuidad.objects.filter(clinica=clinica, codigo=d["motivo"]).first()
                    if motivo is None:
                        raise ErrorTransicion("Ese motivo no existe.")
                prof = None
                if d.get("profesional_nuevo"):
                    prof = Profesional.objects.filter(clinica=clinica, pk=d["profesional_nuevo"]).first()
                    if prof is None:
                        raise ErrorTransicion("Ese profesional no existe.")
                corrige = None
                if d.get("corrige"):
                    corrige = EventoContinuidad.objects.filter(clinica=clinica, uuid=d["corrige"]).first()
                intervalo = d.get("intervalo_dias")
                res = transicionar_proceso(
                    fila, d.get("evento"), request.user, motivo=motivo,
                    fecha_efectiva=_fecha(d.get("fecha_efectiva"), "fecha"),
                    detalle=d.get("detalle_operativo") or "",
                    fecha_revision=_fecha(d.get("fecha_revision"), "fecha de revisión"),
                    profesional_nuevo=prof, frecuencia=d.get("frecuencia") or None,
                    intervalo_dias=int(intervalo) if intervalo not in (None, "") else None,
                    corrige=corrige, estado_esperado=d.get("estado_esperado") or None,
                    clave_idempotencia=d.get("clave_idempotencia"),
                )
        except ConflictoEstado as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except (ErrorTransicion, ValueError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"repetido": res.repetido, "evento": str(res.evento.uuid), "estado": res.proceso.estado,
             "procesos": procesos_de_paciente(paciente, True)},
            status=status.HTTP_200_OK if res.repetido else status.HTTP_201_CREATED)


class MotivosView(APIView):
    def get(self, request):
        from usuarios.models import Profesional

        if _rol(request) not in ROLES_VEN_CONTINUIDAD:
            return _denegado()
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        asegurar_catalogo(clinica)
        motivos = MotivoContinuidad.objects.filter(clinica=clinica, activo=True).order_by("orden", "nombre")
        out = {"motivos": [{
            "codigo": m.codigo, "nombre": m.nombre, "categoria": m.categoria,
            "categoria_label": m.get_categoria_display(),
            "aplica": [k for k, flag in (("pausa_iniciada", m.aplica_a_pausa), ("alta", m.aplica_a_alta),
                                         ("abandono_confirmado", m.aplica_a_abandono), ("cierre", m.aplica_a_cierre),
                                         ("cambio_profesional", m.aplica_a_cambio_profesional)) if flag],
        } for m in motivos],
            "frecuencias": [{"clave": k, "label": v} for k, v in Frecuencia.choices]}
        if puede_registrar_continuidad(request.user):
            out["profesionales"] = list(Profesional.objects.filter(clinica=clinica, activo=True)
                                        .order_by("nombre").values("id", "nombre"))
        return Response(out)


class RevisionView(APIView):
    """Procesos para revisión de continuidad. Solo información."""

    def get(self, request):
        from pacientes.models import Paciente

        if _rol(request) not in ROLES_REVISAN_CONTINUIDAD:
            return _denegado("Tu perfil no ve la lista de revisión.")
        pacientes = continuidad_mod.pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
        sede = (request.query_params.get("sede") or "").strip().lower()
        if sede in ("lima", "piura"):
            pacientes = pacientes.filter(sede=sede)
        procesos = dc.construir_procesos(pacientes)
        metricas.anotar_eventos(procesos)
        items = metricas.revision(procesos)
        nombres = dict(Paciente.objects.filter(id__in={i["proceso"]["paciente_id"] for i in items[:200]})
                       .values_list("id", "nombre"))
        return Response({
            "resumen": metricas.resumen_revision(items),
            "items": [{
                "paciente_id": i["proceso"]["paciente_id"],
                "paciente": nombres.get(i["proceso"]["paciente_id"], ""),
                "proceso": str(i["proceso"]["formal"].uuid) if i["proceso"].get("formal") else None,
                "sede": i["proceso"]["sede"],
                "psicologo": i["proceso"]["psicologo_nombre"],
                "estado_formal": ESTADO_LABEL[i["proceso"]["estado_formal"]],
                "dias_sin_sesion": i["proceso"]["dias_sin_sesion"],
                "frecuencia": FRECUENCIA_LABEL[i["proceso"]["frecuencia"]],
                "desviacion": i["desviacion"],
                "razones": [{"clave": r, "label": metricas.RAZONES[r]} for r in i["razones"]],
            } for i in items[:200]],
            "mostrados": min(200, len(items)),
        })
