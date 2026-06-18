from decimal import Decimal, InvalidOperation

from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenant import get_clinica_actual
from mensajes.models import Mensaje
from mensajes.services import registrar_y_enviar

from .models import Adjunto, Atencion, Cita, Paciente
from .serializers import AdjuntoSerializer, CitaSerializer, PacienteSerializer

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


class PacienteViewSet(viewsets.ModelViewSet):
    """CRUD de pacientes, siempre con scope de la clínica activa."""

    serializer_class = PacienteSerializer

    def get_queryset(self):
        return (
            Paciente.objects.del_tenant_actual()
            .prefetch_related("atenciones__adjuntos", "adjuntos", "cobros", "citas")
            .order_by("nombre")
        )

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())

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
        return (
            Cita.objects.del_tenant_actual()
            .select_related("paciente", "medico")
            .prefetch_related("cobros")
            .order_by("inicio")
        )

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

        medico = Usuario.objects.filter(clinica=clinica, rol=Usuario.Rol.MEDICO).first()

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
        if not any([motivo, diagnostico, indicaciones, nota]):
            return Response(
                {"detail": "Registra al menos el motivo, el diagnóstico, las indicaciones o una nota."},
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
            motivo=motivo,
            presion_arterial=limpio("presion_arterial"),
            frecuencia_cardiaca=_int_o_none(d.get("frecuencia_cardiaca")),
            temperatura=_dec_o_none(d.get("temperatura")),
            peso=_dec_o_none(d.get("peso")),
            talla=_int_o_none(d.get("talla")),
            diagnostico=diagnostico,
            indicaciones=indicaciones,
            nota=nota,
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
            Cobro.objects.create(
                clinica=cita.clinica, paciente=cita.paciente, atencion=atencion, cita=cita, servicio=servicio,
                concepto=concepto, monto=cobro_monto, estado=estado_cobro,
                medio_pago=medio if estado_cobro == Cobro.Estado.PAGADO else "",
                registrado_por=request.user,
            )

        cita.estado = Cita.Estado.ATENDIDA
        cita.save(update_fields=["estado"])
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
        return Response(CitaSerializer(cita).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Marca la cita como cancelada (no se borra: queda el registro)."""
        cita = self.get_object()
        cita.estado = Cita.Estado.CANCELADA
        cita.save(update_fields=["estado"])
        return Response(CitaSerializer(cita).data)

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        """Marca la cita como confirmada (p. ej. el paciente respondió que sí)."""
        cita = self.get_object()
        cita.estado = Cita.Estado.CONFIRMADA
        cita.save(update_fields=["estado"])
        return Response(CitaSerializer(cita).data)


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
