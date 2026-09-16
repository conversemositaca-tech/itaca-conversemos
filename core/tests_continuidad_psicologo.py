"""El Centro de Continuidad visto por un PSICÓLOGO: sus pacientes, solo lectura.

El psicólogo ya podía abrir el Centro (la tarjeta de "Hoy" lo lleva ahí) y el
alcance por rol ya lo dejaba en sus propios pacientes. Lo que faltaba era que
la pantalla fuese de verdad de solo lectura: hasta ahora `medico` estaba en
ROLES_GESTION_CONTINUIDAD y podía guardar seguimiento.

Estas pruebas fijan las dos mitades del trato:

  - lo que SÍ puede: ver sus casos, filtrarlos y ordenarlos;
  - lo que NO: guardar gestión, cambiar responsable, contactar pacientes,
    ver el teléfono de nadie y asomarse al caso de un colega.

Y que nada de eso le quitó permisos a coordinación, gerencia ni dirección.

    python manage.py test core.tests_continuidad_psicologo
"""
from django.test import TestCase
from django.urls import get_resolver

from core import continuidad as C
from core.tests_continuidad_cola import _Base
from pacientes.models import GestionContinuidad, Paciente
from usuarios.models import Profesional, Usuario


class _BasePsicologo(_Base):
    """Dos psicólogos con pacientes propios, y los tres roles que sí gestionan."""

    def setUp(self):
        super().setUp()
        # Psicóloga B: otra cuenta, otra ficha, otros pacientes.
        self.psico_b = Usuario.objects.create_user(
            email="psico-b@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, sede=Usuario.Sede.PIURA)
        self.ficha_b = Profesional.objects.create(
            clinica=self.clinica, usuario=self.psico_b, nombre="Colega B", sede="piura")

        self.coord = Usuario.objects.create_user(
            email="coord-psi@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA)
        self.admin = Usuario.objects.create_user(
            email="adm-psi@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.analista = Usuario.objects.create_user(
            email="ana-psi@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ANALISTA)

        # Un caso vencido de cada psicóloga, los dos en la cola.
        self.mio = self._paciente("Mío de A", ficha=self.ficha, telefono="+51999111222")
        self._asistidas(self.mio, 6, ultima_hace=10)
        self.ajeno = self._paciente("Ajeno de B", ficha=self.ficha_b, telefono="+51999333444")
        self._asistidas(self.ajeno, 6, ultima_hace=12)

    # --- atajos ------------------------------------------------------------

    def _lista(self, usuario, **params):
        self.client.force_login(usuario)
        q = "&".join(f"{k}={v}" for k, v in params.items() if v not in ("", None))
        return self.client.get(f"/api/continuidad/pendientes/?{q}").json()

    def _nombres(self, usuario, **params):
        return [f["paciente"] for f in self._lista(usuario, **params)["filas"]]

    def _caso(self, usuario, paciente):
        self.client.force_login(usuario)
        return self.client.get(f"/api/continuidad/caso/{paciente.id}/")

    def _guardar(self, usuario, paciente, datos):
        self.client.force_login(usuario)
        return self.client.patch(f"/api/continuidad/caso/{paciente.id}/gestion/",
                                 datos, content_type="application/json")


class AlcanceDelPsicologoTests(_BasePsicologo):
    """1-4, 11, 12: qué ve y hasta dónde llega."""

    def test_el_psicologo_solo_ve_sus_pacientes(self):
        self.assertEqual(self._nombres(self.psico, estado="todos"), ["Mío de A"])

    def test_el_psicologo_no_ve_los_pacientes_del_colega(self):
        nombres = self._nombres(self.psico, estado="todos")
        self.assertNotIn("Ajeno de B", nombres)
        # Y al revés, para que no sea un test que pasa porque B no tiene casos.
        self.assertEqual(self._nombres(self.psico_b, estado="todos"), ["Ajeno de B"])

    def test_los_query_params_no_lo_sacan_de_sus_pacientes(self):
        """Pedir explícitamente la ficha del colega no amplía nada: la lista se
        arma sobre `pacientes_del_rol`, y el filtro solo puede achicarla."""
        forzados = [
            {"estado": "todos", "medico": self.ficha_b.id},
            {"estado": "todos", "sede": "piura", "medico": self.ficha_b.id},
            {"estado": "vencido", "medico": self.ficha_b.id},
            {"estado": "todos", "revision": "sin_revisar", "medico": self.ficha_b.id},
        ]
        for params in forzados:
            d = self._lista(self.psico, **params)
            self.assertEqual(d["filas"], [], params)
        # Sin forzar nada sigue viendo lo suyo: el 0 de arriba es del filtro,
        # no de que la vista se haya roto.
        self.assertEqual(self._nombres(self.psico, estado="todos"), ["Mío de A"])

    def test_el_detalle_de_un_paciente_ajeno_responde_404(self):
        self.assertEqual(self._caso(self.psico, self.ajeno).status_code, 404)
        self.assertEqual(self._caso(self.psico, self.mio).status_code, 200)

    def test_los_filtros_y_el_orden_funcionan_dentro_de_sus_pacientes(self):
        for dias in (3, 40, 1):
            self._asistidas(self._paciente(f"A vencido {dias:03d}", ficha=self.ficha),
                            6, ultima_hace=dias)
        recientes = self._nombres(self.psico, estado="vencido", orden="recientes")
        self.assertEqual(recientes, ["A vencido 001", "A vencido 003", "Mío de A", "A vencido 040"])
        self.assertEqual(self._nombres(self.psico, estado="vencido", orden="antiguos"),
                         list(reversed(recientes)))
        self.assertNotIn("Ajeno de B", recientes)

    def test_la_sede_se_sigue_respetando(self):
        """Filtrar por sede acota; nunca abre. Sobre los pacientes del psicólogo
        y, para coordinación, dentro de su propia sede."""
        lima = self._paciente("Mío en Lima", sede="lima", ficha=self.ficha)
        self._asistidas(lima, 6, ultima_hace=5)
        self.assertEqual(self._nombres(self.psico, estado="todos", sede="lima"), ["Mío en Lima"])
        self.assertEqual(sorted(self._nombres(self.psico, estado="todos", sede="piura")), ["Mío de A"])
        # La coordinadora de Piura no alcanza Lima ni pidiéndolo.
        self.assertEqual(self._nombres(self.coord, estado="todos", sede="lima"), [])

    def test_un_psicologo_sin_ficha_enlazada_no_ve_nada(self):
        """Falla cerrado: sin `Profesional` enlazado no se asume 'todos'."""
        suelto = Usuario.objects.create_user(email="suelto@test.pe", password="x",
                                             clinica=self.clinica, rol=Usuario.Rol.MEDICO)
        self.assertEqual(self._lista(suelto, estado="todos")["total"], 0)


class SoloLecturaDelPsicologoTests(_BasePsicologo):
    """5-8, 13, 14: lo que no puede hacer, comprobado contra el servidor."""

    def test_el_psicologo_no_puede_guardar_seguimiento(self):
        r = self._guardar(self.psico, self.mio, {"estado_revision": "en_seguimiento"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(GestionContinuidad.objects.filter(paciente=self.mio).exists())

    def test_el_psicologo_no_puede_cambiar_el_responsable(self):
        """Ni siquiera uno que coordinación ya dejó puesto."""
        self.assertEqual(
            self._guardar(self.coord, self.mio, {"responsable": "coordinacion"}).status_code, 200)
        g = GestionContinuidad.objects.get(paciente=self.mio)
        self.assertEqual(g.responsable, "coordinacion")

        self.assertEqual(
            self._guardar(self.psico, self.mio, {"responsable": "psicologo"}).status_code, 403)
        g.refresh_from_db()
        self.assertEqual(g.responsable, "coordinacion")

    def test_el_psicologo_no_puede_contactar_por_whatsapp(self):
        """Ni preparar el mensaje, ni enviarlo, ni registrar lo que 'contestó'."""
        self.client.force_login(self.psico)
        base = f"/api/continuidad/caso/{self.mio.id}/whatsapp/"
        self.assertEqual(self.client.get(base).status_code, 403)
        self.assertEqual(self.client.post(base, {"texto": "hola"},
                                          content_type="application/json").status_code, 403)
        for ruta, cuerpo in (("reintentar/", {}), ("copiado/", {}), ("respuesta/", {"respuesta": "confirmo"})):
            r = self.client.post(base + ruta, cuerpo, content_type="application/json")
            self.assertEqual(r.status_code, 403, ruta)

    def test_no_hay_endpoint_de_exportacion_que_saltarse(self):
        """La exportación del Centro se arma en el navegador, no en el servidor.

        Si algún día se agrega una de verdad, esta prueba falla y obliga a
        decidir qué roles pueden usarla —en vez de que nazca abierta.
        """
        rutas = [str(p.pattern) for p in get_resolver().url_patterns]
        self.assertEqual([r for r in rutas if "export" in r.lower()], [])

    def test_el_detalle_le_dice_al_frontend_que_no_edita(self):
        """Las banderas que apagan los controles de la pantalla. Son las mismas
        que el servidor usa para rechazar, así que no pueden desalinearse."""
        d = self._caso(self.psico, self.mio).json()
        self.assertFalse(d["puede_gestionar"])
        self.assertFalse(d["contacto"]["puede_contactar"])

    def test_el_backend_bloquea_aunque_se_fuerce_el_request_completo(self):
        """Ocultar el botón no es la defensa: el PATCH con todo el payload,
        contra un paciente que SÍ es suyo, se rechaza igual."""
        r = self._guardar(self.psico, self.mio, {
            "estado_revision": "resuelto",
            "resultado_operativo": "ya_actualizado",
            "responsable": "psicologo",
            "observacion_operativa": "forzado a mano",
        })
        self.assertEqual(r.status_code, 403)
        self.assertFalse(GestionContinuidad.objects.filter(paciente=self.mio).exists())


class PrivacidadDelContactoTests(_BasePsicologo):
    """El detalle del caso no es la puerta lateral al teléfono del paciente.

    `ROLES_SIN_CONTACTO` (psicólogo y analista) existe por la Ley 29733, pero
    `contacto.canal` venía con el número dentro para cualquiera que pudiera ver
    el caso. Aquí se fija que no.
    """

    def _canal(self, usuario):
        return self._caso(usuario, self.mio).json()["contacto"]["canal"]

    def test_el_psicologo_no_recibe_el_telefono_de_su_paciente(self):
        self.assertEqual(self._canal(self.psico)["telefono"], "")

    def test_la_analista_tampoco(self):
        self.assertEqual(self._canal(self.analista)["telefono"], "")

    def test_coordinacion_y_gerencia_si_lo_reciben(self):
        """Son quienes escriben: taparlo les impediría comprobar el destino."""
        for usuario in (self.coord, self.admin):
            self.assertEqual(self._canal(usuario)["telefono"], "+51999111222", usuario.rol)

    def test_tampoco_llega_el_nombre_del_tutor(self):
        menor = self._paciente("Menor de A", ficha=self.ficha, telefono="",
                               tutor_telefono="+51999555666", tutor_nombre="Madre Ejemplo",
                               tutor_parentesco="madre")
        self._asistidas(menor, 6, ultima_hace=8)
        self.client.force_login(self.psico)
        canal = self.client.get(f"/api/continuidad/caso/{menor.id}/").json()["contacto"]["canal"]
        self.assertEqual((canal["telefono"], canal["tutor_nombre"], canal["tutor_parentesco"]),
                         ("", "", ""))
        # La línea de la clínica sí: es dato operativo, no del paciente.
        self.assertEqual(canal["sede"], "piura")

        self.client.force_login(self.coord)
        canal = self.client.get(f"/api/continuidad/caso/{menor.id}/").json()["contacto"]["canal"]
        self.assertEqual(canal["tutor_nombre"], "Madre Ejemplo")


class LosDemasRolesNoPierdenNadaTests(_BasePsicologo):
    """9 y 10: quitarle la escritura al psicólogo no le tocó nada a nadie más."""

    def test_la_coordinadora_conserva_sus_permisos(self):
        self.assertEqual(
            self._guardar(self.coord, self.mio, {"estado_revision": "en_seguimiento"}).status_code, 200)
        d = self._caso(self.coord, self.mio).json()
        self.assertTrue(d["puede_gestionar"])
        self.assertTrue(d["contacto"]["puede_contactar"])
        # Y sigue viendo a los pacientes de AMBAS psicólogas de su sede.
        self.assertEqual(sorted(self._nombres(self.coord, estado="todos")),
                         ["Ajeno de B", "Mío de A"])

    def test_gerencia_conserva_sus_permisos(self):
        self.assertEqual(
            self._guardar(self.admin, self.mio, {"estado_revision": "resuelto"}).status_code, 200)
        d = self._caso(self.admin, self.mio).json()
        self.assertTrue(d["puede_gestionar"])
        self.assertTrue(d["contacto"]["puede_contactar"])

    def test_direccion_clinica_conserva_su_excepcion_de_escritura(self):
        """La analista es de solo lectura en TODA la API menos aquí; eso no
        cambió. Contactar pacientes sigue sin ser suyo."""
        self.assertEqual(
            self._guardar(self.analista, self.mio, {"estado_revision": "en_seguimiento"}).status_code, 200)
        d = self._caso(self.analista, self.mio).json()
        self.assertTrue(d["puede_gestionar"])
        self.assertFalse(d["contacto"]["puede_contactar"])

    def test_el_comercial_sigue_sin_ver_el_centro(self):
        com = Usuario.objects.create_user(email="com-psi@test.pe", password="x",
                                          clinica=self.clinica, rol=Usuario.Rol.COMERCIAL)
        self.assertEqual(self._lista(com, estado="todos")["total"], 0)

    def test_la_tabla_de_roles_que_gestionan_deja_fuera_al_psicologo(self):
        from core import permisos

        self.assertNotIn("medico", permisos.ROLES_GESTION_CONTINUIDAD)
        self.assertEqual(set(permisos.ROLES_GESTION_CONTINUIDAD),
                         {"admin", "asistente", "analista"})
        self.assertFalse(permisos.puede_gestionar_continuidad(self.psico))
        self.assertTrue(permisos.puede_gestionar_continuidad(self.coord))


class ElPsicologoSiVeSuCasoTests(_BasePsicologo):
    """Solo lectura no es 'casi nada': la vista tiene que servirle."""

    def test_ve_la_situacion_completa_de_su_caso(self):
        fila = self._lista(self.psico, estado="todos")["filas"][0]
        for clave in ("paciente", "estado", "grupo", "n_sesion", "meta", "fecha_cierre",
                      "proxima_fecha", "ultima_sesion", "avisos", "anteriores_sin_decision",
                      "proceso", "contexto", "que_confirmar", "dias"):
            self.assertIn(clave, fila, clave)

    def test_ve_los_mismos_chips_que_los_demas(self):
        """Los contadores por estado, para poder filtrar como cualquier otro rol
        —solo que sobre sus pacientes."""
        conteo = self._lista(self.psico, estado="todos")["conteo"]
        for chip in ("accionables", "vencido", "hoy", "riesgo_s3", "sin_agendar", "proximo",
                     "continuo_sin_decision", "dato_incompleto", "backlog", "proceso_anterior"):
            self.assertIn(chip, conteo, chip)
        self.assertEqual(conteo[C.EstadoCierre.VENCIDO], 1)

    def test_ve_el_historial_operativo_del_caso(self):
        """Lo que coordinación ya hizo con el caso: puede leerlo, no cambiarlo."""
        self._guardar(self.coord, self.mio, {"estado_revision": "en_seguimiento",
                                             "responsable": "coordinacion"})
        d = self._caso(self.psico, self.mio).json()
        self.assertEqual(d["gestion"]["estado_revision"], "en_seguimiento")
        self.assertEqual(d["gestion"]["responsable"], "coordinacion")
        self.assertTrue(d["historial_gestion"])
        self.assertFalse(d["puede_gestionar"])
