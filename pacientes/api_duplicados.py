"""Calidad de datos: posibles pacientes duplicados.

Auditoría de set. 2026 sobre producción: 65 grupos de confianza ALTA, 76 fichas
de más sobre 1.646 pacientes, y 34 personas con su próxima cita en la ficha que
Coordinación no está mirando. El detector PROPONE; consolidar es siempre una
decisión humana y la ejecuta gerencia (ver core/permisos.py).

Vive aparte de `pacientes.api` a propósito: ahí ya conviven ocho ViewSets y
esto es una herramienta con su propio ciclo (detectar → comparar → dry-run →
consolidar → descartar).
"""
from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from core import continuidad as continuidad_mod
from core import permisos as permisos_mod
from core.tenant import get_clinica_actual

from . import duplicados as duplicados_mod
from . import fusion as fusion_mod
from .models import Cita, Paciente, RevisionDuplicado


def texto(v):
    return str(v or "").strip()


def flag(v):
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in ("1", "true", "si", "sí", "on")


def fecha(v):
    try:
        y, m, d = [int(x) for x in str(v).split("-")]
        return date(y, m, d)
    except (ValueError, TypeError, AttributeError):
        return None


def mask(v, cola=3):
    s = "".join(str(v or "").split())
    if not s:
        return ""
    return "*" * max(0, len(s) - cola) + s[-cola:]


def coincidencia(f, confianza, senales):
    """Lo mínimo para comparar dos personas en pantalla: sin historia clínica y
    con el contacto enmascarado. Es una comparación de identidad, no la ficha."""
    return {
        "id": f["id"],
        "nombre": f["nombre"],
        "sede": f["sede"],
        "documento": mask(f["numero_documento"]),
        "telefono": mask(duplicados_mod.norm_tel(f["telefono"])),
        "tutor_telefono": mask(duplicados_mod.norm_tel(f["tutor_telefono"])),
        "fecha_nacimiento": f["fecha_nacimiento"].isoformat() if f["fecha_nacimiento"] else None,
        "profesional": f["profesional__nombre"] or "",
        "provisional": f["provisional"],
        "confianza": confianza,
        "senales": senales,
    }


def _par(request, a_id, b_id):
    """Las dos fichas, con scope de clínica. (None, None, respuesta) si algo falla."""
    qs = Paciente.objects.del_tenant_actual()
    a = qs.filter(pk=a_id).first()
    b = qs.filter(pk=b_id).first()
    if a is None or b is None:
        return None, None, Response({"detail": "Paciente no encontrado."},
                                    status=status.HTTP_404_NOT_FOUND)
    if a.pk == b.pk:
        return None, None, Response({"detail": "Es la misma ficha."},
                                    status=status.HTTP_400_BAD_REQUEST)
    return a, b, None


class DuplicadosListaView(APIView):
    """GET /api/duplicados/?confianza=alta|media|baja

    Los candidatos con lo justo para triarlos: quiénes son, qué señales
    coinciden y cuánto está partida su continuidad.
    """

    permission_classes = [permisos_mod.PuedeRevisarDuplicados]

    def get(self, request):
        clinica = get_clinica_actual()
        confianza = texto(request.query_params.get("confianza")).lower() or duplicados_mod.ALTA
        if confianza not in (duplicados_mod.ALTA, duplicados_mod.MEDIA, duplicados_mod.BAJA):
            return Response({"detail": "Confianza no válida."}, status=status.HTTP_400_BAD_REQUEST)

        grupos, por_id = duplicados_mod.grupos(clinica, confianza=confianza)
        ids = [i for g, _s in grupos for i in g]
        citas = {}
        for c in (Cita.objects.filter(paciente_id__in=ids)
                  .values("paciente_id", "inicio", "estado", "n_sesion", "decision",
                          "especialidad", "notas").order_by("inicio")):
            citas.setdefault(c["paciente_id"], []).append(c)
        senales = continuidad_mod.senales_por_paciente(ids)
        ahora = timezone.now()

        out = []
        for miembros, sen in grupos:
            fichas = []
            for pid in miembros:
                f = por_id[pid]
                cs = citas.get(pid, [])
                asis = [c for c in cs if c["estado"] in continuidad_mod._ESTADOS_ASISTIDOS]
                fut = [c for c in cs if c["inicio"] >= ahora and c["estado"] != "cancelada"]
                pa = continuidad_mod.proceso_actual(asis, senales.get(pid, ())) if asis else None
                d = coincidencia(f, confianza, sen)
                d.update({
                    "citas": len(cs),
                    "sesiones": len(asis),
                    "proceso": pa["numero"] if pa else None,
                    "sesion": pa["n"] if pa else 0,
                    "proxima_cita": fut[0]["inicio"].date().isoformat() if fut else None,
                    "decisiones": [c["decision"] for c in cs if c["decision"]],
                    "creado_en": timezone.localtime(f["creado_en"]).date().isoformat(),
                })
                fichas.append(d)
            con_proxima = [f for f in fichas if f["proxima_cita"]]
            con_sesiones = [f for f in fichas if f["sesiones"]]
            out.append({
                "ids": miembros,
                "nombre": por_id[miembros[0]]["nombre"],
                "senales": sen,
                "fichas": fichas,
                # El daño concreto de este grupo, para poder priorizar el triaje.
                "impacto": {
                    "sesiones_repartidas": len(con_sesiones) > 1,
                    "proxima_en_una_sola": len(con_proxima) == 1 and len(fichas) > 1,
                    "decisiones_repartidas": (len(con_sesiones) > 1
                                              and sum(1 for f in fichas if f["decisiones"]) == 1),
                },
            })
        return Response({"confianza": confianza, "total": len(out), "grupos": out})


class DuplicadoAnalizarView(APIView):
    """POST /api/duplicados/analizar/ {principal, secundario, aceptar_sede_distinta}

    El DRY-RUN. No escribe nada: dice qué se conservaría, qué se heredaría, qué
    entra en conflicto, cuántas filas se moverían y cómo quedaría la continuidad.
    """

    permission_classes = [permisos_mod.PuedeRevisarDuplicados]

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        a, b, err = _par(request, d.get("principal"), d.get("secundario"))
        if err is not None:
            return err
        return Response(fusion_mod.analizar_fusion(
            a, b, aceptar_sede_distinta=flag(d.get("aceptar_sede_distinta"))))


class DuplicadoFusionarView(APIView):
    """POST /api/duplicados/fusionar/ {principal, secundario, motivo, confirmar}

    Consolida de verdad: mueve todo, recalcula continuidad y ELIMINA la ficha
    secundaria. Solo gerencia, y exige `confirmar` explícito.
    """

    permission_classes = [permisos_mod.PuedeFusionarPacientes]

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        if not flag(d.get("confirmar")):
            return Response(
                {"detail": "Falta la confirmación explícita de la consolidación."},
                status=status.HTTP_400_BAD_REQUEST)
        a, b, err = _par(request, d.get("principal"), d.get("secundario"))
        if err is not None:
            return err
        try:
            registro = fusion_mod.fusionar_pacientes(
                a, b, request.user, motivo=texto(d.get("motivo")),
                aceptar_sede_distinta=flag(d.get("aceptar_sede_distinta")))
        except fusion_mod.FusionBloqueada as e:
            return Response({"detail": "No se pudo consolidar.", "conflictos": e.motivos},
                            status=status.HTTP_409_CONFLICT)
        return Response({
            "ok": True,
            "paciente_id": registro.principal_id_original,
            "eliminado_id": registro.secundario_id_eliminado,
            "relaciones_movidas": registro.relaciones_movidas,
            "conflictos_resueltos": registro.conflictos_resueltos,
            "continuidad": registro.continuidad_despues,
            "registro_id": registro.pk,
        })


class DuplicadoDescartarView(APIView):
    """POST /api/duplicados/descartar/ {a, b, nota} — "no son la misma persona".

    Sin esto el detector vuelve a ofrecer los mismos homónimos cada vez y la
    pantalla deja de servir. No toca las fichas: solo registra la decisión.
    """

    permission_classes = [permisos_mod.PuedeRevisarDuplicados]

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        a, b, err = _par(request, d.get("a"), d.get("b"))
        if err is not None:
            return err
        menor, mayor = (a, b) if a.pk < b.pk else (b, a)
        obj, creado = RevisionDuplicado.objects.get_or_create(
            clinica=get_clinica_actual(), paciente_a=menor, paciente_b=mayor,
            defaults={"nota": texto(d.get("nota"))[:300], "revisado_por": request.user},
        )
        return Response({"ok": True, "creado": creado, "id": obj.pk})
