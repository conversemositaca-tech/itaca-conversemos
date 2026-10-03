"""Matriz ROL × ENDPOINT × MÉTODO → código HTTP esperado.

Detecta escalamientos de privilegio accidentales: si un cambio hace que un rol
reciba 2xx donde se esperaba 403/404 (o al revés), el test falla y dice qué
celda cambió. Las escrituras usan cuerpos inválidos: un rol autorizado recibe
400 y uno no autorizado 403/404, sin modificar datos.

Cambiar una celda es cambiar la política de acceso: se hace a propósito, en el
mismo PR que cambia el código, y con aprobación de Max (ver CLAUDE.md).

    python manage.py test core.tests_matriz_permisos
    ITACA_MATRIZ_GENERAR=1 python manage.py test core.tests_matriz_permisos  # imprime la matriz real
"""
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Clinica
from finanzas.models import Cobro, Egreso
from pacientes.models import Adjunto, Atencion, Consentimiento, Paciente, SugerenciaRiesgo
from usuarios.models import Profesional, Usuario

ROLES = ("anonimo", "admin", "asistente", "medico", "comercial", "analista")

# (método, ruta, cuerpo). {mio}/{ajeno} = paciente propio / ajeno del psicólogo.
ENDPOINTS = {
    "pacientes.lista": ("get", "/api/pacientes/", None),
    "pacientes.propio": ("get", "/api/pacientes/{mio}/", None),
    "pacientes.ajeno": ("get", "/api/pacientes/{ajeno}/", None),
    "atenciones.ajena": ("get", "/api/atenciones/{atencion_ajena}/", None),
    "adjuntos.descargar_propio": ("get", "/api/adjuntos/{adjunto_mio}/descargar/", None),
    "adjuntos.descargar_ajeno": ("get", "/api/adjuntos/{adjunto_ajeno}/descargar/", None),
    "consentimientos.ajeno": ("get", "/api/consentimientos/{consentimiento_ajeno}/", None),
    "riesgo.ver_ajena": ("get", "/api/sugerencias-riesgo/{sugerencia_ajena}/", None),
    "riesgo.resolver_propia": ("post", "/api/sugerencias-riesgo/{sugerencia_mia}/resolver/", {"decision": "x"}),
    "riesgo.resolver_ajena": ("post", "/api/sugerencias-riesgo/{sugerencia_ajena}/resolver/", {"decision": "x"}),
    "continuidad.pendientes": ("get", "/api/continuidad/pendientes/", None),
    "continuidad.caso_ajeno": ("get", "/api/continuidad/caso/{ajeno}/", None),
    "gerencia.resumen": ("get", "/api/gerencia/resumen/", None),
    "finanzas.caja": ("get", "/api/finanzas/caja/", None),
    "finanzas.liquidacion": ("get", "/api/finanzas/liquidacion/", None),
    "finanzas.egresos": ("get", "/api/egresos/", None),
    "finanzas.egreso_borrar": ("delete", "/api/egresos/{egreso}/", None),
    "usuarios.lista": ("get", "/api/usuarios/", None),
    "usuarios.crear": ("post", "/api/usuarios/", {}),
    "duplicados.lista": ("get", "/api/duplicados/", None),
    "duplicados.fusionar": ("post", "/api/duplicados/fusionar/", {}),
    "clinica.config": ("get", "/api/clinica/", None),
    "captacion.config": ("get", "/api/captacion/config/", None),
    "whatsapp.config": ("get", "/api/whatsapp/config/", None),
    "mensajes.bitacora": ("get", "/api/mensajes/", None),
    "faro.alertas": ("get", "/api/faro/panel/alertas/", None),
    "leads.lista": ("get", "/api/leads/", None),
    "integraciones.respaldo_sin_token": ("get", "/api/integraciones/respaldo/?resumen=1", None),
    "consentimientos.editar": ("patch", "/api/consentimientos/{consentimiento_ajeno}/", {"texto": "x"}),
    "cobros.lista": ("get", "/api/cobros/", None),
    "cobros.crear": ("post", "/api/cobros/", {}),
    "cobros.corregir_monto_ajeno": ("patch", "/api/cobros/{cobro_ajeno}/", {"monto": "1"}),
    "cobros.eliminar": ("delete", "/api/cobros/999999/", None),
    "paquetes.anular": ("post", "/api/paquetes/999999/anular/", {}),
    "paquetes.vender": ("post", "/api/paquetes/", {}),
}

def _fila(*codigos):
    return dict(zip(ROLES, codigos))


# Política vigente al 1 oct 2026 (tras los arreglos P0-S). Orden de columnas: anonimo, admin, asistente, medico, comercial, analista.
MATRIZ = {
    "pacientes.lista": _fila(403, 200, 200, 200, 200, 200),            # comercial: 200 con lista vacía
    "pacientes.propio": _fila(403, 200, 200, 200, 404, 200),
    "pacientes.ajeno": _fila(403, 200, 200, 404, 404, 200),
    "atenciones.ajena": _fila(403, 200, 200, 404, 404, 200),
    "adjuntos.descargar_propio": _fila(403, 200, 200, 200, 404, 200),  # P0-S1
    "adjuntos.descargar_ajeno": _fila(403, 200, 200, 404, 404, 200),   # P0-S1
    "consentimientos.ajeno": _fila(403, 200, 200, 404, 404, 404),      # P0-S2
    "riesgo.ver_ajena": _fila(403, 200, 200, 404, 404, 200),           # P0-S4
    "riesgo.resolver_propia": _fila(403, 400, 403, 400, 403, 403),     # P0-S4: 400 = autorizado
    "riesgo.resolver_ajena": _fila(403, 400, 403, 404, 403, 403),      # P0-S4
    "continuidad.pendientes": _fila(403, 200, 200, 200, 200, 200),
    "continuidad.caso_ajeno": _fila(403, 200, 200, 404, 404, 200),
    "gerencia.resumen": _fila(403, 200, 403, 403, 403, 200),
    "finanzas.caja": _fila(403, 200, 403, 403, 403, 200),
    "finanzas.liquidacion": _fila(403, 200, 403, 403, 403, 403),
    "finanzas.egresos": _fila(403, 200, 403, 403, 403, 200),
    "finanzas.egreso_borrar": _fila(403, 204, 403, 403, 403, 403),
    "usuarios.lista": _fila(403, 200, 403, 403, 403, 403),
    "usuarios.crear": _fila(403, 400, 403, 403, 403, 403),
    "duplicados.lista": _fila(403, 200, 200, 403, 403, 403),
    "duplicados.fusionar": _fila(403, 400, 400, 403, 403, 403),
    "clinica.config": _fila(403, 200, 200, 200, 200, 200),
    "captacion.config": _fila(403, 200, 200, 200, 200, 403),
    "whatsapp.config": _fila(403, 200, 403, 403, 403, 403),
    "mensajes.bitacora": _fila(403, 200, 200, 200, 200, 200),          # analista: vacía; médico: solo sus pacientes
    # BRECHA CONOCIDA (fase 1): cualquier psicólogo ve todas las alertas de Faro.
    "faro.alertas": _fila(403, 200, 403, 200, 403, 403),
    # BRECHA CONOCIDA (fase 1): el psicólogo recibe el contacto de los leads.
    "leads.lista": _fila(403, 200, 200, 200, 200, 200),
    "integraciones.respaldo_sin_token": _fila(403, 403, 403, 403, 403, 403),
    # Fase 1: consentimiento inmutable por API; cobros con alcance por rol.
    "consentimientos.editar": _fila(403, 405, 405, 405, 405, 403),
    "cobros.lista": _fila(403, 200, 200, 200, 200, 200),             # psicólogo: solo sus pacientes; comercial: vacía
    "cobros.crear": _fila(403, 400, 400, 403, 403, 403),             # 400 = autorizado (cuerpo vacío)
    "cobros.corregir_monto_ajeno": _fila(403, 200, 403, 404, 404, 403),  # monto: solo gerencia
    "cobros.eliminar": _fila(403, 404, 404, 403, 403, 403),          # 404 = autorizado (id inexistente)
    "paquetes.anular": _fila(403, 404, 404, 403, 403, 403),
    "paquetes.vender": _fila(403, 400, 400, 403, 403, 403),           # genera un cobro pagado: caja
}


@override_settings(MEDIA_ROOT=os.path.join(os.environ.get("TEMP", "/tmp"), "itaca-matriz-media"))
class MatrizDePermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-matriz")
        crear = Usuario.objects.create_user
        cls.usuarios = {
            rol: crear(email=f"{rol}@matriz.pe", password="x", clinica=cls.clinica, rol=rol)
            for rol in ("admin", "asistente", "medico", "comercial", "analista")
        }
        otro = crear(email="otro@matriz.pe", password="x", clinica=cls.clinica, rol="medico")
        ficha = Profesional.objects.create(clinica=cls.clinica, usuario=cls.usuarios["medico"], nombre="Psico")
        otra = Profesional.objects.create(clinica=cls.clinica, usuario=otro, nombre="Otro")
        mio = Paciente.objects.create(clinica=cls.clinica, nombre="Ana Mía", profesional=ficha)
        ajeno = Paciente.objects.create(clinica=cls.clinica, nombre="Luis Ajeno", profesional=otra)
        atencion = Atencion.objects.create(clinica=cls.clinica, paciente=ajeno, medico=otro)

        def adjunto(p):
            return Adjunto.objects.create(clinica=cls.clinica, paciente=p, nombre="a.pdf", tipo="pdf",
                                          archivo=SimpleUploadedFile("a.pdf", b"%PDF"))

        cls.ids = {
            "mio": mio.id, "ajeno": ajeno.id, "atencion_ajena": atencion.id,
            "adjunto_mio": adjunto(mio).id, "adjunto_ajeno": adjunto(ajeno).id,
            "consentimiento_ajeno": Consentimiento.objects.create(
                clinica=cls.clinica, paciente=ajeno, texto="t", token=Consentimiento.nuevo_token()).id,
            "sugerencia_mia": SugerenciaRiesgo.objects.create(
                clinica=cls.clinica, paciente=mio, valor_sugerido="alto").id,
            "sugerencia_ajena": SugerenciaRiesgo.objects.create(
                clinica=cls.clinica, paciente=ajeno, valor_sugerido="alto").id,
            "egreso": Egreso.objects.create(clinica=cls.clinica, concepto="Luz", monto=10).id,
            "cobro_ajeno": Cobro.objects.create(clinica=cls.clinica, paciente=ajeno, monto=50, concepto="Sesión").id,
        }

    def _codigo(self, rol, clave):
        metodo, ruta, cuerpo = ENDPOINTS[clave]
        self.client.logout()
        if rol != "anonimo":
            self.client.force_login(self.usuarios[rol])
        kwargs = {"content_type": "application/json"} if cuerpo is not None else {}
        args = (cuerpo,) if cuerpo is not None else ()
        return getattr(self.client, metodo)(ruta.format(**self.ids), *args, **kwargs).status_code

    def test_matriz(self):
        real = {clave: {rol: self._codigo(rol, clave) for rol in ROLES} for clave in ENDPOINTS}
        if os.environ.get("ITACA_MATRIZ_GENERAR"):
            for clave, fila in real.items():
                print(f'    "{clave}": _fila({", ".join(str(fila[r]) for r in ROLES)}),')
            return
        escalan, restringen = [], []
        for clave, esperado in MATRIZ.items():
            for rol in ROLES:
                antes, ahora = esperado[rol], real[clave][rol]
                if antes == ahora:
                    continue
                celda = f"{clave} · {rol}: esperado {antes}, recibió {ahora}"
                (escalan if ahora < 400 <= antes else restringen).append(celda)
        faltan = sorted(set(ENDPOINTS) - set(MATRIZ))
        self.assertFalse(escalan, "ESCALAMIENTO DE PRIVILEGIOS:\n" + "\n".join(escalan))
        self.assertFalse(restringen, "La política cambió (más restrictiva o distinta):\n" + "\n".join(restringen))
        self.assertFalse(faltan, f"Endpoints sin fila en MATRIZ: {faltan}")

    def test_cobertura(self):
        self.assertGreaterEqual(len(MATRIZ) * len(ROLES), 200)
