"""Detección de pacientes duplicados: propone, nunca decide.

Este módulo SOLO lee. No fusiona nada y no escribe: lo que hace es señalar
pares que podrían ser la misma persona para que alguien los mire
(`pacientes.fusion` hace el trabajo, y siempre con confirmación humana).

La regla de identidad de fondo es la misma que usan la reserva web y Marketing
(`leads.identidad`): el teléfono solo NO identifica a nadie —en esta clínica
hay 155 pares de fichas que comparten número y son familiares distintos— y dos
documentos válidos distintos son dos personas, gane lo que gane el parecido del
nombre.

Confianza (medida contra producción, set. 2026):
  ALTA   mismo documento válido; o mismo nombre normalizado + mismo teléfono
         válido + sede compatible, sin ninguna señal que los contradiga.
  MEDIA  sugerente sin identificador fuerte (mismo nombre y sede compatible,
         o el número del tutor como único puente).
  BAJA   solo el nombre se parece.
  Descartado: documentos válidos distintos.
"""
from collections import defaultdict

from leads.identidad import (
    MIN_DIGITOS_TELEFONO, norm_documento, norm_nombre, norm_tel, sedes_compatibles,
)

from .models import Paciente, RevisionDuplicado

ALTA, MEDIA, BAJA = "alta", "media", "baja"

# Un documento peruano: DNI 8, RUC 11, CE hasta 12. Fuera de ese rango es
# relleno mal cargado, no un identificador con el que afirmar nada.
DOC_MIN, DOC_MAX = 8, 12

# Un nombre de pila muy común (decenas de fichas) no se cruza todas contra
# todas: son homónimos, no duplicados, y el producto cartesiano no aporta.
MAX_POR_NOMBRE_DE_PILA = 60


def doc_valido(d):
    """El documento normalizado si sirve para identificar; '' si no."""
    n = norm_documento(d)
    return n if DOC_MIN <= len(n) <= DOC_MAX else ""


def tel_valido(t):
    """El teléfono normalizado si tiene dígitos suficientes; '' si no.

    Con 6, 7 u 8 dígitos hay un dato a medio cargar, no un identificador: dos
    fichas con '123456' no son la misma persona por eso.
    """
    n = norm_tel(t)
    return n if len(n) >= MIN_DIGITOS_TELEFONO else ""


def es_de_pareja(nombre):
    """'Andrea Z. y Roy P.' es el expediente de una PAREJA, no un duplicado de
    'Andrea Z.': son dos procesos y mezclarlos junta dos historias clínicas."""
    return " y " in " " + norm_nombre(nombre) + " "


def nombre_compatible(a, b):
    """¿Los nombres pueden ser de la misma persona? Conservador a propósito:
    mismo primer nombre y un conjunto de tokens contenido en el otro. Nada de
    apodos ni parecidos fonéticos."""
    if es_de_pareja(a) != es_de_pareja(b):
        return False
    ta, tb = norm_nombre(a).split(), norm_nombre(b).split()
    if not ta or not tb:
        return False
    if ta[0] != tb[0]:
        return False
    sa, sb = set(ta), set(tb)
    return sa.issubset(sb) or sb.issubset(sa)


# --- Señales entre dos fichas ------------------------------------------------

def contradicciones(a, b):
    """Lo que dice que NO son la misma persona. Si hay algo aquí, no hay ALTA.

    `a` y `b` son dicts con al menos numero_documento, fecha_nacimiento y sede.
    """
    out = []
    da, db = doc_valido(a.get("numero_documento")), doc_valido(b.get("numero_documento"))
    if da and db and da != db:
        out.append("documentos_distintos")
    fa, fb = a.get("fecha_nacimiento"), b.get("fecha_nacimiento")
    if fa and fb and fa != fb:
        out.append("nacimiento_distinto")
    if not sedes_compatibles(a.get("sede"), b.get("sede")):
        out.append("sedes_distintas")
    return out


def senales(a, b):
    """Lo que dice que SÍ podrían serlo, como lista de claves legibles."""
    out = []
    da, db = doc_valido(a.get("numero_documento")), doc_valido(b.get("numero_documento"))
    if da and db and da == db:
        out.append("documento_igual")
    na, nb = norm_nombre(a.get("nombre")), norm_nombre(b.get("nombre"))
    if na and na == nb:
        out.append("nombre_igual")
    elif nombre_compatible(a.get("nombre"), b.get("nombre")):
        out.append("nombre_similar")
    ta, tb = tel_valido(a.get("telefono")), tel_valido(b.get("telefono"))
    if ta and ta == tb:
        out.append("telefono_igual")
    # El número del tutor es un CANAL, no la identidad del paciente: cuenta
    # como pista para mirar el par, jamás para darlo por resuelto.
    tua, tub = tel_valido(a.get("tutor_telefono")), tel_valido(b.get("tutor_telefono"))
    puente = {x for x in (ta, tua) if x} & {x for x in (tb, tub) if x}
    if puente and "telefono_igual" not in out:
        out.append("telefono_tutor_igual")
    fa, fb = a.get("fecha_nacimiento"), b.get("fecha_nacimiento")
    if fa and fa == fb:
        out.append("nacimiento_igual")
    ea, eb = (a.get("email") or "").strip().lower(), (b.get("email") or "").strip().lower()
    if ea and ea == eb:
        out.append("email_igual")
    pa, pb = a.get("profesional_id"), b.get("profesional_id")
    if pa and pa == pb:
        out.append("mismo_psicologo")
    return out


def clasificar(a, b):
    """(confianza, señales, contradicciones) del par. None si ni siquiera es
    candidato o si algo lo descarta de plano."""
    contra = contradicciones(a, b)
    if "documentos_distintos" in contra:
        return None, [], contra          # homónimos: no se ofrecen nunca
    sen = senales(a, b)
    if not sen:
        return None, [], contra
    if "nacimiento_distinto" in contra:
        return None, sen, contra         # misma razón: dos personas
    fuerte_doc = "documento_igual" in sen
    mismo_nombre = "nombre_igual" in sen
    mismo_tel = "telefono_igual" in sen
    sede_ok = "sedes_distintas" not in contra

    if fuerte_doc:
        return ALTA, sen, contra
    if mismo_nombre and mismo_tel and sede_ok:
        return ALTA, sen, contra
    if mismo_nombre and sede_ok:
        return MEDIA, sen, contra
    if "telefono_tutor_igual" in sen and (mismo_nombre or "nombre_similar" in sen) and sede_ok:
        return MEDIA, sen, contra
    if mismo_tel and "nombre_similar" in sen and sede_ok:
        return MEDIA, sen, contra
    if "nombre_similar" in sen:
        return BAJA, sen, contra
    # Mismo teléfono con nombres que no se parecen: familiares. NO es duplicado.
    return None, sen, contra


CAMPOS = (
    "id", "nombre", "sede", "telefono", "tutor_telefono", "numero_documento",
    "email", "fecha_nacimiento", "provisional", "creado_en", "profesional_id",
    "profesional__nombre", "n_sesion", "sesiones_proceso", "frecuencia",
)


def _fichas(clinica, excluir_id=None):
    qs = Paciente.objects.filter(clinica=clinica)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return list(qs.values(*CAMPOS))


def coincidencias(clinica, *, nombre, telefono="", documento="", sede="",
                  tutor_telefono="", fecha_nacimiento=None, excluir_id=None,
                  minimo=BAJA):
    """Fichas que podrían ser esta persona, para AVISAR antes de crear una nueva.

    Devuelve [(ficha, confianza, señales)] ordenado de más a menos probable. No
    decide: quien registra mira la comparación y elige usar la existente o
    confirmar que es otra persona (ver PacienteViewSet.create).
    """
    nueva = {
        "nombre": nombre, "telefono": telefono, "numero_documento": documento,
        "sede": sede, "tutor_telefono": tutor_telefono,
        "fecha_nacimiento": fecha_nacimiento, "email": "", "profesional_id": None,
    }
    orden = {ALTA: 0, MEDIA: 1, BAJA: 2}
    tope = orden[minimo]
    out = []
    for f in _fichas(clinica, excluir_id=excluir_id):
        conf, sen, contra = clasificar(nueva, f)
        if conf is None or orden[conf] > tope:
            continue
        out.append((f, conf, sen))
    out.sort(key=lambda x: (orden[x[1]], -len(x[2]), x[0]["id"]))
    return out


def _descartados(clinica):
    return {
        (r["paciente_a_id"], r["paciente_b_id"])
        for r in RevisionDuplicado.objects.filter(clinica=clinica)
        .values("paciente_a_id", "paciente_b_id")
    }


def pares(clinica, incluir_descartados=False):
    """Todos los pares candidatos de la clínica, clasificados.

    Se indexa por documento, nombre y teléfono para no comparar 1.646 fichas
    todas contra todas.
    """
    fichas = _fichas(clinica)
    por_id = {f["id"]: f for f in fichas}
    por_doc, por_nombre, por_tel, por_pila = (defaultdict(list) for _ in range(4))
    for f in fichas:
        d = doc_valido(f["numero_documento"])
        if d:
            por_doc[d].append(f["id"])
        n = norm_nombre(f["nombre"])
        if n:
            por_nombre[n].append(f["id"])
            por_pila[n.split()[0]].append(f["id"])
        for t in (tel_valido(f["telefono"]), tel_valido(f["tutor_telefono"])):
            if t:
                por_tel[t].append(f["id"])

    vistos = set()

    def cruzar(grupo, tope=None):
        if tope and len(grupo) > tope:
            return
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                vistos.add((min(a, b), max(a, b)))

    for g in por_doc.values():
        cruzar(g)
    for g in por_nombre.values():
        cruzar(g)
    for g in por_tel.values():
        cruzar(g)
    for g in por_pila.values():
        cruzar(g, tope=MAX_POR_NOMBRE_DE_PILA)

    fuera = set() if incluir_descartados else _descartados(clinica)
    out = []
    for a, b in vistos:
        if (a, b) in fuera:
            continue
        conf, sen, contra = clasificar(por_id[a], por_id[b])
        if conf is None:
            continue
        out.append({"a": a, "b": b, "confianza": conf, "senales": sen,
                    "contradicciones": contra})
    orden = {ALTA: 0, MEDIA: 1, BAJA: 2}
    out.sort(key=lambda r: (orden[r["confianza"]], por_id[r["a"]]["nombre"]))
    return out, por_id


def grupos(clinica, confianza=ALTA, incluir_descartados=False):
    """Los pares de esa confianza agrupados por persona (alguien puede tener
    tres fichas). Devuelve [(ids_ordenados, señales_unidas)]."""
    todos, por_id = pares(clinica, incluir_descartados=incluir_descartados)
    padre = {}

    def raiz(x):
        padre.setdefault(x, x)
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    sen_de = defaultdict(set)
    for r in todos:
        if r["confianza"] != confianza:
            continue
        ra, rb = raiz(r["a"]), raiz(r["b"])
        if ra != rb:
            padre[rb] = ra
        sen_de[raiz(r["a"])].update(r["senales"])
    agr = defaultdict(list)
    for x in list(padre):
        agr[raiz(x)].append(x)
    out = []
    for r, miembros in agr.items():
        if len(miembros) > 1:
            out.append((sorted(miembros), sorted(sen_de[r])))
    out.sort(key=lambda g: por_id[g[0][0]]["nombre"])
    return out, por_id
