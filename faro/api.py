"""Panel del colegio y formulario de las familias, servidos por token.

Público y sin sesión: se entra por un enlace permanente, igual que la landing
de reservas. Hay tres enlaces distintos porque hay tres audiencias distintas
—dirección, aula y familias— y que se filtre uno no puede dar acceso a lo de
los otros dos.

QUÉ VE EL COLEGIO. Esto cambió en setiembre de 2026 por decisión de la
dirección clínica. Antes salía SIEMPRE agregado y nunca un estudiante
identificado. Ahora el colegio ve la lista nominal con el nivel de cada
estudiante y sus puntajes por instrumento, porque es el colegio quien acompaña
el día a día y no podía hacer nada con un porcentaje.

Lo que sigue sin salir son las RESPUESTAS una por una. El colegio lee "ASQ
positivo", no "¿has pensado en suicidarte? → sí". La diferencia no es
cosmética: con lo primero se convoca al estudiante a tutoría, con lo segundo
se lee en voz alta en una sala de profesores.

Este alcance tiene que coincidir, palabra por palabra, con lo que firma la
familia en el formulario de autorización. Si se amplía acá, se amplía allá, y
hay que volver a pedir firma.
"""
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.utils import timezone

from core import permisos
from . import instrumentos, registro
from .models import Alerta, Aplicacion, Autorizacion, clave_estudiante


class PanelFaroView(APIView):
    """GET /api/faro/<token>/ → lo que ve el colegio en su panel."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"

    def get(self, request, token):
        ap = Aplicacion.objects.filter(token=token).select_related("clinica").first()
        if ap is None:
            raise Http404

        # Con el tamizaje aún sin aplicar no hay nada que resumir, y decir "0%"
        # daría a entender que fue mal. Se dice que todavía no hay.
        hay_datos = ap.evaluados > 0

        return Response({
            "institucion": ap.institucion,
            "ciudad": ap.ciudad,
            "contacto": ap.contacto,
            "estado": ap.estado,
            "estado_label": ap.get_estado_display(),
            "fecha_aplicacion": ap.fecha_aplicacion.isoformat() if ap.fecha_aplicacion else None,
            "fecha_informe": ap.fecha_informe.isoformat() if ap.fecha_informe else None,
            "hay_datos": hay_datos,
            "matriculados": ap.matriculados,
            "autorizados": ap.autorizados,
            "evaluados": ap.evaluados,
            "participacion": ap.participacion,
            "grados": _por_grado(ap),
            "estudiantes": _nominal(ap),
            "resumen": _conteo(ap.respuestas.all()),
        })


# ── Cómo se le arma el panorama al colegio ─────────────────────────────────

def _conteo(resps):
    """Cuántos en cada nivel. Se cuenta sobre lo que hay, sin proyectar."""
    c = {"verde": 0, "ambar": 0, "rojo": 0, "evaluados": 0}
    for r in resps:
        c["evaluados"] += 1
        if r.nivel in c:
            c[r.nivel] += 1
    return c


def _por_grado(ap):
    """Agregados por grado, y dentro de cada grado por sección.

    Un director decide por grado y un tutor por sección, así que las dos
    miradas tienen que estar. Obligar a sumar secciones a mano para ver el
    grado es pedirle al lector que haga el trabajo del sistema.
    """
    grados = {}
    for r in ap.respuestas.all():
        g = grados.setdefault(r.grado or "Sin grado", {})
        g.setdefault(r.seccion or "—", []).append(r)
    salida = []
    for grado in sorted(grados):
        secciones = grados[grado]
        todas = [r for lista in secciones.values() for r in lista]
        salida.append({
            "grado": grado,
            **_conteo(todas),
            "secciones": [{"seccion": sec, **_conteo(secciones[sec])}
                          for sec in sorted(secciones)],
        })
    return salida


def _nominal(ap):
    """La lista con nombre y resultado de cada estudiante.

    Van el nivel y los puntajes por instrumento. NO van las respuestas una por
    una: eso se queda en el panel clínico. El motivo está en el docstring del
    módulo, y no se amplía sin cambiar antes el consentimiento.
    """
    return [{
        "nombre": r.nombre,
        "grado": r.grado,
        "seccion": r.seccion,
        "nivel": r.nivel,
        "phq_total": r.phq_total,
        "gad_total": r.gad_total,
        "asq_positivo": r.asq_positivo,
        "ebipq_rol": r.ebipq_rol,
        "ciber_rol": r.ciber_rol,
        "completa": r.completa,
        "fecha": r.creado_en.date().isoformat(),
    } for r in ap.respuestas.all().order_by("grado", "seccion", "nombre")]


class AutorizacionView(APIView):
    """GET y POST /api/faro/autorizacion/<token>/ — la firma de la familia.

    Reemplaza la hoja de papel. El apoderado lee el consentimiento, deja sus
    datos y decide. Se guarda también el NO: un colegio necesita saber cuántas
    familias se negaron, y borrar esas filas confundiría a quien no quiso con
    quien nunca respondió.

    Sin sesión y por token, como todo lo que es de cara al colegio. Este token
    es el de apoderados, distinto del de dirección y del de aula.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"

    # Se guarda con cada firma. Si el texto cambia, esto dice quién firmó cuál;
    # un consentimiento sin versión no sirve para defender nada después.
    VERSION = "2026-09-v3"

    def _aplicacion(self, token):
        ap = Aplicacion.objects.filter(token_apoderado=token).first()
        if ap is None:
            raise Http404
        return ap

    def get(self, request, token):
        ap = self._aplicacion(token)
        return Response({
            "institucion": ap.institucion,
            "ciudad": ap.ciudad,
            "abierto": ap.estado != Aplicacion.Estado.CERRADA,
            "version": self.VERSION,
        })

    def post(self, request, token):
        ap = self._aplicacion(token)
        if ap.estado == Aplicacion.Estado.CERRADA:
            return Response({"detail": "Este tamizaje ya cerró."},
                            status=status.HTTP_409_CONFLICT)

        d = request.data if isinstance(request.data, dict) else {}
        estudiante = str(d.get("estudiante") or "").strip()
        apoderado = str(d.get("apoderado") or "").strip()
        correo = str(d.get("correo") or "").strip()
        autoriza = bool(d.get("autoriza"))

        if len(estudiante) < 3:
            return Response({"detail": "Escriba el nombre completo del estudiante."},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(apoderado) < 3:
            return Response({"detail": "Escriba su nombre completo."},
                            status=status.HTTP_400_BAD_REQUEST)
        # El correo se le exige solo a quien autoriza: a quien dice que no no hay
        # nada que enviarle, y pedírselo sería un obstáculo para decir que no.
        if autoriza and "@" not in correo:
            return Response(
                {"detail": "Escriba un correo válido: ahí le enviaremos el resultado."},
                status=status.HTTP_400_BAD_REQUEST)

        grado = str(d.get("grado") or "").strip()[:30]
        seccion = str(d.get("seccion") or "").strip()[:10]

        # Una familia que reenvía el formulario corrige su respuesta, no crea
        # una segunda: la clave del estudiante es única por aplicación.
        Autorizacion.objects.update_or_create(
            aplicacion=ap, clave=clave_estudiante(estudiante, grado, seccion),
            defaults={
                "clinica": ap.clinica,
                "estudiante": estudiante[:200], "grado": grado, "seccion": seccion,
                "apoderado": apoderado[:200],
                "documento": str(d.get("documento") or "").strip()[:20],
                "parentesco": (str(d.get("parentesco") or "").strip()[:12] or "apoderado"),
                "correo": correo[:254],
                "celular": str(d.get("celular") or "").strip()[:30],
                "autoriza": autoriza, "version_texto": self.VERSION,
                "ip": (request.META.get("REMOTE_ADDR") or None),
            })
        return Response({"ok": True, "autoriza": autoriza}, status=status.HTTP_201_CREATED)


class CuestionarioView(APIView):
    """GET y POST /api/faro/cuestionario/<token>/ — el tamizaje del estudiante.

    Token DISTINTO del panel del colegio: este se reparte en un aula entera, así
    que se asume semipúblico. Con uno solo, cualquier alumno que lo copiara
    entraría al panel de la dirección.

    Sin límite de peticiones a propósito. Un colegio sale a internet por una
    sola IP, así que un aula de treinta respondiendo a la vez se vería como
    ráfaga y el límite cortaría la aplicación a media clase. El token hace de
    puerta; lo peor que permite su filtración son filas de basura, no acceso a
    datos de nadie.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def _aplicacion(self, token):
        ap = Aplicacion.objects.filter(token_estudiante=token).first()
        if ap is None:
            raise Http404
        return ap

    def get(self, request, token):
        ap = self._aplicacion(token)
        return Response({
            "institucion": ap.institucion,
            "abierto": ap.estado != Aplicacion.Estado.CERRADA,
            "items": [
                {"id": i["id"], "marco": i["marco"], "texto": i["texto"], "escala": i["escala"]}
                for i in instrumentos.ORDEN
            ],
        })

    def post(self, request, token):
        ap = self._aplicacion(token)
        if ap.estado == Aplicacion.Estado.CERRADA:
            return Response(
                {"detail": "Este tamizaje ya cerró. Avísale a tu tutor."},
                status=status.HTTP_409_CONFLICT)

        d = request.data if isinstance(request.data, dict) else {}
        nombre = str(d.get("nombre") or "").strip()
        if len(nombre) < 3:
            return Response({"detail": "Escribe tu nombre completo."},
                            status=status.HTTP_400_BAD_REQUEST)

        crudas = d.get("respuestas")
        if not isinstance(crudas, dict) or not crudas:
            return Response({"detail": "No recibimos tus respuestas. Intenta de nuevo."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Solo se guardan los identificadores que existen: lo que venga de más
        # se descarta en vez de quedar en la base sin significado.
        validos = {i["id"] for i in instrumentos.ORDEN}
        limpias = {k: v for k, v in crudas.items() if k in validos}

        registro.registrar(
            ap, nombre=nombre, respuestas=limpias,
            grado=str(d.get("grado") or ""), seccion=str(d.get("seccion") or ""),
            codigo=str(d.get("codigo") or ""))

        # La respuesta al estudiante NO dice en qué nivel quedó. Enterarse por
        # una pantalla de que uno "salió en rojo", solo y en un salón, es
        # exactamente lo que el protocolo evita: eso se conversa en persona.
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


# ── Panel interno del psicólogo ────────────────────────────────────────────
# Acceso restringido a psicólogo y gerencia (ver core/permisos.ROLES_FARO). Aquí
# SÍ aparecen nombres: el protocolo obliga a poder llegar al estudiante el mismo
# día. Lo que no aparece en ninguna parte es en el panel del colegio.

class _PanelBase(APIView):
    permission_classes = [permisos.PuedeVerFaro]


def _dato_alerta(a):
    r = a.respuesta
    return {
        "id": a.id,
        "institucion": r.aplicacion.institucion,
        "ciudad": r.aplicacion.ciudad,
        "estudiante": r.nombre,
        "grado": r.grado,
        "seccion": r.seccion,
        "motivos": a.motivos,
        "aviso": a.aviso,
        "aviso_label": a.get_aviso_display(),
        # Por qué falló. Sin esto el panel dice "el aviso falló" y deja a quien
        # lo lee sin nada que hacer al respecto.
        "aviso_detalle": a.aviso_detalle,
        "avisado_en": a.avisado_en.isoformat() if a.avisado_en else None,
        "atendida": a.atendida,
        "atendida_en": a.atendida_en.isoformat() if a.atendida_en else None,
        "atendida_por": getattr(a.atendida_por, "nombre", "") or getattr(a.atendida_por, "email", ""),
        "acciones": a.acciones,
        "creado_en": a.creado_en.isoformat(),
        "phq_total": r.phq_total,
        "gad_total": r.gad_total,
        "asq_positivo": r.asq_positivo,
        "ebipq_rol": r.ebipq_rol,
        "ciber_rol": r.ciber_rol,
        "completa": r.completa,
    }


class AlertasView(_PanelBase):
    """GET /api/faro/panel/alertas/ → los casos rojos, sin atender primero.

    El orden no es por fecha sino por atención pendiente: quien abre esto está
    buscando a quién le falta llamar, no leyendo historia.
    """

    def get(self, request):
        qs = (Alerta.objects.del_tenant_actual()
              .select_related("respuesta", "respuesta__aplicacion", "atendida_por")
              .order_by("atendida", "-creado_en"))
        if request.query_params.get("pendientes") == "1":
            qs = qs.filter(atendida=False)
        datos = [_dato_alerta(a) for a in qs[:300]]
        return Response({
            "alertas": datos,
            "pendientes": sum(1 for d in datos if not d["atendida"]),
            "sin_avisar": sum(1 for d in datos
                              if d["aviso"] in ("pendiente", "fallido", "sin_canal")
                              and not d["atendida"]),
        })


class AtenderAlertaView(_PanelBase):
    """POST /api/faro/panel/alertas/<pk>/ → registrar qué se hizo con el caso.

    Exige texto. Marcar "atendida" sin decir qué se hizo deja el registro sin
    valor justo donde más falta hace: si alguien cuestiona la actuación meses
    después, una casilla marcada no sostiene nada.
    """

    def post(self, request, pk):
        a = (Alerta.objects.del_tenant_actual()
             .select_related("respuesta", "respuesta__aplicacion").filter(pk=pk).first())
        if a is None:
            raise Http404
        acciones = str((request.data or {}).get("acciones") or "").strip()
        if len(acciones) < 10:
            return Response(
                {"detail": "Escribe qué se hizo con el caso: con quién se habló, "
                           "qué se acordó y qué derivación hubo."},
                status=status.HTTP_400_BAD_REQUEST)
        a.acciones = acciones[:4000]
        a.atendida = True
        a.atendida_en = timezone.now()
        a.atendida_por = request.user
        a.save(update_fields=["acciones", "atendida", "atendida_en", "atendida_por"])
        return Response(_dato_alerta(a))


class ResultadosView(_PanelBase):
    """GET /api/faro/panel/resultados/<pk>/ → la hoja de resultados de un colegio.

    Sale como datos y no como archivo: el panel ya arma sus exportables con
    exceljs en el navegador, y repetir esa maquinaria en el servidor solo para
    Faro sería una segunda forma de hacer lo mismo.
    """

    def get(self, request, pk):
        ap = Aplicacion.objects.del_tenant_actual().filter(pk=pk).first()
        if ap is None:
            raise Http404
        filas = []
        for r in ap.respuestas.select_related("alerta").order_by("grado", "seccion", "nombre"):
            filas.append({
                "estudiante": r.nombre, "grado": r.grado, "seccion": r.seccion,
                "codigo": r.codigo, "nivel": r.nivel,
                "phq_total": r.phq_total, "gad_total": r.gad_total,
                "asq_positivo": "Sí" if r.asq_positivo else "No",
                "ebipq_rol": r.ebipq_rol,
                "ciber_rol": r.ciber_rol,
                "completa": "Sí" if r.completa else "No",
                "motivos": " · ".join(r.motivos),
                "fecha": r.creado_en.date().isoformat(),
            })
        return Response({
            "institucion": ap.institucion, "ciudad": ap.ciudad,
            "estado": ap.get_estado_display(), "filas": filas,
            "totales": {
                "evaluados": len(filas),
                "rojo": sum(1 for f in filas if f["nivel"] == "rojo"),
                "ambar": sum(1 for f in filas if f["nivel"] == "ambar"),
                "verde": sum(1 for f in filas if f["nivel"] == "verde"),
                "incompletos": sum(1 for f in filas if f["completa"] == "No"),
            },
        })


def _dato_aplicacion(ap, base, rs=None):
    rs = ap.respuestas.all() if rs is None else rs
    return {
        "id": ap.id,
        "institucion": ap.institucion,
        "ciudad": ap.ciudad,
        "contacto": ap.contacto,
        "estado": ap.estado,
        "estado_label": ap.get_estado_display(),
        "avisar_whatsapp": ap.avisar_whatsapp,
        "enlace_estudiante": f"{base}/faro/t/{ap.token_estudiante}",
        "enlace_colegio": f"{base}/faro/{ap.token}",
        "autorizados": ap.autorizados,
        "evaluados": rs.count(),
        "rojos": rs.filter(nivel="rojo").count(),
        "ambares": rs.filter(nivel="ambar").count(),
    }


class AplicacionesView(_PanelBase):
    """Los colegios y sus dos enlaces. GET los lista, POST crea uno.

    Devuelve los tokens porque el psicólogo necesita repartirlos: el del
    estudiante va al aula, el del panel va a la dirección. Son distintos a
    propósito y aquí se ven juntos para no confundirlos al copiar.

    Crear se hace desde aquí y no desde el admin de Django a propósito. El
    admin exige `is_staff`, que es una llave de servidor —abre todas las tablas
    del sistema, no solo las de Faro— y nadie debería necesitarla para abrir un
    colegio. Además el admin no respeta el filtro por clínica: la aplicación
    creada ahí puede quedar colgada del tenant equivocado sin que se note.
    """

    def get(self, request):
        base = request.build_absolute_uri("/").rstrip("/")
        salida = [_dato_aplicacion(ap, base)
                  for ap in Aplicacion.objects.del_tenant_actual().order_by("-creado_en")[:200]]
        return Response({"aplicaciones": salida})

    def post(self, request):
        d = request.data or {}
        institucion = str(d.get("institucion") or "").strip()
        if len(institucion) < 3:
            return Response({"detail": "Escribe el nombre de la institución educativa."},
                            status=status.HTTP_400_BAD_REQUEST)

        estado = str(d.get("estado") or "").strip() or Aplicacion.Estado.PREPARANDO
        if estado not in Aplicacion.Estado.values:
            return Response({"detail": "Ese estado no existe."},
                            status=status.HTTP_400_BAD_REQUEST)

        # `autorizados` entra porque de él sale el % de participación, y un
        # colegio que empieza con 0 mostraría participación vacía todo el ciclo.
        try:
            autorizados = max(0, int(d.get("autorizados") or 0))
            matriculados = d.get("matriculados")
            matriculados = int(matriculados) if str(matriculados or "").strip() else None
        except (TypeError, ValueError):
            return Response({"detail": "Los totales deben ser números."},
                            status=status.HTTP_400_BAD_REQUEST)

        ap = Aplicacion.objects.create(
            clinica=request.user.clinica,
            institucion=institucion,
            ciudad=str(d.get("ciudad") or "").strip(),
            contacto=str(d.get("contacto") or "").strip(),
            estado=estado,
            autorizados=autorizados,
            matriculados=matriculados,
            avisar_whatsapp=str(d.get("avisar_whatsapp") or "").strip(),
            notas=str(d.get("notas") or "").strip(),
        )
        base = request.build_absolute_uri("/").rstrip("/")
        return Response(_dato_aplicacion(ap, base), status=status.HTTP_201_CREATED)
