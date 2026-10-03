"""A quién va un correo y cómo se le encuentra en el historial.

`Destinatario` envuelve la identidad (paciente, lead, apoderado de Faro o el
tutor de un paciente) y responde tres preguntas:

- `correo()`: a qué dirección se escribe, siempre leída del sistema;
- `nombre()`: cómo se le saluda;
- `filtro()`: qué filas de consentimiento, preferencias y bitácora son de la
  MISMA persona. Un paciente y los leads que se le convirtieron son una sola
  persona: su permiso dado al reservar (en el lead) vale cuando luego se le
  escribe como paciente, y su baja también.
"""
from dataclasses import dataclass

from django.db.models import Q

EDAD_MAXIMA_MENOR = 14  # "menor de 14": por debajo de esta edad decide el tutor


@dataclass(frozen=True)
class Destinatario:
    paciente: object = None
    lead: object = None
    autorizacion: object = None
    es_tutor: bool = False

    def __post_init__(self):
        llenos = sum(x is not None for x in (self.paciente, self.lead, self.autorizacion))
        if llenos != 1:
            raise ValueError("Un destinatario es exactamente una persona.")
        if self.es_tutor and self.paciente is None:
            raise ValueError("El tutor siempre es el de un paciente.")

    # --- Construcción ---------------------------------------------------------
    @classmethod
    def de_paciente(cls, paciente):
        return cls(paciente=paciente)

    @classmethod
    def tutor_de(cls, paciente):
        return cls(paciente=paciente, es_tutor=True)

    @classmethod
    def de_lead(cls, lead):
        return cls(lead=lead)

    @classmethod
    def de_autorizacion(cls, autorizacion):
        return cls(autorizacion=autorizacion)

    @classmethod
    def de_fila(cls, fila):
        """El destinatario de una fila con identidad (consentimiento, preferencia…)."""
        if fila.paciente_id:
            return cls(paciente=fila.paciente, es_tutor=fila.es_tutor)
        if fila.lead_id:
            return cls(lead=fila.lead)
        return cls(autorizacion=fila.autorizacion)

    # --- Datos ----------------------------------------------------------------
    @property
    def clinica(self):
        return (self.paciente or self.lead or self.autorizacion).clinica

    def identidad(self):
        """Los campos de identidad para crear una fila de este destinatario."""
        return {
            "clinica": self.clinica,
            "paciente": self.paciente,
            "lead": self.lead,
            "autorizacion": self.autorizacion,
            "es_tutor": self.es_tutor,
        }

    def correo(self):
        if self.autorizacion is not None:
            return (self.autorizacion.correo or "").strip()
        if self.es_tutor:
            return (self.paciente.tutor_correo or "").strip()
        if self.paciente is not None:
            propio = (self.paciente.email or "").strip()
            if propio:
                return propio
            # Quien reservó por la web dejó su correo en el lead; si su ficha
            # ya existía, la ficha no lo recibió. Se usa el más reciente.
            from leads.models import Lead
            return (Lead.objects.filter(paciente=self.paciente).exclude(email="")
                    .order_by("-creado_en", "-id").values_list("email", flat=True).first()
                    or "").strip()
        return (self.lead.email or "").strip()

    def nombre(self):
        """Nombre de pila para el saludo."""
        if self.autorizacion is not None:
            completo = self.autorizacion.apoderado
        elif self.es_tutor:
            completo = self.paciente.tutor_nombre
        elif self.paciente is not None:
            completo = self.paciente.nombre
        else:
            completo = self.lead.nombre
        return ((completo or "").strip().split() or [""])[0].capitalize()

    def paciente_relacionado(self):
        """La ficha clínica detrás de este destinatario, si la hay."""
        if self.paciente is not None:
            return self.paciente
        if self.lead is not None and self.lead.paciente_id:
            return self.lead.paciente
        return None

    def es_menor(self):
        """¿La persona es menor de 14? Solo se sabe si la ficha tiene fecha de nacimiento.

        El tutor nunca es menor. Sin fecha de nacimiento se asume adulto: la
        reserva web no la pide y no hay otro dato fiable.
        """
        if self.es_tutor or self.autorizacion is not None:
            return False
        p = self.paciente_relacionado()
        edad = p.edad if p is not None else None
        return edad is not None and edad < EDAD_MAXIMA_MENOR

    # --- Historial de la misma persona ---------------------------------------
    def filtro(self):
        """Q sobre un modelo `ConIdentidad` con las filas de esta persona."""
        if self.autorizacion is not None:
            return Q(autorizacion=self.autorizacion)
        if self.es_tutor:
            return Q(paciente=self.paciente, es_tutor=True)
        p = self.paciente_relacionado()
        q = Q(pk__in=[])
        if self.lead is not None:
            q |= Q(lead=self.lead)
        if p is not None:
            q |= Q(paciente=p, es_tutor=False) | Q(lead__paciente=p)
        return q
