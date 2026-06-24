from decimal import Decimal, InvalidOperation

from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core import estructurar_nota, gcalendar, transcripcion
from core.tenant import get_clinica_actual
from mensajes.models import Mensaje
from mensajes.services import registrar_y_enviar

from .models import Adjunto, Atencion, Cita, Paciente, SeguimientoSesion
from .serializers import AdjuntoSerializer, AtencionSerializer, CitaSerializer, PacienteSerializer

# Tipos de archivo permitidos para adjuntos clínicos.
EXT_PERMITIDAS = {
    "pdf", "jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "heic",
    "doc", "docx", "xls", "xlsx", "txt", "dcm", "zip",
}
MAX_ADJUNTO_MB = 25


def _int_o_none(valor):
    try:
        s = str(valor).strip()
        return int(s) if s else None
    except (ValueError, TypeError):
        return None


def _dec_o_none(valor):
    try:
        s = str(valor).strip().replace(",", ".")
        return Decimal(s) if s else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _inicio_desde(fecha_str, hora_str):
    """Construye un datetime con zona horaria desde 'YYYY-MM-DD' (vacío = hoy)
    y 'HH:MM'. Lanza ValueError si el formato no es válido."""
    h, m = [int(x) for x in (hora_str or "").strip().split(":")]
    fecha_str = (fecha_str or "").strip()
    if fecha_str:
        y, mo, da = [int(x) for x in fecha_str.split("-")]
    else:
        hoy = timezone.localdate()
        y, mo, da = hoy.year, hoy.month, hoy.day
    return timezone.make_aware(timezone.datetime(y, mo, da, h, m))


def texto_recordatorio(cita):
    """Mensaje por defecto del recordatorio de una cita."""
    primer = cita.paciente.nombre.split(" ")[0]
    hora = timezone.localtime(cita.inicio).strftime("%H:%M")
    medico = str(cita.medico) if cita.medico_id else "tu profesional"
    return (
        f"Hola {primer} 👋 Te recordamos tu sesión en {cita.clinica.nombre} hoy a las "
        f"{hora} con {medico} ({cita.especialidad}). ¿Confirmas tu asistencia? "
        f"Responde SÍ para confirmar 🌿"
    )


def _es_medico(user):
    """True si el usuario es psicólogo (rol médico). El admin NO se acota."""
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.MEDICO


def _ficha_de(user):
    """Ficha del directorio (Profesional) enlazada a este usuario, o None."""
    from usuarios.models import Profesional
    return Profesional.objects.filter(usuario=user).first()


def _es_comercial(user):
    """El rol Comercial no accede a datos clínicos (pacientes, agenda, historias)."""
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.COMERCIAL


class PacienteViewSet(viewsets.ModelViewSet):
    """CRUD de pacientes, siempre con scope de la clínica activa.
    El psicólogo ve solo SUS pacientes; el admin, todos."""

    serializer_class = PacienteSerializer

    def get_queryset(self):
        qs = (
            Paciente.objects.del_tenant_actual()
            .prefetch_related("atenciones__adjuntos", "adjuntos", "cobros", "citas", "seguimientos")
        )
        if _es_comercial(self.request.user):
            return qs.none()
        # El psicólogo solo ve a los pacientes de su ficha del directorio.
        if _es_medico(self.request.user):
            ficha = _ficha_de(self.request.user)
            qs = qs.filter(profesional=ficha) if ficha else qs.none()
        prof = self.request.query_params.get("profesional")
        if prof:
            qs = qs.filter(profesional_id=prof)
        sede = self.request.query_params.get("sede")
        if sede:
            qs = qs.filter(sede=sede)
        return qs.order_by("nombre")

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())

    @action(detail=True, methods=["post"], url_path="registrar-sesion")
    def registrar_sesion(self, request, pk=None):
        """Registra (o actualiza) la sesión del paciente para una semana. Deja el
        'actual' del paciente sincronizado con la última semana registrada.
        Solo psicólogos (médicos) y administradores."""
        from usuarios.models import Usuario

        if getattr(request.user, "rol", None) not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            return Response({"detail": "Solo psicólogos y administradores pueden registrar sesiones."},
                            status=status.HTTP_403_FORBIDDEN)
        paciente = self.get_object()
        try:
            anio = int(request.data.get("anio"))
            mes = int(request.data.get("mes"))
            semana = int(request.data.get("semana"))
            n_sesion = int(request.data.get("n_sesion") or 0)
        except (TypeError, ValueError):
            return Response({"detail": "Año, mes, semana y N° de sesión deben ser números."},
                            status=status.HTTP_400_BAD_REQUEST)
        proceso = (request.data.get("proceso") or "").strip()

        SeguimientoSesion.objects.update_or_create(
            clinica=paciente.clinica, paciente=paciente, anio=anio, mes=mes, semana=semana,
            defaults={"n_sesion": n_sesion, "proceso": proceso},
        )
        # Sincronizar el 'actual' con la última semana registrada.
        ultimo = paciente.seguimientos.order_by("-anio", "-mes", "-semana").first()
        if ultimo:
            paciente.n_sesion = ultimo.n_sesion
            paciente.proceso = ultimo.proceso
            paciente.save(update_fields=["n_sesion", "proceso"])
        # Re-consultar (con prefetch fresco) para devolver el seguimiento actualizado.
        fresco = self.get_queryset().get(pk=paciente.pk)
        return Response(PacienteSerializer(fresco).data)

    @action(detail=True, methods=["post"])
    def mensaje(self, request, pk=None):
        """Envía un WhatsApp libre al paciente (p. ej. seguimiento / reactivación)."""
        paciente = self.get_object()
        texto = (request.data.get("texto") or "").strip()
        tipo = request.data.get("tipo") or Mensaje.Tipo.SEGUIMIENTO
        if not texto:
            return Response({"detail": "El mensaje no puede estar vacío."}, status=status.HTTP_400_BAD_REQUEST)
        if not paciente.telefono:
            return Response({"detail": "El paciente no tiene teléfono registrado."}, status=status.HTTP_400_BAD_REQUEST)
        mensaje, resultado, wa_url = registrar_y_enviar(
            paciente.clinica, telefono=paciente.telefono, texto=texto, tipo=tipo,
            paciente=paciente, usuario=request.user,
        )
        return Response({"estado": resultado["estado"], "detalle": resultado["detalle"],
                         "wa_url": wa_url, "mensaje_id": mensaje.id})


class CitaViewSet(viewsets.ModelViewSet):
    serializer_class = CitaSerializer

    def get_queryset(self):
        qs = (
            Cita.objects.del_tenant_actual()
            .select_related("paciente", "medico")
            .prefetch_related("cobros")
        )
        if _es_comercial(self.request.user):
            return qs.none()
        # El psicólogo ve solo SU agenda; el admin, la de toda la clínica.
        if _es_medico(self.request.user):
            qs = qs.filter(medico=self.request.user)
        return qs.order_by("inicio")

    def create(self, request, *args, **kwargs):
        """Agenda una cita. Recibe pacienteId, especialidad, hora (HH:MM) y
        fecha (YYYY-MM-DD; si no viene, es hoy). El médico queda en el primero
        disponible de la clínica (se ajustará al haber login)."""
        clinica = get_clinica_actual()
        paciente_id = request.data.get("pacienteId")
        especialidad = (request.data.get("especialidad") or "").strip()

        paciente = Paciente.objects.del_tenant_actual().filter(pk=paciente_id).first()
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            inicio = _inicio_desde(request.data.get("fecha"), request.data.get("hora"))
        except (ValueError, TypeError):
            return Response({"detail": "Fecha u hora inválida (usa fecha y HH:MM)."}, status=status.HTTP_400_BAD_REQUEST)

        from usuarios.models import Usuario

        # El médico de la cita: si la agenda un psicólogo, es él mismo; si es el
        # admin/gerente, puede indicar medicoId; por defecto, el primero de la clínica.
        if getattr(request.user, "rol", None) == Usuario.Rol.MEDICO:
            medico = request.user
        else:
            medico_id = request.data.get("medicoId")
            medico = (
                Usuario.objects.filter(clinica=clinica, rol=Usuario.Rol.MEDICO, pk=medico_id).first()
                if medico_id else None
            ) or Usuario.objects.filter(clinica=clinica, rol=Usuario.Rol.MEDICO).first()

        # Aviso (no bloqueante) si el mismo médico ya tiene una cita a esa hora.
        aviso = None
        if medico and Cita.objects.del_tenant_actual().filter(
            medico=medico, inicio=inicio
        ).exclude(estado=Cita.Estado.CANCELADA).exists():
            aviso = f"Aviso: {medico} ya tiene otra cita a las {timezone.localtime(inicio):%H:%M}."

        cita = Cita.objects.create(
            clinica=clinica,
            paciente=paciente,
            medico=medico,
            inicio=inicio,
            especialidad=especialidad or paciente.especialidad_habitual,
            estado=Cita.Estado.POR_CONFIRMAR,
        )
        gcalendar.sync_cita(cita)  # no-op si Google Calendar no está configurado
        data = CitaSerializer(cita).data
        if aviso:
            data["aviso"] = aviso
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def atender(self, request, pk=None):
        """Registra la atención en la historia clínica y marca la cita como atendida.

        Acepta campos estructurados (todos opcionales): motivo, signos vitales
        (presion_arterial, frecuencia_cardiaca, temperatura, peso, talla),
        diagnostico, indicaciones y la nota/evolución libre. Debe venir al menos
        uno de motivo / diagnostico / indicaciones / nota.
        Solo médicos y administradores pueden registrar atenciones.
        """
        from usuarios.models import Usuario

        if request.user.rol not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            return Response(
                {"detail": "Solo el personal médico puede registrar atenciones."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cita = self.get_object()
        d = request.data

        def limpio(clave):
            return (d.get(clave) or "").strip()

        motivo = limpio("motivo")
        diagnostico = limpio("diagnostico")
        indicaciones = limpio("indicaciones")
        nota = limpio("nota")
        aspectos_historicos = limpio("aspectos_historicos")
        objetivos = limpio("objetivos")
        puntos_importantes = limpio("puntos_importantes")
        proximos_pasos = limpio("proximos_pasos")
        tipo = d.get("tipo") if d.get("tipo") in dict(Atencion.Tipo.choices) else Atencion.Tipo.EVOLUCION
        contenido = [motivo, diagnostico, indicaciones, nota, aspectos_historicos,
                     objetivos, puntos_importantes, proximos_pasos]
        if not any(contenido):
            return Response(
                {"detail": "Registra al menos un campo de la ficha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        atencion = Atencion.objects.create(
            clinica=cita.clinica,
            paciente=cita.paciente,
            cita=cita,
            medico=cita.medico,
            registrado_por=request.user,
            especialidad=cita.especialidad,
            fecha=timezone.now(),
            tipo=tipo,
            motivo=motivo,
            presion_arterial=limpio("presion_arterial"),
            frecuencia_cardiaca=_int_o_none(d.get("frecuencia_cardiaca")),
            temperatura=_dec_o_none(d.get("temperatura")),
            peso=_dec_o_none(d.get("peso")),
            talla=_int_o_none(d.get("talla")),
            diagnostico=diagnostico,
            indicaciones=indicaciones,
            nota=nota,
            aspectos_historicos=aspectos_historicos,
            objetivos=objetivos,
            puntos_importantes=puntos_importantes,
            proximos_pasos=proximos_pasos,
        )

        # Cobro opcional en el mismo acto de atender (el médico cobra ahí mismo).
        cobro_monto = _dec_o_none(d.get("cobro_monto"))
        if cobro_monto and cobro_monto > 0:
            from finanzas.models import Cobro, Servicio

            servicio = (
                Servicio.objects.del_tenant_actual().filter(pk=d.get("cobro_servicio")).first()
                if d.get("cobro_servicio") else None
            )
            estado_cobro = d.get("cobro_estado") if d.get("cobro_estado") in dict(Cobro.Estado.choices) else Cobro.Estado.PAGADO
            medio = d.get("cobro_medio") if d.get("cobro_medio") in dict(Cobro.Medio.choices) else ""
            concepto = (str(d.get("cobro_concepto") or "").strip()
                        or (servicio.nombre if servicio else f"Consulta {cita.especialidad}".strip()))[:200]
            comprobante = d.get("cobro_comprobante") if d.get("cobro_comprobante") in dict(Cobro.Comprobante.choices) else ""
            Cobro.objects.create(
                clinica=cita.clinica, paciente=cita.paciente, atencion=atencion, cita=cita, servicio=servicio,
                concepto=concepto, monto=cobro_monto, estado=estado_cobro,
                medio_pago=medio if estado_cobro == Cobro.Estado.PAGADO else "",
                comprobante_tipo=comprobante,
                comprobante_numero=(d.get("cobro_comprobante_numero") or "").strip()[:40],
                registrado_por=request.user,
            )

        cita.estado = Cita.Estado.ATENDIDA
        cita.save(update_fields=["estado"])
        gcalendar.sync_cita(cita)
        return Response(CitaSerializer(cita).data)

    @action(detail=True, methods=["post"])
    def recordar(self, request, pk=None):
        """Envía el recordatorio de la cita por WhatsApp y lo deja en la bitácora.

        Acepta `texto` opcional (lo que se ve en el preview, editable); si viene
        vacío, usa el mensaje por defecto. Marca la cita como recordada cuando se
        envió o cuando queda el enlace manual de respaldo (wa.me).
        """
        cita = self.get_object()
        texto = (request.data.get("texto") or "").strip() or texto_recordatorio(cita)
        mensaje, resultado, wa_url = registrar_y_enviar(
            cita.clinica, telefono=cita.paciente.telefono, texto=texto,
            tipo=Mensaje.Tipo.RECORDATORIO, paciente=cita.paciente, cita=cita,
            usuario=request.user,
        )
        if resultado["estado"] == "enviado" or wa_url:
            cita.recordatorio_enviado = True
            cita.save(update_fields=["recordatorio_enviado"])
        return Response({
            "cita": CitaSerializer(cita).data,
            "estado": resultado["estado"],
            "detalle": resultado["detalle"],
            "wa_url": wa_url,
            "texto": texto,
        })

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        """Reagenda la cita a una nueva fecha/hora. Vuelve a 'Por confirmar' y
        limpia el recordatorio para poder avisar de nuevo al paciente."""
        cita = self.get_object()
        try:
            cita.inicio = _inicio_desde(request.data.get("fecha"), request.data.get("hora"))
        except (ValueError, TypeError):
            return Response({"detail": "Fecha u hora inválida (usa fecha y HH:MM)."}, status=status.HTTP_400_BAD_REQUEST)
        cita.estado = Cita.Estado.POR_CONFIRMAR
        cita.recordatorio_enviado = False
        cita.save(update_fields=["inicio", "estado", "recordatorio_enviado"])
        gcalendar.sync_cita(cita)
        return Response(CitaSerializer(cita).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Marca la cita como cancelada (no se borra: queda el registro)."""
        cita = self.get_object()
        cita.estado = Cita.Estado.CANCELADA
        cita.save(update_fields=["estado"])
        gcalendar.eliminar_cita(cita)  # quita el evento del calendario
        return Response(CitaSerializer(cita).data)

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        """Marca la cita como confirmada (p. ej. el paciente respondió que sí)."""
        cita = self.get_object()
        cita.estado = Cita.Estado.CONFIRMADA
        cita.save(update_fields=["estado"])
        gcalendar.sync_cita(cita)
        return Response(CitaSerializer(cita).data)


class TranscribirView(APIView):
    """Transcribe un audio de la sesión con Whisper (local) y, si OpenAI está
    configurado, lo estructura en los campos de la nota. NO guarda nada: devuelve
    el texto para que el terapeuta lo revise y guarde con el flujo normal (Atender).
    Solo médico/admin.
    """

    def post(self, request):
        from usuarios.models import Usuario

        if getattr(request.user, "rol", None) not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            return Response({"detail": "Solo el personal médico puede transcribir notas."},
                            status=status.HTTP_403_FORBIDDEN)
        audio = request.FILES.get("audio")
        if audio is None:
            return Response({"detail": "No se recibió ningún audio."}, status=status.HTTP_400_BAD_REQUEST)
        if audio.size > 25 * 1024 * 1024:
            return Response({"detail": "El audio supera el límite de 25 MB."}, status=status.HTTP_400_BAD_REQUEST)
        if not transcripcion.disponible():
            return Response({"detail": "Whisper no está instalado en el servidor."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            texto = transcripcion.transcribir_archivo(audio)
        except Exception as e:  # noqa: BLE001 — reportamos el fallo de forma controlada
            return Response({"detail": f"No se pudo transcribir el audio: {e}"},
                            status=status.HTTP_400_BAD_REQUEST)
        tipo = request.data.get("tipo") or "evolucion"
        return Response({
            "transcripcion": texto,
            "estructura": estructurar_nota.estructurar(texto, tipo),  # None si no hay OpenAI
        })


class AtencionViewSet(viewsets.ModelViewSet):
    """Historia clínica (atenciones). Ver: cualquier usuario de la clínica.
    EDITAR el contenido: solo médico/admin. NO se crea aquí (se registra al Atender
    una cita) ni se borra: la historia clínica es un registro permanente que se
    corrige, no se elimina (integridad médica · Ley 29733). Las correcciones quedan
    a cargo del personal clínico; conviene sumar un registro de auditoría más adelante.
    """

    serializer_class = AtencionSerializer

    CAMPOS_AUDIT = [
        "especialidad", "motivo", "presion_arterial", "frecuencia_cardiaca",
        "temperatura", "peso", "talla", "diagnostico", "indicaciones", "nota",
        "aspectos_historicos", "objetivos", "puntos_importantes", "proximos_pasos",
    ]

    def get_queryset(self):
        qs = (
            Atencion.objects.del_tenant_actual()
            .select_related("paciente", "medico", "registrado_por")
            .prefetch_related("ediciones__editado_por")
        )
        if _es_comercial(self.request.user):
            return qs.none()
        # El psicólogo solo ve las historias de SUS pacientes.
        if _es_medico(self.request.user):
            ficha = _ficha_de(self.request.user)
            qs = qs.filter(paciente__profesional=ficha) if ficha else qs.none()
        pid = self.request.query_params.get("paciente")
        if pid:
            qs = qs.filter(paciente_id=pid)
        return qs.order_by("-fecha")

    def _solo_clinico(self):
        from usuarios.models import Usuario
        if getattr(self.request.user, "rol", None) not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            raise PermissionDenied("Solo el personal médico (médico/admin) puede editar la historia clínica.")

    def perform_update(self, serializer):
        self._solo_clinico()
        from .models import EdicionAtencion

        instancia = serializer.instance
        antes = {c: getattr(instancia, c) for c in self.CAMPOS_AUDIT}
        atencion = serializer.save()
        # Bitácora: una fila por campo que realmente cambió.
        logs = []
        for c in self.CAMPOS_AUDIT:
            nuevo = getattr(atencion, c)
            if str(antes[c] if antes[c] is not None else "") != str(nuevo if nuevo is not None else ""):
                logs.append(EdicionAtencion(
                    clinica=atencion.clinica, atencion=atencion, campo=c,
                    antes=str(antes[c] if antes[c] is not None else ""),
                    despues=str(nuevo if nuevo is not None else ""),
                    editado_por=self.request.user,
                ))
        if logs:
            EdicionAtencion.objects.bulk_create(logs)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Las atenciones se registran al Atender una cita, no se crean sueltas."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "La historia clínica no se borra (integridad médica · Ley 29733)."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class AdjuntoViewSet(viewsets.ModelViewSet):
    """Archivos clínicos (laboratorios, ecografías, PDFs, imágenes).

    Subir y listar es para cualquier usuario de la clínica; eliminar queda para
    médico/admin. La descarga pasa por la acción `descargar`, siempre autenticada
    y con scope de clínica: nunca se expone una URL pública (Ley 29733).
    """

    serializer_class = AdjuntoSerializer

    def get_queryset(self):
        return (
            Adjunto.objects.del_tenant_actual()
            .select_related("paciente", "subido_por")
            .order_by("-creado_en")
        )

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        archivo = request.FILES.get("archivo")
        if archivo is None:
            return Response({"detail": "No se recibió ningún archivo."}, status=status.HTTP_400_BAD_REQUEST)
        if archivo.size > MAX_ADJUNTO_MB * 1024 * 1024:
            return Response(
                {"detail": f"El archivo supera el límite de {MAX_ADJUNTO_MB} MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ext = archivo.name.rsplit(".", 1)[-1].lower() if "." in archivo.name else ""
        if ext not in EXT_PERMITIDAS:
            return Response(
                {"detail": "Tipo de archivo no permitido. Sube PDF, imagen, documento o estudio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paciente = Paciente.objects.del_tenant_actual().filter(pk=request.data.get("paciente")).first()
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        atencion = None
        atencion_id = request.data.get("atencion")
        if atencion_id:
            atencion = Atencion.objects.del_tenant_actual().filter(pk=atencion_id).first()

        nombre = (request.data.get("nombre") or archivo.name).strip()[:255]
        adjunto = Adjunto.objects.create(
            clinica=clinica,
            paciente=paciente,
            atencion=atencion,
            archivo=archivo,
            nombre=nombre,
            tipo=ext,
            subido_por=request.user,
        )
        return Response(AdjuntoSerializer(adjunto).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        from usuarios.models import Usuario

        if request.user.rol not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            return Response(
                {"detail": "Solo el personal médico puede eliminar archivos clínicos."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        instance.archivo.delete(save=False)  # borra también el archivo del disco
        instance.delete()

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        adjunto = self.get_object()  # get_queryset ya filtra por clínica
        return FileResponse(
            adjunto.archivo.open("rb"),
            as_attachment=True,
            filename=adjunto.nombre or adjunto.archivo.name,
        )
