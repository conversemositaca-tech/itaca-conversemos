"""Visibilidad por CAMPO: ver un recurso no es ver todos sus campos.

La matriz (core/tests_matriz_permisos.py) dice qué rol recibe 200 en cada
endpoint. Este archivo dice, dentro de ese 200, qué campos sensibles llegan
con valor y cuáles llegan vacíos. Si un cambio hace que un campo sensible
llegue con valor a un rol que no debía verlo, el test lo nombra.

    python manage.py test core.tests_campos_por_rol
"""
from django.test import TestCase

from core.models import Clinica
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes.models import Atencion, Consentimiento, Paciente
from usuarios.models import Profesional, Usuario

ROLES = ("admin", "asistente", "medico", "comercial", "analista")

CONTACTO_PACIENTE = ("tel", "email", "direccion", "numero_documento",
                     "tutor_telefono", "tutor_documento", "tutor_correo")
CONTACTO_LEAD = ("telefono", "email", "ubicacion", "contacto_telefono")

# (nombre, cómo obtener la fila, campos, roles que ven el valor, roles que lo reciben vacío)
CASOS = [
    ("paciente.detalle", "detalle_paciente", CONTACTO_PACIENTE, ("admin", "asistente"), ("medico", "analista")),
    ("paciente.lista", "lista_paciente", ("tel", "email"), ("admin", "asistente"), ("medico", "analista")),
    ("lead.contacto", "lead", CONTACTO_LEAD, ("admin", "asistente", "comercial"), ("medico", "analista")),
    ("consentimiento.token", "consentimiento", ("token", "url"), ("admin", "asistente"), ("medico",)),
    ("mensaje.telefono", "mensaje", ("telefono",), ("admin", "asistente", "comercial"), ("medico",)),
    ("mensaje.enlace_firma", "mensaje_texto", ("texto_con_token",), ("admin", "asistente"), ("medico", "comercial")),
    ("historia.diagnostico", "atencion", ("diagnostico", "nota"), ("admin", "asistente", "medico", "analista"), ()),
]


class CamposSensiblesPorRolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Conversemos", slug="campos-rol")
        cls.u = {r: Usuario.objects.create_user(email=f"{r}@campos.pe", password="x", clinica=cls.clinica, rol=r)
                 for r in ROLES}
        ficha = Profesional.objects.create(clinica=cls.clinica, usuario=cls.u["medico"], nombre="Psico")
        cls.paciente = Paciente.objects.create(
            clinica=cls.clinica, nombre="Ana Mía", profesional=ficha, telefono="987111222",
            email="ana@x.pe", direccion="Av. 1", numero_documento="12345678",
            tutor_telefono="987333444", tutor_documento="87654321", tutor_correo="tutor@x.pe")
        cls.lead = Lead.objects.create(
            clinica=cls.clinica, nombre="Interesada", telefono="987555666", email="lead@x.pe",
            ubicacion="Castilla", contacto_telefono="987777888")
        cls.consentimiento = Consentimiento.objects.create(
            clinica=cls.clinica, paciente=cls.paciente, texto="t", token=Consentimiento.nuevo_token())
        cls.mensaje = Mensaje.objects.create(
            clinica=cls.clinica, paciente=cls.paciente, telefono="51987111222",
            texto=f"Firma aquí: https://x.pe/consentimiento/{cls.consentimiento.token}")
        cls.atencion = Atencion.objects.create(
            clinica=cls.clinica, paciente=cls.paciente, medico=cls.u["medico"], diagnostico="F41.1", nota="Sesión")

    def _fila(self, rol, fuente):
        self.client.force_login(self.u[rol])
        if fuente == "detalle_paciente":
            return self.client.get(f"/api/pacientes/{self.paciente.id}/").json()
        if fuente == "lista_paciente":
            return next(p for p in self.client.get("/api/pacientes/").json() if p["id"] == self.paciente.id)
        if fuente == "lead":
            return next(x for x in self.client.get("/api/leads/").json() if x["id"] == self.lead.id)
        if fuente == "consentimiento":
            return self.client.get(f"/api/consentimientos/{self.consentimiento.id}/").json()
        if fuente == "mensaje":
            return next(m for m in self.client.get("/api/mensajes/").json() if m["id"] == self.mensaje.id)
        if fuente == "mensaje_texto":
            m = next(m for m in self.client.get("/api/mensajes/").json() if m["id"] == self.mensaje.id)
            return {"texto_con_token": self.consentimiento.token if self.consentimiento.token in m["texto"] else ""}
        if fuente == "atencion":
            return self.client.get(f"/api/atenciones/{self.atencion.id}/").json()
        raise AssertionError(fuente)

    def test_campos_sensibles(self):
        fugas, faltan = [], []
        for nombre, fuente, campos, ven, ocultos in CASOS:
            for rol in ven:
                fila = self._fila(rol, fuente)
                faltan += [f"{nombre} · {rol} · {c}" for c in campos if not fila.get(c)]
            for rol in ocultos:
                fila = self._fila(rol, fuente)
                fugas += [f"{nombre} · {rol} · {c}" for c in campos if fila.get(c)]
        self.assertFalse(fugas, "CAMPO SENSIBLE VISIBLE PARA UN ROL QUE NO DEBE VERLO:\n" + "\n".join(fugas))
        self.assertFalse(faltan, "Un rol autorizado dejó de ver un campo que necesita:\n" + "\n".join(faltan))
