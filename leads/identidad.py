"""Quién es la persona que llega: la regla, en un solo sitio.

El teléfono NO identifica a nadie. En esta clínica 140 números están
compartidos por 307 fichas —hermanos, madres e hijos, familiares que gestionan
la atención de otro—, así que dar por hecho que un número es una persona
terminaba colgándole la consulta de alguien a la ficha de otro, con su agenda y
su historial (#86).

Esa regla vivía dentro de `leads.api` y solo la usaba el registro de Marketing.
La reserva web tenía su propia versión, más laxa todavía (`.endswith()` sobre
todos los pacientes), y por eso volvía a cruzar personas por el mismo camino.
Aquí está una sola vez, para los dos.

Ante la duda se separa: una ficha repetida se corrige; dos historias clínicas
mezcladas, no.
"""
import unicodedata

from pacientes.models import Paciente

# Un número peruano tiene 9 dígitos. Con menos es un dato a medio cargar, no un
# identificador: con "123" en dos fichas no se puede afirmar que sean la misma
# persona.
MIN_DIGITOS_TELEFONO = 9


def norm_tel(t):
    """Solo dígitos, los últimos 9 (el móvil, sin el prefijo del país)."""
    return "".join(c for c in (t or "") if c.isdigit())[-9:]


def norm_documento(d):
    return "".join(c for c in (d or "") if c.isalnum()).upper()


def norm_nombre(n):
    """El nombre para comparar personas: sin mayúsculas, tildes ni espacios de más.

    Corrige lo trivial (MARÍA / maria / María  Pérez) y nada más. Nada de
    parecidos ni apodos: dos nombres distintos son dos personas distintas, y
    equivocarse aquí mezcla dos historias clínicas.
    """
    limpio = unicodedata.normalize("NFKD", (n or "").strip().lower())
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    return " ".join(limpio.split())


def sedes_compatibles(sede_ficha, sede_nueva):
    """¿Las sedes permiten dar por hecho que es la misma persona?

    Dos sedes DISTINTAS no se fusionan solas: puede ser un homónimo, o alguien
    que se atiende en otra ciudad, y eso lo decide una persona.

    Una sede VACÍA es otra cosa: es un dato que falta, no un dato que
    contradiga. Muchas fichas antiguas no la tienen, y tratarla como "distinta"
    llenaría la base de duplicados de gente que ya existe.
    """
    a, b = (sede_ficha or "").strip(), (sede_nueva or "").strip()
    return not a or not b or a == b


def numeros_de(paciente):
    """Por qué números se llega a esta persona: el suyo y el de su tutor.

    Un menor no suele tener celular: su número vive en `tutor_telefono`. Hasta
    ahora la búsqueda solo miraba `telefono`, así que una ficha de menor era
    **inencontrable** y cada lead suyo abría una ficha nueva. Mirar los dos
    campos NO reabre el cruce que cerró el fix #86: el nombre sigue siendo lo
    que decide, y el número solo confirma (ver `ficha_que_calza`).
    """
    return {t for t in (norm_tel(paciente.telefono), norm_tel(paciente.tutor_telefono))
            if len(t) >= MIN_DIGITOS_TELEFONO}


def ficha_que_calza(clinica, *, nombre, telefono="", sede="", documento="",
                    tutor_telefono=""):
    """La ficha que es SIN DUDA de esta persona, o None.

    Dos caminos, y los dos exigen que no haya ambigüedad:

    - **Documento**: identifica por sí solo (un DNI es de una persona), pero si
      dos fichas lo comparten es que algo está mal cargado y no se elige.
    - **Teléfono + nombre**: el número solo no basta; tiene que coincidir
      también el NOMBRE, y la sede no puede contradecir. El número puede ser el
      del paciente o el de su tutor, en cualquiera de los dos lados: madre e
      hija comparten celular, pero no nombre, así que siguen separadas.

    Si calzan dos fichas no se devuelve ninguna: crear una de más se corrige,
    mezclar dos historias clínicas no.
    """
    doc = norm_documento(documento)
    if doc:
        por_doc = [p for p in Paciente.objects.filter(clinica=clinica)
                   .exclude(numero_documento="")
                   if norm_documento(p.numero_documento) == doc]
        if len(por_doc) == 1:
            return por_doc[0]
        if por_doc:
            return None      # el mismo documento en dos fichas: que lo mire una persona

    buscados = {t for t in (norm_tel(telefono), norm_tel(tutor_telefono))
                if len(t) >= MIN_DIGITOS_TELEFONO}
    nom = norm_nombre(nombre)
    if not buscados or not nom:
        return None
    candidatos = [
        p for p in Paciente.objects.filter(clinica=clinica)
        .exclude(telefono="", tutor_telefono="")
        if numeros_de(p) & buscados
        and norm_nombre(p.nombre) == nom
        and sedes_compatibles(p.sede, sede)
    ]
    return candidatos[0] if len(candidatos) == 1 else None
