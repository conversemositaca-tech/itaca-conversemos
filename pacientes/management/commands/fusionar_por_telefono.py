"""Fusiona pacientes repetidos que comparten NÚMERO DE TELÉFONO.

Son los que dejó el doble registro: la coordinadora registraba la consulta en
Marketing y volvía a crear al paciente desde la Agenda, así que la misma persona
quedaba dos veces con el mismo número. (El flujo ya no los genera; esto limpia
los que quedaron.)

`fusionar_duplicados` NO sirve para estos: aquel compara nombres y exige que el
duplicado no tenga teléfono.

CUIDADO — el mismo número NO siempre es la misma persona: en la clínica se
atiende a niños y adolescentes, y madre e hijo comparten celular. Por eso solo se
fusionan los pares cuyo NOMBRE también encaja (mismo primer nombre y uno contenido
en el otro). Los demás se listan para que alguien los mire, pero no se tocan.

    python manage.py fusionar_por_telefono                 # simula, no escribe
    python manage.py fusionar_por_telefono --sede piura
    python manage.py fusionar_por_telefono --aplicar       # ahora sí fusiona
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Clinica
from finanzas.models import Cobro, Paquete
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes.management.commands.importar_lima import norm
from pacientes.models import (
    Adjunto, AplicacionEscala, Atencion, Cita, Consentimiento, ContactoProfesional,
    ObjetivoTerapeutico, Paciente, RespuestaNPS, SeguimientoSesion, Tarea,
)

# TODO lo que cuelga de un paciente. El comando viejo solo movía cinco de estas y
# el resto se borraba con el duplicado (consentimientos, escalas, objetivos,
# tareas, NPS…). Aquí se mueven todas antes de borrar.
RELACIONES = [
    Atencion, Cita, Adjunto, Cobro, Paquete, Lead, Mensaje, SeguimientoSesion,
    Consentimiento, AplicacionEscala, ObjetivoTerapeutico, Tarea, RespuestaNPS,
    ContactoProfesional,
]


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
    help = "Fusiona pacientes repetidos con el mismo teléfono (y nombre compatible)."

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
            self.stdout.write(self.style.SUCCESS("SIMULACIÓN: no se escribió nada. Agrega --aplicar para fusionar."))
            return

        with transaction.atomic():
            for duplicado, principal in pares:
                for modelo in RELACIONES:
                    modelo.objects.filter(paciente=duplicado).update(paciente=principal)
                # Se queda el dato que el principal no tenga (el duplicado suele
                # traer el correo o el documento que al otro le falta).
                cambios = []
                for campo in ("email", "numero_documento", "fecha_nacimiento", "direccion"):
                    if not getattr(principal, campo) and getattr(duplicado, campo):
                        setattr(principal, campo, getattr(duplicado, campo))
                        cambios.append(campo)
                # Se queda el nombre más completo: el principal es el que más
                # historia tiene, pero suele ser el que se registró más corto.
                if len(norm(duplicado.nombre).split()) > len(norm(principal.nombre).split()):
                    principal.nombre = duplicado.nombre
                    cambios.append("nombre")
                if cambios:
                    principal.save(update_fields=cambios)
                duplicado.delete()
        self.stdout.write(self.style.SUCCESS(f"Listo: {len(pares)} pacientes fusionados."))

    @staticmethod
    def _peso(p):
        """Cuánta historia tiene el paciente (para elegir cuál se queda)."""
        return (p.atenciones.count() + p.cobros.count() + p.citas.count()
                + p.adjuntos.count() + p.paquetes.count())
