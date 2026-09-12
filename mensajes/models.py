import uuid

from django.conf import settings
from django.db import models

from core.models import ModeloTenant


class Mensaje(ModeloTenant):
    """Bitácora de mensajes de WhatsApp enviados (o intentados) por la clínica.

    Queda registro de qué se mandó, a quién y con qué resultado (auditoría +
    historial). Es append-only en la práctica: se registra cada envío."""

    class Tipo(models.TextChoices):
        RECORDATORIO = "recordatorio", "Recordatorio de cita"
        CONFIRMACION = "confirmacion", "Confirmación"
        SEGUIMIENTO = "seguimiento", "Seguimiento"
        # Respuesta que el sistema envía solo a un lead que preguntó por WhatsApp
        # (precios, tipos de terapia, ubicación…): leads/whatsapp_auto.py.
        AUTOMATICO = "automatico", "Respuesta automática"
        # Contacto que coordinación hace desde el Centro de Continuidad para
        # preguntarle al paciente si sigue con su proceso. Lo escribe una
        # persona (revisa la plantilla antes de enviar) y sale por la línea de
        # SU sede, igual que un recordatorio.
        CONTINUIDAD = "continuidad", "Contacto de continuidad"
        MANUAL = "manual", "Mensaje manual"

    class Estado(models.TextChoices):
        # Los tres primeros son los de siempre: NO cambiar sus valores, la
        # bitácora vieja los tiene guardados así.
        ENVIADO = "enviado", "Enviado"
        FALLIDO = "fallido", "Falló"
        NO_CONFIGURADO = "no_configurado", "Sin WhatsApp"
        # Parte de una comunicación con imágenes que todavía no se intentó. Las
        # partes se crean ANTES de empezar a enviar: si algo se corta a mitad,
        # esta fila es la que sabe qué faltaba. Un mensaje suelto nunca la usa.
        PENDIENTE = "pendiente", "Pendiente de envío"
        # Los que agrega el webhook de Evolution: el ciclo de vida real del
        # mensaje (lo que se ve como ✓, ✓✓ y ✓✓ azul en el celular).
        RECIBIDO = "recibido", "Recibido"
        ENTREGADO = "entregado", "Entregado"
        LEIDO = "leido", "Leído"

    class Proveedor(models.TextChoices):
        META = "meta", "WhatsApp Cloud (Meta)"
        EVOLUTION = "evolution", "Evolution API"
        MANUAL = "manual", "Manual (wa.me)"

    class Direccion(models.TextChoices):
        SALIENTE = "saliente", "Enviado"
        ENTRANTE = "entrante", "Recibido"

    # Orden del ciclo de vida de un mensaje SALIENTE. Sirve para que un acuse que
    # llega tarde o desordenado no haga retroceder el estado (WhatsApp manda los
    # acuses por su cuenta: el "leído" puede llegar antes que el "entregado").
    # Los estados que no están aquí (fallido, no_configurado, recibido) no entran
    # en la comparación: no son parte de esa escalera.
    ORDEN_ESTADO = {
        Estado.ENVIADO: 1,
        Estado.ENTREGADO: 2,
        Estado.LEIDO: 3,
    }

    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )
    cita = models.ForeignKey(
        "pacientes.Cita", on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )
    telefono = models.CharField(max_length=40, blank=True)
    texto = models.TextField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MANUAL)
    estado = models.CharField(max_length=20, choices=Estado.choices)
    detalle = models.CharField(max_length=300, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )
    # --- Trazabilidad (agregado con las instancias de Evolution por sede) ---
    # Los mensajes anteriores a este cambio quedan con proveedor vacío: no se
    # puede saber a posteriori por dónde salieron, y adivinar sería peor que
    # dejarlo en blanco.
    proveedor = models.CharField(max_length=12, choices=Proveedor.choices, blank=True, default="")
    direccion = models.CharField(max_length=10, choices=Direccion.choices,
                                 default=Direccion.SALIENTE)
    sede = models.CharField(max_length=10, blank=True, default="")
    instancia = models.CharField("Instancia / línea", max_length=120, blank=True, default="",
                                 help_text="Instancia de Evolution que envió o recibió el mensaje.")
    # Id que le pone WhatsApp al mensaje (key.id). Es la llave para casar los
    # acuses de entrega y para no procesar dos veces el mismo evento.
    external_message_id = models.CharField(max_length=180, blank=True, default="")
    error_codigo = models.CharField(max_length=40, blank=True, default="")
    actualizado_en = models.DateTimeField(auto_now=True)
    # Qué plantilla se usó y qué decía ANTES de que la editaran. Si nadie tocó
    # el texto, `texto_original` queda vacío (no se guarda dos veces lo mismo).
    # Así la auditoría muestra lo que el sistema propuso y lo que la persona
    # realmente envió, aunque después alguien edite la plantilla.
    plantilla_clave = models.CharField(max_length=40, blank=True, default="")
    texto_original = models.TextField(blank=True, default="")
    # Caso del Centro de Continuidad que motivó el contacto. Solo lo llenan los
    # mensajes enviados desde ahí: así el panel puede mostrar qué se le escribió
    # a este paciente por ESTE caso, sin partir en dos la bitácora (el historial
    # de WhatsApp del paciente sigue siendo uno solo, en su ficha).
    gestion_continuidad = models.ForeignKey(
        "pacientes.GestionContinuidad", on_delete=models.SET_NULL,
        related_name="mensajes", null=True, blank=True,
    )

    # --- Una comunicación puede necesitar varios mensajes ---------------------
    # WhatsApp no tiene álbum: tres imágenes y un texto son CUATRO mensajes para
    # el proveedor. `grupo_envio` los une para que Coordinación vea una sola
    # comunicación en el historial, y para que "reintentar lo que falta" sepa
    # qué partes ya salieron. Un mensaje suelto lo deja en null: la bitácora
    # vieja no cambia.
    grupo_envio = models.UUIDField(null=True, blank=True, db_index=True)
    orden = models.PositiveSmallIntegerField(default=0)
    # Qué pieza de la biblioteca se envió en esta parte (vacío si es el texto).
    material = models.ForeignKey(
        "mensajes.Material", on_delete=models.SET_NULL,
        related_name="mensajes", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["clinica", "-creado_en"]),
            models.Index(fields=["clinica", "external_message_id"]),
            models.Index(fields=["clinica", "gestion_continuidad"]),
        ]
        constraints = [
            # La deduplicación la sostiene la BASE DE DATOS, no un `if` en Python:
            # Evolution reintenta el webhook cuando no le respondemos rápido, y dos
            # reintentos a la vez pasarían cualquier chequeo previo. Los mensajes
            # sin id (los históricos, los que fallaron antes de salir) quedan fuera
            # del constraint.
            models.UniqueConstraint(
                fields=["clinica", "external_message_id"],
                condition=~models.Q(external_message_id=""),
                name="uniq_mensaje_external_id",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.telefono} · {self.estado}"

    def avanzar_estado(self, nuevo, *, detalle="", error_codigo=""):
        """Mueve el estado hacia adelante en la escalera enviado→entregado→leído.

        Devuelve True si guardó. Un acuse que llega tarde (el "entregado" después
        del "leído") NO retrocede el estado: en la bitácora quedaría como si el
        paciente no hubiera leído algo que ya leyó.
        """
        if nuevo not in self.ORDEN_ESTADO:
            return False
        actual = self.ORDEN_ESTADO.get(self.estado, 0)
        if self.ORDEN_ESTADO[nuevo] <= actual:
            return False
        self.estado = nuevo
        campos = ["estado", "actualizado_en"]
        if detalle:
            self.detalle = detalle[:300]
            campos.append("detalle")
        if error_codigo:
            self.error_codigo = error_codigo[:40]
            campos.append("error_codigo")
        self.save(update_fields=campos)
        return True


# --- Biblioteca de material compartible ---------------------------------------
# Las piezas que Coordinación manda por WhatsApp (ubicación, horarios, tarifas,
# medios de pago, cómo entrar a la sesión online). NO es material clínico: los
# estudios e informes de un paciente viven en pacientes.Adjunto, con otro
# control de acceso (Ley 29733). Están separados a propósito, para que una
# ecografía no pueda aparecer nunca en el selector del compositor.

TIPOS_MATERIAL = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def ruta_material(instance, filename):
    """Ruta en disco, aislada por clínica y con nombre propio.

    El nombre que traía el archivo del PC de la coordinadora no se usa como
    ruta: se guarda aparte, en `nombre`, y en disco va un uuid. Así ni un
    nombre con acentos, espacios o barras toca el sistema de archivos.
    """
    ext = TIPOS_MATERIAL.get(getattr(instance, "mime", ""), "bin")
    return f"material/clinica_{instance.clinica_id}/{uuid.uuid4().hex}.{ext}"


class Material(ModeloTenant):
    """Una pieza de la biblioteca compartible de la clínica."""

    class Categoria(models.TextChoices):
        UBICACIONES = "ubicaciones", "Ubicaciones"
        HORARIOS = "horarios", "Horarios"
        TARIFAS = "tarifas", "Tarifas"
        PAGOS = "pagos", "Medios de pago"
        ONLINE = "online", "Sesiones online"
        POLITICAS = "politicas", "Políticas"
        PACIENTES = "pacientes", "Material para pacientes"
        OTROS = "otros", "Otros"

    nombre = models.CharField(max_length=200)
    archivo = models.FileField(upload_to=ruta_material)
    categoria = models.CharField(max_length=20, choices=Categoria.choices,
                                 default=Categoria.OTROS)
    # "" = sirve para las dos sedes. No restringe el envío: es una ayuda para
    # encontrar la pieza correcta, no un candado.
    sede = models.CharField(max_length=10, blank=True, default="")
    # El tipo REAL, leído de la cabecera del archivo (mensajes/materiales.py),
    # no el Content-Type que manda el navegador.
    mime = models.CharField(max_length=40)
    tamano = models.PositiveIntegerField(default=0)
    ancho = models.PositiveSmallIntegerField(default=0)
    alto = models.PositiveSmallIntegerField(default=0)
    # SHA-256 del contenido: es lo que impide subir dos veces la misma imagen.
    hash = models.CharField(max_length=64, db_index=True)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   related_name="materiales", null=True, blank=True)
    # Baja lógica: una pieza retirada no puede desaparecer, porque los mensajes
    # ya enviados la referencian y el historial dejaría de cuadrar.
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Material de WhatsApp"
        verbose_name_plural = "Materiales de WhatsApp"
        ordering = ["categoria", "nombre"]
        indexes = [
            models.Index(fields=["clinica", "categoria", "activo"]),
            models.Index(fields=["clinica", "activo"]),
        ]
        constraints = [
            # La deduplicación la sostiene la base, no un `if`: dos coordinadoras
            # subiendo la misma pieza a la vez pasarían cualquier chequeo previo.
            models.UniqueConstraint(
                fields=["clinica", "hash"], condition=models.Q(activo=True),
                name="uniq_material_hash",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def sede_label(self):
        return {"lima": "Lima", "piura": "Piura"}.get(self.sede, "Ambas sedes")

    def leer_bytes(self):
        with self.archivo.open("rb") as f:
            return f.read()



class PlantillaMensaje(ModeloTenant):
    """Plantilla de mensaje de WhatsApp con variables. La gestiona el gerente.
    Variables: {nombre} {psicologo} {fecha} {hora} {n_sesion} {sede} {clinica}."""

    clave = models.CharField(max_length=30, help_text="recordatorio, confirmacion, pago, ubicacion, politicas, consentimiento…")
    nombre = models.CharField(max_length=120)
    texto = models.TextField()
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    # --- Plantilla aprobada de WhatsApp Cloud (HSM), para envíos proactivos ---
    # Si wa_template_nombre está puesto, los envíos por Cloud API usan la plantilla
    # aprobada en Meta (se entrega aunque hayan pasado >24h). Si está vacío, se envía
    # texto libre (solo dentro de la ventana de 24h).
    wa_template_nombre = models.CharField(
        "Plantilla aprobada (Meta)", max_length=120, blank=True, default="",
        help_text="Nombre EXACTO de la plantilla aprobada en Meta WhatsApp Manager.")
    wa_template_idioma = models.CharField(
        "Idioma de la plantilla", max_length=10, blank=True, default="es",
        help_text="Código de idioma de la plantilla aprobada (ej. es, es_ES, es_MX).")
    wa_template_vars = models.CharField(
        "Variables de la plantilla", max_length=200, blank=True, default="",
        help_text="Variables que llenan {{1}},{{2}}… en orden, separadas por coma. Ej: nombre o nombre,clinica")

    class Meta:
        verbose_name = "Plantilla de mensaje"
        verbose_name_plural = "Plantillas de mensaje"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "clave"], name="uniq_plantilla_clave")
        ]

    def __str__(self):
        return self.nombre


VARIABLES_PLANTILLA = ["nombre", "psicologo", "fecha", "hora", "n_sesion", "sede", "clinica",
                       "coordinadora"]


def valores_plantilla(paciente=None, cita=None, clinica=None, usuario=None):
    """Devuelve el dict de variables {nombre, psicologo, fecha, …} con sus valores.

    `usuario` (opcional) llena {coordinadora} con el primer nombre de quien
    envía: un mensaje de continuidad lo firma la persona que escribe, no "el
    sistema". Si no se pasa, queda vacío y las plantillas de siempre no cambian.
    """
    from django.utils import timezone

    nombre = (paciente.nombre.split(" ")[0] if paciente and paciente.nombre else "")
    psicologo, fecha, hora = "", "", ""
    if cita is not None:
        loc = timezone.localtime(cita.inicio)
        fecha, hora = loc.strftime("%d/%m/%Y"), loc.strftime("%H:%M")
        if cita.medico_id:
            psicologo = str(cita.medico)
    if not psicologo and paciente is not None and paciente.profesional_id:
        psicologo = paciente.profesional.nombre
    # Anteponer "psic." al nombre (los mensajes deben decir "psic. Karol García").
    if psicologo and not psicologo.lower().startswith(("psic", "lic", "dr", "dra", "ps.")):
        psicologo = f"psic. {psicologo}"
    n_sesion = ""
    if paciente is not None:
        from core.continuidad import sesion_real_de_paciente
        # La sesión real sale de las citas asistidas, no del contador manual
        # Paciente.n_sesion (se queda en 0 salvo que alguien use "Registrar
        # sesión" a propósito) — para no mandarle al paciente un WhatsApp que
        # diga "tu sesión N° 0" cuando en realidad va por la 10.
        n_sesion = str(sesion_real_de_paciente(paciente))
    sede = paciente.get_sede_display() if (paciente and paciente.sede) else ""
    cl = clinica or (paciente.clinica if paciente else None) or (cita.clinica if cita else None)
    coordinadora = ""
    if usuario is not None:
        completo = (getattr(usuario, "nombre", "") or "").strip()
        coordinadora = completo.split(" ")[0] if completo else ""
    return {
        "nombre": nombre, "psicologo": psicologo, "fecha": fecha, "hora": hora,
        "n_sesion": n_sesion, "sede": sede, "clinica": cl.nombre if cl else "",
        "coordinadora": coordinadora,
    }


def render_plantilla(texto, paciente=None, cita=None, clinica=None, usuario=None):
    """Sustituye las variables {...} de una plantilla con datos del paciente/cita."""
    repl = valores_plantilla(paciente=paciente, cita=cita, clinica=clinica, usuario=usuario)
    out = texto or ""
    for k, v in repl.items():
        out = out.replace("{" + k + "}", v)
    return out


def params_plantilla(plantilla, paciente=None, cita=None, clinica=None):
    """Valores ordenados para {{1}},{{2}}… de una plantilla aprobada (HSM),
    según el campo wa_template_vars (lista de variables separadas por coma)."""
    repl = valores_plantilla(paciente=paciente, cita=cita, clinica=clinica)
    nombres = [v.strip() for v in (plantilla.wa_template_vars or "").split(",") if v.strip()]
    return [repl.get(v, "") for v in nombres]
