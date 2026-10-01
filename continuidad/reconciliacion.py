"""Une los procesos DETECTADOS (tramos de `segmentar_procesos`) con los
procesos PERSISTIDOS (`ProcesoContinuidad`), conservando su identidad.

Criterio de emparejamiento, en orden:

1. Ancla. Cada proceso persistido guarda `cita_inicio`, su primera sesión. Si
   esa cita sigue siendo una sesión de algún tramo, ese es su tramo, aunque
   ya no sea la primera (se agregó una sesión anterior) o le hayan corregido
   la fecha. Es la señal fuerte: el id de una cita no cambia al editarla.
2. Si dos persistidos caen en el MISMO tramo (alguien corrigió la numeración y
   dos procesos pasaron a ser uno) se queda el que tiene el ancla en la S1 o,
   si ninguno, el más antiguo; el otro queda marcado `fusion_potencial`.
   Nunca se fusionan ni se borra su historia.
3. Fecha. Un persistido cuyo ancla ya no es sesión de ningún tramo (la cita se
   anuló o se borró) busca un tramo libre que empiece a ±`TOLERANCIA_DIAS`
   de su `fecha_inicio`. Con UN solo candidato se re-ancla; con varios queda
   `inicio_ambiguo`; con ninguno, `sin_tramo`. Las tres marcas son para
   revisión humana y se recalculan en cada reconciliación.
4. Un tramo sin persistido es un proceso nuevo. Si empieza antes del fin
   observado de otro proceso del mismo paciente (una corrección partió un
   proceso en dos) se crea marcado `division_potencial`.

La versión de solo lectura (`anotar_formales`) usa el mismo emparejamiento sin
escribir: es la que lee Dirección Clínica. La que escribe
(`reconciliar_paciente`) corre al guardar citas, al registrar un evento y en
la carga histórica.
"""
import logging
from datetime import date

from django.conf import settings
from django.db import transaction

from .models import Estado, EventoContinuidad, Origen, ProcesoContinuidad, TipoEvento

log = logging.getLogger(__name__)

TOLERANCIA_DIAS = 14
R = ProcesoContinuidad.Revision


def registro_formal_desde(clinica_id):
    """Desde qué fecha de S1 un proceso nuevo nace ACTIVO (con evento de
    inicio). Lo anterior nace "sin estado formal": no se le inventa uno.

    Sale de `ConfiguracionContinuidad` (la fija sola la migración el día del
    despliegue; una clínica nueva, el día en que se usa por primera vez). El
    setting CONTINUIDAD_REGISTRO_FORMAL_DESDE, si está, la sobrescribe."""
    from django.utils import timezone

    from .models import ConfiguracionContinuidad

    valor = getattr(settings, "CONTINUIDAD_REGISTRO_FORMAL_DESDE", None)
    if valor:
        return valor if isinstance(valor, date) else date.fromisoformat(str(valor))
    conf, _ = ConfiguracionContinuidad.objects.get_or_create(
        clinica_id=clinica_id, defaults={"registro_formal_desde": timezone.localdate()})
    return conf.registro_formal_desde


def emparejar(tramos, persistidos, tolerancia=TOLERANCIA_DIAS):
    """Emparejamiento puro (sin base de datos).

    `tramos`: dicts con "ids" (ids de las citas-sesión del tramo, en orden),
    "s1_fecha" y "fin". `persistidos`: objetos con id, cita_inicio_id,
    fecha_inicio, fecha_inicio_original y fin_observado.

    Devuelve (asignados {índice_tramo: persistido}, nuevos [índices],
    marcas {persistido.id: motivo_revision}, nuevos_division {índices}).
    """
    tramo_de_cita = {}
    for i, t in enumerate(tramos):
        for cid in t["ids"]:
            tramo_de_cita[cid] = i

    candidatos = {}
    sin_ancla = []
    for p in persistidos:
        i = tramo_de_cita.get(p.cita_inicio_id) if p.cita_inicio_id else None
        if i is None:
            sin_ancla.append(p)
        else:
            candidatos.setdefault(i, []).append(p)

    asignados, marcas = {}, {}
    for i, ps in candidatos.items():
        s1 = tramos[i]["ids"][0]
        ps = sorted(ps, key=lambda p: (p.cita_inicio_id != s1, p.fecha_inicio_original, p.id))
        asignados[i] = ps[0]
        for otro in ps[1:]:
            marcas[otro.id] = R.FUSION_POTENCIAL

    libres = [i for i in range(len(tramos)) if i not in asignados]
    por_tramo = {}
    for p in sin_ancla:
        cerca = [i for i in libres if abs((tramos[i]["s1_fecha"] - p.fecha_inicio).days) <= tolerancia]
        if len(cerca) == 1:
            por_tramo.setdefault(cerca[0], []).append(p)
        elif cerca:
            marcas[p.id] = R.INICIO_AMBIGUO
        else:
            marcas[p.id] = R.SIN_TRAMO
    for i, ps in por_tramo.items():
        if len(ps) == 1:
            asignados[i] = ps[0]
        else:
            for p in ps:
                marcas[p.id] = R.INICIO_AMBIGUO

    nuevos = [i for i in range(len(tramos)) if i not in asignados]
    division = set()
    for i in nuevos:
        s1 = tramos[i]["s1_fecha"]
        for p in persistidos:
            fin = p.fin_observado
            if fin and p.fecha_inicio < s1 <= fin and p.id not in marcas:
                division.add(i)
    return asignados, nuevos, marcas, division


def _tramos_por_paciente(procesos):
    """Los procesos de `construir_procesos` agrupados como tramos."""
    out = {}
    for p in procesos:
        out.setdefault(p["paciente_id"], []).append(p)
    for lista in out.values():
        lista.sort(key=lambda p: p["numero"])
    return out


def _como_tramo(p):
    return {"ids": [s["id"] for s in p["sesiones"]], "s1_fecha": p["s1"], "fin": p["ultima"]}


def anotar_formales(procesos):
    """Agrega a cada proceso detectado su registro formal, SIN escribir.

    Pone en cada dict: "formal" (el ProcesoContinuidad o None) y
    "estado_formal" (código de Estado; "sin_registro" si no hay fila).
    Dos consultas para todos los pacientes, no una por proceso."""
    por_pac = _tramos_por_paciente(procesos)
    for p in procesos:
        p["formal"], p["estado_formal"] = None, Estado.SIN_REGISTRO
    if not por_pac:
        return procesos
    persistidos = {}
    for fila in ProcesoContinuidad.objects.filter(paciente_id__in=list(por_pac)):
        persistidos.setdefault(fila.paciente_id, []).append(fila)
    for pid, lista in por_pac.items():
        filas = persistidos.get(pid)
        if not filas:
            continue
        asignados, _, _, _ = emparejar([_como_tramo(p) for p in lista], filas)
        for i, fila in asignados.items():
            lista[i]["formal"] = fila
            lista[i]["estado_formal"] = fila.estado
    return procesos


def _procesos_de(paciente_id, hoy=None):
    from core.direccion_clinica import construir_procesos
    from pacientes.models import Paciente
    return construir_procesos(Paciente.objects.filter(pk=paciente_id), hoy=hoy, formal=False)


@transaction.atomic
def reconciliar_paciente(paciente_id, hoy=None):
    """Persiste el emparejamiento de UN paciente. Devuelve sus procesos
    persistidos emparejados: [(proceso_detectado, ProcesoContinuidad)].

    Bloquea la fila del paciente para que dos reconciliaciones simultáneas no
    creen el mismo proceso dos veces. No borra nada ni cambia estados (salvo
    el ACTIVO inicial de un proceso nuevo, con su evento de inicio)."""
    from pacientes.models import Paciente

    paciente = Paciente.objects.select_for_update().filter(pk=paciente_id).first()
    if paciente is None:  # se borró (p. ej. al consolidar duplicados)
        return []
    detectados = sorted(_procesos_de(paciente_id, hoy), key=lambda p: p["numero"])
    filas = list(ProcesoContinuidad.objects.select_for_update().filter(paciente_id=paciente_id))
    asignados, nuevos, marcas, division = emparejar([_como_tramo(p) for p in detectados], filas)

    desde = registro_formal_desde(paciente.clinica_id)
    pares = []
    for i, fila in asignados.items():
        p = detectados[i]
        cambios = {"cita_inicio_id": p["sesiones"][0]["id"], "fecha_inicio": p["s1"],
                   "fin_observado": p["ultima"], "requiere_revision": ""}
        sucio = [k for k, v in cambios.items() if getattr(fila, k) != v]
        for k in sucio:
            setattr(fila, k, cambios[k])
        if sucio:
            fila.save(update_fields=sucio + ["actualizado_en"])
        pares.append((p, fila))
    for fila in filas:
        if fila.id in marcas and fila.requiere_revision != marcas[fila.id]:
            fila.requiere_revision = marcas[fila.id]
            fila.save(update_fields=["requiere_revision", "actualizado_en"])
    for i in nuevos:
        p = detectados[i]
        activo = p["s1"] >= desde
        fila = ProcesoContinuidad.objects.create(
            clinica_id=paciente.clinica_id, paciente=paciente,
            cita_inicio_id=p["sesiones"][0]["id"], fecha_inicio=p["s1"], fecha_inicio_original=p["s1"],
            fin_observado=p["ultima"],
            estado=Estado.ACTIVO if activo else Estado.SIN_REGISTRO,
            fecha_estado=p["s1"] if activo else None,
            requiere_revision=R.DIVISION_POTENCIAL if i in division else "",
        )
        if activo:
            EventoContinuidad.objects.create(
                clinica_id=paciente.clinica_id, proceso=fila, tipo=TipoEvento.INICIO_PROCESO,
                estado_anterior="", estado_nuevo=Estado.ACTIVO, fecha_efectiva=p["s1"],
                origen=Origen.SISTEMA, clave_idempotencia=f"inicio:{fila.uuid}",
            )
        pares.append((p, fila))
    pares.sort(key=lambda x: x[0]["numero"])
    return pares


def reconciliar_en_segundo_plano(paciente_id):
    """Para las señales de la Agenda: corre al confirmar la transacción y
    nunca rompe el guardado de una cita si algo falla aquí."""
    def correr():
        try:
            reconciliar_paciente(paciente_id)
        except Exception:  # noqa: BLE001 — la agenda no puede caerse por esto
            log.exception("No se pudo reconciliar la continuidad del paciente %s", paciente_id)
    transaction.on_commit(correr)
