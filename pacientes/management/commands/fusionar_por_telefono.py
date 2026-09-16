"""LISTA pacientes repetidos que comparten NÚMERO DE TELÉFONO. Ya no fusiona.

Son los que dejó el doble registro: la coordinadora registraba la consulta en
Marketing y volvía a crear al paciente desde la Agenda, así que la misma persona
quedaba dos veces con el mismo número.

CUIDADO — el mismo número NO siempre es la misma persona: en la clínica se
atiende a niños y adolescentes, y madre e hijo comparten celular. Por eso solo se
fusionan los pares cuyo NOMBRE también encaja (mismo primer nombre y uno contenido
en el otro). Los demás se listan para que alguien los mire, pero no se tocan.

    python manage.py fusionar_por_telefono                 # simula, no escribe
    python manage.py fusionar_por_telefono --sede piura

`--aplicar` está DESACTIVADO desde set. 2026: lo reemplaza la pantalla
"Posibles duplicados" (pacientes/fusion.py), que mueve las relaciones por
introspección y consolida de a un caso con confirmación humana. Este comando
queda solo como listado rápido desde la consola.
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import Clinica
from pacientes.management.commands.importar_lima import norm
from pacientes.models import Paciente


def solo_digitos(t):
    return "".join(c for c in (t or "") if c.isdigit())[-9:]


def es_de_pareja(nombre):
    """"Andrea Zapata y Roy Pozo" es el expediente de una PAREJA, no un duplicado
    de "Andrea Zapata": son procesos distintos y no se pueden mezclar."""
    return f" y " in f" {norm(nombre)} "


def mismo_nombre(a, b):
    """¿Los nombres son de la misma persona? Conservador a propósito."""
    if es_de_pareja(a) != es_de_pareja(b):
        return False
    ta, tb = norm(a).split(), norm(b).split()
    if not ta or not tb:
        return False
    if ta[0] != tb[0]:                      # distinto primer nombre → distinta persona
        return False
    sa, sb = set(ta), set(tb)
    return sa.issubset(sb) or sb.issubset(sa)


class Command(BaseCommand):
    help = "Lista pacientes repetidos con el mismo teléfono. Ya NO fusiona."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "lima", "piura"])
        parser.add_argument("--aplicar", action="store_true",
                            help="Sin esto solo simula: no escribe nada.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica.")
            return

        qs = Paciente.objects.filter(clinica=clinica).exclude(telefono="")
        if opt["sede"]:
            qs = qs.filter(sede=opt["sede"])

        grupos = {}
        for p in qs:
            tel = solo_digitos(p.telefono)
            if len(tel) >= 8:
                grupos.setdefault(tel, []).append(p)

        pares, revisar = [], []
        for tel, gente in grupos.items():
            if len(gente) < 2:
                continue
            # El principal es el que más historia tiene; ante empate, el más antiguo.
            gente.sort(key=lambda p: (-self._peso(p), p.id))
            principal = gente[0]
            for otro in gente[1:]:
                if mismo_nombre(principal.nombre, otro.nombre):
                    pares.append((otro, principal))
                else:
                    revisar.append((tel, principal, otro))

        self.stdout.write(self.style.HTTP_INFO(
            f"Teléfonos repetidos: {sum(1 for g in grupos.values() if len(g) > 1)} | "
            f"fusiones seguras: {len(pares)} | a revisar a mano: {len(revisar)}"
        ))
        for d, r in pares[:30]:
            self.stdout.write(f"  '{d.nombre}' ({self._peso(d)} registros) -> '{r.nombre}'")
        if len(pares) > 30:
            self.stdout.write(f"  … y {len(pares) - 30} más")
        if revisar:
            self.stdout.write(self.style.WARNING(
                "\nMismo número pero nombres distintos — NO se tocan "
                "(suelen ser madre/padre e hijo compartiendo celular):"))
            for tel, a, b in revisar[:30]:
                self.stdout.write(f"  …{tel[-4:]}  '{a.nombre}'  ·  '{b.nombre}'")

        if not opt["aplicar"]:
            self.stdout.write(self.style.WARNING(
                "\nRevisa la lista de arriba ANTES de aplicar: si en un mismo nombre "
                "ves a dos personas (pasa en terapia de pareja), no lo apliques."))
            self.stdout.write(self.style.SUCCESS("SIMULACIÓN: no se escribió nada."))
            return

        # --aplicar queda DESACTIVADO. Su lista `RELACIONES` está escrita a mano y
        # se quedó sin GestionContinuidad (PROTECT), así que revienta a mitad de
        # camino con ProtectedError; y aunque no reventara, fusiona en lote sin que
        # nadie mire cada caso. Lo reemplaza "Posibles duplicados" en el sistema,
        # que mueve las relaciones por introspección, proyecta la continuidad antes
        # de tocar nada y exige confirmación humana caso por caso.
        raise CommandError(
            "Este comando ya no fusiona: su lista de relaciones quedó incompleta "
            "(falta GestionContinuidad) y fusionaba en lote sin revisión. "
            "Usa la pantalla 'Posibles duplicados' del sistema, que compara las dos "
            "fichas, muestra la vista previa y consolida de a un caso. "
            "Por código: pacientes.fusion.analizar_fusion / fusionar_pacientes."
        )

    @staticmethod
    def _peso(p):
        """Cuánta historia tiene el paciente (para elegir cuál se queda)."""
        return (p.atenciones.count() + p.cobros.count() + p.citas.count()
                + p.adjuntos.count() + p.paquetes.count())
