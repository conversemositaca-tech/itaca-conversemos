"""Consolidar dos fichas de la misma persona en UNA sola.

Fusionar no es "quedarse con una ficha y tirar la otra": es reunir toda la
información en una ficha maestra, trasladar TODAS las relaciones, recalcular el
estado con la historia completa, verificar que no quedó nada suelto y recién
entonces eliminar la ficha sobrante — todo dentro de una sola transacción. Si
algo falla en cualquier paso, no se fusionó nada.

Dos funciones, y solo la segunda escribe:

    analizar_fusion(principal, secundario)   -> el dry-run, 100 % de lectura
    fusionar_pacientes(principal, secundario, usuario, motivo)

La proyección de continuidad del dry-run NO reimplementa las reglas del Centro:
llama a `core.continuidad.evaluar_paciente` con la historia unida, que es la
misma función que produce la cola de verdad. Por eso lo que muestra la
proyección es exactamente lo que se verá después de fusionar.
"""
from django.db import models, transaction
from django.utils import timezone

from core import continuidad as cont
from core import gestion_continuidad as gestion_mod

from .duplicados import doc_valido, norm_nombre, tel_valido
from .models import (
    Cita, GestionContinuidad, HistorialContinuidad, Paciente,
    RegistroFusionPaciente, RevisionDuplicado, SeguimientoSesion,
)


class FusionBloqueada(Exception):
    """La fusión no puede continuar. `motivos` explica por qué, en claro."""

    def __init__(self, motivos):
        self.motivos = list(motivos)
        super().__init__("; ".join(self.motivos))


# --- Campos de la ficha maestra ---------------------------------------------
#
# Identidad y contacto: solo se heredan si el principal los tiene VACÍOS. Nunca
# se pisa un dato cargado con otro: eso sería decidir un conflicto en silencio.
CAMPOS_HEREDABLES = (
    "numero_documento", "tipo_documento", "fecha_nacimiento", "email", "direccion",
    "telefono", "genero", "tutor_nombre", "tutor_parentesco", "tutor_telefono",
    "tutor_documento", "profesional_id", "objetivo_principal",
)

# Texto clínico libre: si los DOS tienen contenido no se descarta ninguno —se
# unen con una marca—. Perder el resumen o los antecedentes que alguien escribió
# en la otra ficha sería exactamente el daño que la fusión viene a evitar.
CAMPOS_TEXTO = (
    "alergias", "antecedentes", "antecedentes_medicos", "antecedentes_familiares",
    "antecedentes_otros", "medicacion_habitual", "resumen_clinico", "notas_internas",
)

# Campos que describen la ATENCIÓN VIGENTE, no la identidad: manda la ficha que
# se usó más recientemente, porque el dato viejo no es un conflicto sino una
# etapa superada —quien aparece como "Consulta psicológica" en la ficha antigua
# y como "Terapia individual" en la reciente ya está en terapia—. Y si no se
# puede afirmar cuál es la más reciente, no se adivina: se pide revisión.
#
# Esta regla NO se extiende al documento, la fecha de nacimiento, el teléfono ni
# al resto de los datos maestros: ahí dos valores distintos son un conflicto de
# identidad, no una evolución del tratamiento.
CAMPOS_ATENCION_VIGENTE = ("especialidad_habitual",)

# Estado del proceso: se queda el más avanzado. Una ficha vieja nunca puede
# hacer retroceder el estado actual de la persona.
CAMPOS_MAXIMO = ("n_sesion", "sesiones_proceso")

# Estado "de hoy": lo dice la ficha que se usó más recientemente, no la más
# antigua ni la que tenga el id más bajo.
CAMPOS_DEL_MAS_RECIENTE = ("proceso", "frecuencia", "modalidad", "riesgo", "sede")

SEPARADOR_TEXTO = "\n\n--- de la ficha #%s (consolidada) ---\n"


# --- Relaciones --------------------------------------------------------------

def relaciones_entrantes():
    """Todo lo que apunta a Paciente, por introspección.

    A propósito NO es una lista escrita a mano: la anterior se quedó corta
    cuando llegó GestionContinuidad y el comando de fusión reventaba con
    ProtectedError. Lo que el modelo diga es lo que se mueve.
    """
    out = []
    for f in Paciente._meta.get_fields():
        if not (f.is_relation and f.auto_created and not f.concrete):
            continue
        out.append({
            "modelo": f.related_model,
            "campo": f.field.name,
            "label": f.related_model._meta.label,
            "tipo": type(f).__name__,
            "on_delete": getattr(f.field.remote_field.on_delete, "__name__", "?"),
        })
    out.sort(key=lambda r: r["label"])
    return out


def _campos_de_constraint(modelo, campo):
    """¿Hay alguna restricción de unicidad que incluya este campo?

    Si la hay, un `update()` masivo puede violarla al juntar las filas de las
    dos fichas, así que ese modelo EXIGE un manejo propio. Es la regla que hace
    que una relación nueva no pase desapercibida.
    """
    nombres = set()
    for c in modelo._meta.constraints:
        if isinstance(c, models.UniqueConstraint) and campo in (c.fields or ()):
            nombres.add(c.name)
    for grupo in (modelo._meta.unique_together or ()):
        if campo in grupo:
            nombres.add("unique_together%s" % (tuple(grupo),))
    return nombres


def _handlers():
    """Modelos con restricción de unicidad sobre `paciente` y cómo se resuelven.

    Si aparece una relación nueva con una restricción así y no está aquí,
    `plan_de_relaciones` bloquea la fusión en vez de intentar un update que la
    rompería. Es deliberado: una relación que nadie enseñó a mover no se mueve
    a ciegas.
    """
    return {
        GestionContinuidad._meta.label: _mover_gestiones,
        SeguimientoSesion._meta.label: _mover_seguimientos,
        RevisionDuplicado._meta.label: _mover_revisiones,
    }


def plan_de_relaciones(principal, secundario):
    """Qué se movería, cuánto, y qué no se sabe mover (bloquea). Solo lectura."""
    handlers = _handlers()
    plan, bloqueos = [], []
    for rel in relaciones_entrantes():
        modelo, campo = rel["modelo"], rel["campo"]
        if rel["tipo"] not in ("ManyToOneRel",):
            bloqueos.append(
                "No sé trasladar %s (%s): la herramienta solo mueve claves foráneas "
                "simples. Hay que darle un manejo propio antes de fusionar."
                % (rel["label"], rel["tipo"]))
            continue
        constraints = _campos_de_constraint(modelo, campo)
        if constraints and rel["label"] not in handlers:
            bloqueos.append(
                "%s tiene una restricción de unicidad sobre '%s' (%s) y no hay un "
                "manejo propio: moverlo en bloque podría romperla."
                % (rel["label"], campo, ", ".join(sorted(constraints))))
            continue
        n = modelo.objects.filter(**{campo: secundario}).count()
        plan.append({
            "label": rel["label"], "campo": campo, "filas": n,
            "on_delete": rel["on_delete"],
            "especial": rel["label"] in handlers,
        })
    return plan, bloqueos


def _mover_gestiones(principal, secundario, usuario):
    """Las gestiones de continuidad del secundario pasan al principal.

    El choque posible: `uniq_gestion_continuidad_abierta` permite UNA gestión
    abierta por (paciente, tipo, meta). Si las dos fichas tienen abierta la
    misma, se conserva la del principal —es la que la coordinación viene
    trabajando— y la del secundario se cierra ANTES de moverla, con su historial
    intacto y un asiento que dice por qué. Nada se borra: la gestión cerrada
    viaja igual y queda como historia del caso.
    """
    ahora = timezone.now()
    abiertas_principal = {
        (g.tipo, g.meta)
        for g in GestionContinuidad.objects.filter(paciente=principal, resuelto_en__isnull=True)
    }
    resueltas = []
    for g in GestionContinuidad.objects.filter(paciente=secundario, resuelto_en__isnull=True):
        if (g.tipo, g.meta) not in abiertas_principal:
            continue
        antes = g.estado_revision
        g.estado_revision = GestionContinuidad.Revision.RESUELTO
        g.resuelto_en, g.resuelto_por = ahora, usuario
        g.actualizado_en, g.actualizado_por = ahora, usuario
        g.save(update_fields=["estado_revision", "resuelto_en", "resuelto_por",
                              "actualizado_en", "actualizado_por"])
        HistorialContinuidad.objects.create(
            clinica=g.clinica, gestion=g, evento=HistorialContinuidad.Evento.ESTADO,
            antes=antes, despues="fusion_duplicado",
            origen=HistorialContinuidad.Origen.SISTEMA, usuario=usuario,
        )
        resueltas.append({"gestion": g.id, "tipo": g.tipo, "meta": g.meta,
                          "motivo": "ya había una gestión abierta igual en la ficha principal"})
    movidas = GestionContinuidad.objects.filter(paciente=secundario).update(paciente=principal)
    return movidas, resueltas


def _mover_seguimientos(principal, secundario, usuario):
    """El seguimiento semanal pasa al principal, semana por semana.

    `uniq_seg_paciente_semana` permite UNA fila por (paciente, año, mes, semana).
    Cuando las dos fichas tienen la misma semana no se descarta ninguna: se
    fusionan en la del principal quedándose con el número de sesión MÁS ALTO y
    con la etapa que venga con él —una ficha vieja nunca puede hacer retroceder
    el estado de la persona— y recién entonces se borra la fila redundante.
    """
    del usuario                                   # la firma es común a todos los handlers
    propias = {
        (s.anio, s.mes, s.semana): s
        for s in SeguimientoSesion.objects.filter(paciente=principal)
    }
    unidos = []
    for s in SeguimientoSesion.objects.filter(paciente=secundario):
        gemela = propias.get((s.anio, s.mes, s.semana))
        if gemela is None:
            continue
        campos = []
        if (s.n_sesion or 0) > (gemela.n_sesion or 0):
            gemela.n_sesion = s.n_sesion
            campos.append("n_sesion")
            if s.proceso:
                gemela.proceso = s.proceso
                campos.append("proceso")
        elif not gemela.proceso and s.proceso:
            gemela.proceso = s.proceso
            campos.append("proceso")
        if campos:
            gemela.save(update_fields=campos)
        unidos.append({"seguimiento": s.id,
                       "semana": "%s-%s S%s" % (s.anio, s.mes, s.semana),
                       "motivo": "las dos fichas tenían esa semana; se conserva la sesión más alta"})
        s.delete()
    movidos = SeguimientoSesion.objects.filter(paciente=secundario).update(paciente=principal)
    return movidos, unidos


def _mover_revisiones(principal, secundario, usuario):
    """Los 'no son la misma persona' que involucran al secundario se eliminan.

    Esa decisión se tomó sobre una ficha que deja de existir; arrastrarla al
    principal inventaría un descarte que nadie revisó (y podría crear un par
    consigo mismo). El detector volverá a proponer lo que corresponda.
    """
    n = RevisionDuplicado.objects.filter(
        models.Q(paciente_a=secundario) | models.Q(paciente_b=secundario)).count()
    RevisionDuplicado.objects.filter(
        models.Q(paciente_a=secundario) | models.Q(paciente_b=secundario)).delete()
    return n, ([{"revisiones_descartadas": n}] if n else [])


# --- Conflictos --------------------------------------------------------------

def conflictos(principal, secundario, aceptar_sede_distinta=False):
    """Lo que impide fusionar. Vacío = se puede (con confirmación humana)."""
    out = []
    if principal.pk == secundario.pk:
        out.append("Es la misma ficha: no hay nada que consolidar.")
        return out
    if principal.clinica_id != secundario.clinica_id:
        out.append("Las fichas son de clínicas distintas. No se fusionan nunca.")
    da, db = doc_valido(principal.numero_documento), doc_valido(secundario.numero_documento)
    if da and db and da != db:
        out.append("Tienen documentos válidos DISTINTOS: son dos personas.")
    fa, fb = principal.fecha_nacimiento, secundario.fecha_nacimiento
    if fa and fb and fa != fb:
        out.append("Tienen fechas de nacimiento distintas (%s y %s): requiere corregir "
                   "el dato antes de consolidar." % (fa, fb))
    sa, sb = (principal.sede or "").strip(), (secundario.sede or "").strip()
    if sa and sb and sa != sb and not aceptar_sede_distinta:
        out.append("Están en sedes distintas (%s y %s): requiere revisión humana "
                   "explícita." % (principal.get_sede_display(), secundario.get_sede_display()))
    return out


# --- Ficha maestra -----------------------------------------------------------

def _mas_reciente(principal, secundario):
    """(ficha usada más recientemente, ¿se puede afirmar?).

    Se decide por la última CITA, que es actividad real. `creado_en` NO sirve de
    desempate: los importadores lo reescribieron con la fecha de alta de
    AgendaPro, así que una ficha abierta después puede tener fecha de 2024. Si
    ninguna de las dos tiene citas, no hay con qué decidir y se dice así.
    """
    def ultima(p):
        return (Cita.objects.filter(paciente=p).order_by("-inicio")
                .values_list("inicio", flat=True).first())

    ua, ub = ultima(principal), ultima(secundario)
    if ua and ub:
        return (principal, True) if ua >= ub else (secundario, True)
    if ua:
        return principal, True
    if ub:
        return secundario, True
    return principal, False


def plan_de_campos(principal, secundario):
    """Qué queda en la ficha maestra y de dónde sale cada cosa. Solo lectura.

    Devuelve (cambios, detalle) donde `cambios` es {campo: valor_final} listo
    para aplicar y `detalle` explica cada decisión para mostrarla en el dry-run.
    """
    cambios, detalle = {}, []
    reciente, reciente_seguro = _mas_reciente(principal, secundario)

    for campo in CAMPOS_HEREDABLES:
        actual, otro = getattr(principal, campo), getattr(secundario, campo)
        if not actual and otro:
            cambios[campo] = otro
            detalle.append({"campo": campo, "accion": "hereda",
                            "origen": "secundario", "resumen": _resumen(campo, otro)})
        elif actual and otro and not _equivalentes(campo, actual, otro):
            detalle.append({"campo": campo, "accion": "conserva",
                            "origen": "principal", "resumen": _resumen(campo, actual),
                            "descartado": _resumen(campo, otro)})

    for campo in CAMPOS_TEXTO:
        actual = (getattr(principal, campo) or "").strip()
        otro = (getattr(secundario, campo) or "").strip()
        if not otro or otro == actual:
            continue
        if not actual:
            cambios[campo] = otro
            detalle.append({"campo": campo, "accion": "hereda", "origen": "secundario"})
        else:
            cambios[campo] = actual + (SEPARADOR_TEXTO % secundario.pk) + otro
            detalle.append({"campo": campo, "accion": "une",
                            "resumen": "se conservan los dos textos"})

    for campo in CAMPOS_ATENCION_VIGENTE:
        actual, otro = getattr(principal, campo), getattr(secundario, campo)
        if not otro or _equivalentes(campo, actual, otro):
            continue
        if not actual:                       # solo una tiene valor: es ese
            cambios[campo] = otro
            detalle.append({"campo": campo, "accion": "hereda", "origen": "secundario",
                            "resumen": _resumen(campo, otro)})
            continue
        if not reciente_seguro:              # ninguna tiene citas: no se adivina
            detalle.append({"campo": campo, "accion": "requiere revisión",
                            "resumen": "%s / %s" % (_resumen(campo, actual), _resumen(campo, otro))})
            continue
        vigente = getattr(reciente, campo)
        if vigente and not _equivalentes(campo, actual, vigente):
            cambios[campo] = vigente
            detalle.append({"campo": campo, "accion": "atención vigente",
                            "origen": "ficha #%s" % reciente.pk,
                            "resumen": "%s → %s" % (_resumen(campo, actual), _resumen(campo, vigente))})

    for campo in CAMPOS_MAXIMO:
        actual, otro = getattr(principal, campo) or 0, getattr(secundario, campo) or 0
        if otro > actual:
            cambios[campo] = otro
            detalle.append({"campo": campo, "accion": "toma el mayor",
                            "resumen": "%s → %s" % (actual, otro)})

    for campo in CAMPOS_DEL_MAS_RECIENTE:
        actual = getattr(principal, campo)
        del_reciente = getattr(reciente, campo)
        if del_reciente and del_reciente != actual:
            cambios[campo] = del_reciente
            detalle.append({"campo": campo, "accion": "estado más actual",
                            "origen": "ficha #%s" % reciente.pk,
                            "resumen": "%s → %s" % (actual or "(vacío)", del_reciente)})

    # Alertas clínicas: la unión, sin repetir.
    ta = [x.strip() for x in (principal.alertas or "").split(",") if x.strip()]
    tb = [x.strip() for x in (secundario.alertas or "").split(",") if x.strip()]
    union = ta + [x for x in tb if x not in ta]
    if union and ", ".join(union) != (principal.alertas or ""):
        cambios["alertas"] = ", ".join(union)[:300]
        detalle.append({"campo": "alertas", "accion": "une"})

    # El nombre más completo representa mejor a la persona (uno suele ser el
    # apodo con el que la registraron de apuro).
    if len(norm_nombre(secundario.nombre).split()) > len(norm_nombre(principal.nombre).split()):
        cambios["nombre"] = secundario.nombre
        detalle.append({"campo": "nombre", "accion": "toma el más completo",
                        "resumen": "%s → %s" % (principal.nombre, secundario.nombre)})

    # Si CUALQUIERA de las dos ya es paciente de verdad, la consolidada lo es:
    # una ficha provisional es "todavía no vino", y esta persona sí vino.
    if principal.provisional and not secundario.provisional:
        cambios["provisional"] = False
        detalle.append({"campo": "provisional", "accion": "deja de ser provisional"})

    return cambios, detalle


def _equivalentes(campo, a, b):
    """¿Los dos valores dicen lo MISMO? '+51 987 654 321' y '987654321' son el
    mismo número, y anunciarlos como conflicto sería ruido que esconde los
    conflictos de verdad."""
    if campo in ("telefono", "tutor_telefono"):
        return tel_valido(a) == tel_valido(b) and bool(tel_valido(a))
    if campo in ("numero_documento", "tutor_documento"):
        return doc_valido(a) == doc_valido(b) and bool(doc_valido(a))
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    return a == b


def _resumen(campo, valor):
    """El valor para mostrar en pantalla, enmascarado si es de contacto."""
    if valor in (None, ""):
        return "(vacío)"
    if campo in ("telefono", "tutor_telefono"):
        n = tel_valido(valor) or "".join(c for c in str(valor) if c.isdigit())
        return ("*" * max(0, len(n) - 3)) + n[-3:] if n else "(vacío)"
    if campo in ("numero_documento", "tutor_documento"):
        s = str(valor)
        return ("*" * max(0, len(s) - 3)) + s[-3:]
    if campo == "email":
        return "(tiene correo)"
    if campo == "profesional_id":
        from usuarios.models import Profesional
        p = Profesional.objects.filter(pk=valor).first()
        return p.nombre if p else str(valor)
    return str(valor)[:80]


def conflictos_de_campos(detalle):
    """Los campos que `plan_de_campos` no pudo resolver solo.

    Hoy es uno: la atención vigente cuando las dos fichas dicen cosas distintas
    y ninguna tiene citas con las que saber cuál manda. No se elige a la suerte:
    alguien corrige el dato en una de las dos y se vuelve a intentar.
    """
    return ["%s: las dos fichas dicen cosas distintas (%s) y no hay actividad "
            "con la que saber cuál está vigente. Corrige el campo en una de las "
            "dos antes de consolidar." % (d["campo"], d.get("resumen", ""))
            for d in detalle if d["accion"] == "requiere revisión"]


# --- Continuidad -------------------------------------------------------------

def _registro_cola(paciente, extra=None):
    """El paciente como lo arma `cola_de_continuidad` para evaluarlo."""
    r = {
        "id": paciente.pk, "nombre": paciente.nombre, "sede": paciente.sede,
        "sesiones_proceso": paciente.sesiones_proceso,
        "profesional_id": paciente.profesional_id,
        "profesional__nombre": paciente.profesional.nombre if paciente.profesional_id else None,
    }
    r.update(extra or {})
    return r


def _citas_de(ids):
    campos = ["id", "paciente_id", "n_sesion", "inicio", "estado", "decision",
              "especialidad", "notas"]
    asistidas = list(Cita.objects.filter(paciente_id__in=ids, estado__in=cont._ESTADOS_ASISTIDOS)
                     .values(*campos).order_by("inicio"))
    futuras = list(Cita.objects.filter(paciente_id__in=ids, inicio__gte=timezone.now())
                   .exclude(estado="cancelada").values(*campos).order_by("inicio"))
    return asistidas, futuras


def _foto_continuidad(r, asistidas, futuras, senales_pac, migrado):
    """Proceso, sesión, próxima cita y filas de la cola de UNA historia."""
    filas = cont.evaluar_paciente(r, asistidas, futuras, senales_pac=senales_pac,
                                  migrado=migrado, con_contexto=False)
    pa = cont.proceso_actual(asistidas, senales_pac) if asistidas else None
    return {
        "proceso": pa["numero"] if pa else None,
        "sesion": pa["n"] if pa else 0,
        "procesos_totales": pa["total"] if pa else 0,
        "anteriores_sin_cierre": pa["anteriores_sin_cierre"] if pa else 0,
        "numeracion_inconsistente": bool(pa["numeracion_inconsistente"]) if pa else False,
        "sesiones_asistidas": len(asistidas),
        "proxima_cita": futuras[0]["inicio"].date().isoformat() if futuras else None,
        "alertas": [{"estado": f["estado"], "meta": f["meta"], "dias": f["dias"]} for f in filas],
    }


def proyectar_continuidad(principal, secundario):
    """Continuidad antes (cada ficha) y después (la historia unida). Solo lectura."""
    senales = cont.senales_por_paciente([principal.pk, secundario.pk])
    asis, fut = _citas_de([principal.pk, secundario.pk])

    def parte(p):
        a = [c for c in asis if c["paciente_id"] == p.pk]
        f = [c for c in fut if c["paciente_id"] == p.pk]
        mig = bool(a or f) and all(
            (c["notas"] or "").startswith(cont.MARCADOR_IMPORTADO_AGENDAPRO) for c in (a + f))
        return _foto_continuidad(_registro_cola(p), a, f, senales.get(p.pk, ()), mig)

    cambios, _ = plan_de_campos(principal, secundario)
    # La proyección se evalúa con la ficha maestra, no con la actual: si la
    # sede o el total de sesiones del proceso cambian al consolidar, la cola lo
    # ve distinto y hay que mostrar eso, no una foto que no va a existir.
    extra = {}
    if "sede" in cambios:
        extra["sede"] = cambios["sede"]
    if "sesiones_proceso" in cambios:
        extra["sesiones_proceso"] = cambios["sesiones_proceso"]
    if "profesional_id" in cambios:
        from usuarios.models import Profesional
        prof = Profesional.objects.filter(pk=cambios["profesional_id"]).first()
        extra["profesional_id"] = cambios["profesional_id"]
        extra["profesional__nombre"] = prof.nombre if prof else None

    senales_union = tuple(s for pid in (principal.pk, secundario.pk) for s in senales.get(pid, ()))
    migrado_union = bool(asis or fut) and all(
        (c["notas"] or "").startswith(cont.MARCADOR_IMPORTADO_AGENDAPRO) for c in (asis + fut))
    despues = _foto_continuidad(_registro_cola(principal, extra), asis, fut,
                                senales_union, migrado_union)
    return {"principal": parte(principal), "secundario": parte(secundario), "despues": despues}


# --- Dry-run -----------------------------------------------------------------

def recomendar_principal(a, b):
    """Cuál conviene conservar, y por qué. Es una RECOMENDACIÓN: la persona que
    revisa elige, y el sistema nunca decide esto solo."""
    def puntaje(p):
        pts, razones = 0, []
        if not p.provisional:
            pts += 8
            razones.append("no es provisional")
        if doc_valido(p.numero_documento):
            pts += 6
            razones.append("tiene documento")
        if p.profesional_id:
            pts += 3
            razones.append("tiene psicólogo asignado")
        if p.fecha_nacimiento:
            pts += 2
            razones.append("tiene fecha de nacimiento")
        if p.sede:
            pts += 1
            razones.append("tiene sede")
        n = Cita.objects.filter(paciente=p).count()
        pts += min(n, 10)
        if n:
            razones.append("%d cita(s)" % n)
        return pts, razones

    pa, ra = puntaje(a)
    pb, rb = puntaje(b)
    if pa == pb:
        # Empate: se queda la más antigua, que es la que más referencias suele
        # tener fuera del sistema (boletas, mensajes, planillas de la sede).
        elegido = a if a.pk <= b.pk else b
        return elegido, ["empate en datos: se conserva la ficha más antigua (#%s)" % elegido.pk]
    return (a, ra) if pa > pb else (b, rb)


def analizar_fusion(principal, secundario, aceptar_sede_distinta=False):
    """El DRY-RUN. No escribe absolutamente nada.

    Devuelve todo lo que hace falta para decidir: qué se conserva, qué se
    hereda, qué entra en conflicto, cuántas filas se mueven, cómo queda la
    continuidad y qué id desaparecería.
    """
    bloqueos = conflictos(principal, secundario, aceptar_sede_distinta)
    plan_rel, bloqueos_rel = plan_de_relaciones(principal, secundario)
    bloqueos = bloqueos + bloqueos_rel
    cambios, detalle = plan_de_campos(principal, secundario)
    bloqueos = bloqueos + conflictos_de_campos(detalle)
    recomendado, razones = recomendar_principal(principal, secundario)

    return {
        "principal": _ficha_resumen(principal),
        "secundario": _ficha_resumen(secundario),
        "recomendado_id": recomendado.pk,
        "recomendado_porque": razones,
        "campos": detalle,
        "campos_a_escribir": sorted(cambios.keys()),
        "relaciones": plan_rel,
        "total_relaciones": sum(r["filas"] for r in plan_rel),
        "continuidad": proyectar_continuidad(principal, secundario),
        "conflictos": bloqueos,
        "puede_fusionar": not bloqueos,
        "id_que_desaparece": secundario.pk,
        "id_que_sobrevive": principal.pk,
    }


def _ficha_resumen(p):
    ultima = Cita.objects.filter(paciente=p).order_by("-inicio").values_list("inicio", flat=True).first()
    primera = Cita.objects.filter(paciente=p).order_by("inicio").values_list("inicio", flat=True).first()
    return {
        "id": p.pk,
        "nombre": p.nombre,
        "sede": p.sede,
        "sede_label": p.get_sede_display() if p.sede else "",
        "documento": _resumen("numero_documento", p.numero_documento) if p.numero_documento else "",
        "telefono": _resumen("telefono", p.telefono) if p.telefono else "",
        "tutor_telefono": _resumen("tutor_telefono", p.tutor_telefono) if p.tutor_telefono else "",
        "fecha_nacimiento": p.fecha_nacimiento.isoformat() if p.fecha_nacimiento else None,
        "provisional": p.provisional,
        "profesional": p.profesional.nombre if p.profesional_id else "",
        "creado_en": timezone.localtime(p.creado_en).date().isoformat(),
        "citas": Cita.objects.filter(paciente=p).count(),
        "primera_cita": primera.date().isoformat() if primera else None,
        "ultima_cita": ultima.date().isoformat() if ultima else None,
        "decisiones": list(Cita.objects.filter(paciente=p).exclude(decision="")
                           .values_list("decision", flat=True)),
    }


# --- Fusión real -------------------------------------------------------------

@transaction.atomic
def fusionar_pacientes(principal, secundario, usuario, motivo="", aceptar_sede_distinta=False):
    """Consolida secundario DENTRO de principal y elimina el secundario.

    Orden, y no es negociable: resolver choques → mover todo → completar la
    ficha maestra → reconciliar continuidad → verificar que no quedó ninguna
    referencia → dejar constancia → borrar. Cualquier error deshace todo
    (la transacción envuelve la función entera).
    """
    # Se re-valida DENTRO de la transacción: entre el dry-run que vio la
    # persona y este momento pudo cambiar cualquiera de las dos fichas.
    cambios, detalle = plan_de_campos(principal, secundario)
    bloqueos = conflictos(principal, secundario, aceptar_sede_distinta)
    bloqueos += plan_de_relaciones(principal, secundario)[1]
    bloqueos += conflictos_de_campos(detalle)
    if bloqueos:
        raise FusionBloqueada(bloqueos)

    antes = proyectar_continuidad(principal, secundario)
    handlers = _handlers()
    movidas, conflictos_resueltos = {}, []

    # 1) Modelos con restricción de unicidad: primero, y con su propia lógica.
    for label, handler in handlers.items():
        n, resueltos = handler(principal, secundario, usuario)
        if n:
            movidas[label] = n
        conflictos_resueltos.extend(resueltos)

    # 2) El resto: una clave foránea simple se mueve en bloque.
    for rel in relaciones_entrantes():
        if rel["label"] in handlers or rel["tipo"] != "ManyToOneRel":
            continue
        n = rel["modelo"].objects.filter(**{rel["campo"]: secundario}).update(
            **{rel["campo"]: principal})
        if n:
            movidas[rel["label"]] = movidas.get(rel["label"], 0) + n

    # 3) La ficha maestra: lo que el principal no tenía y el secundario sí
    #    (el plan se calculó arriba, con las dos fichas todavía intactas).
    if cambios:
        for campo, valor in cambios.items():
            setattr(principal, campo, valor)
        principal.save(update_fields=list(cambios.keys()))

    # 4) Verificar ANTES de borrar: si algo quedó apuntando al secundario, el
    #    borrado o lo arrastraría (CASCADE) o reventaría (PROTECT). Las dos
    #    cosas son inaceptables, así que se comprueba explícitamente.
    huerfanas = []
    for rel in relaciones_entrantes():
        if rel["tipo"] != "ManyToOneRel":
            continue
        n = rel["modelo"].objects.filter(**{rel["campo"]: secundario}).count()
        if n:
            huerfanas.append("%s: %d fila(s) siguen apuntando a #%s"
                             % (rel["label"], n, secundario.pk))
    if huerfanas:
        raise FusionBloqueada(huerfanas)

    # 5) Continuidad con la historia completa. Mover citas con update() NO
    #    dispara las señales de pacientes/signals.py, así que se llama a la
    #    reconciliación oficial a mano (nunca se reimplementa la regla).
    gestion_mod.reconciliar(principal.pk)

    principal.refresh_from_db()
    asis, fut = _citas_de([principal.pk])
    senales = cont.senales_por_paciente([principal.pk]).get(principal.pk, ())
    migrado = bool(asis or fut) and all(
        (c["notas"] or "").startswith(cont.MARCADOR_IMPORTADO_AGENDAPRO) for c in (asis + fut))
    despues = _foto_continuidad(_registro_cola(principal), asis, fut, senales, migrado)

    # 6) La constancia se crea ANTES del borrado: si el borrado falla, la
    #    transacción se va entera y no queda un registro de algo que no pasó.
    registro = RegistroFusionPaciente.objects.create(
        clinica=principal.clinica,
        principal=principal,
        principal_id_original=principal.pk,
        secundario_id_eliminado=secundario.pk,
        principal_nombre=principal.nombre[:200],
        secundario_nombre=secundario.nombre[:200],
        motivo=motivo or "",
        relaciones_movidas=movidas,
        campos_heredados=[d["campo"] for d in detalle if d["accion"] != "conserva"],
        conflictos_resueltos=conflictos_resueltos,
        continuidad_antes=antes,
        continuidad_despues=despues,
        fusionado_por=usuario,
    )

    # 7) Y recién ahora desaparece la ficha sobrante. Es la última operación.
    secundario.delete()
    return registro
