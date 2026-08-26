from datetime import date, datetime, time as dtime, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenant import get_clinica_actual
from pacientes.models import Paciente

from . import whatsapp_auto
from .captacion import _base_url
from .models import Anuncio, Lead
from .reporte import generar_reporte_pauta, personas_unicas
from .serializers import AnuncioSerializer, LeadSerializer

_FUENTE_LABEL = dict(Lead.Fuente.choices)


def _norm_tel(t):
    return "".join(c for c in (t or "") if c.isdigit())[-9:]


def _parse_fecha(valor, por_defecto):
    """'YYYY-MM-DD' -> date; si viene vacío/ inválido, usa por_defecto."""
    try:
        y, m, d = [int(x) for x in str(valor).split("-")]
        return date(y, m, d)
    except (ValueError, TypeError, AttributeError):
        return por_defecto


def _paciente_del_lead(lead):
    """El paciente de este lead: el enlazado, uno que ya exista con su teléfono, o
    uno nuevo. NO toca el estado del lead (agendar una consulta no es cerrarla).

    La ficha que se crea aquí nace `provisional`: existe para que la cita cuelgue
    de alguien, pero la persona todavía no es paciente y no debe contarse como
    tal. Deja de serlo cuando el lead inicia proceso.

    El match por teléfono es el mismo criterio que usa la reserva web: sin él, la
    coordinadora terminaba creando un paciente repetido cada vez que registraba
    la cita a mano, y eso descuadraba los conteos.
    """
    if lead.paciente_id:
        return lead.paciente
    from usuarios.models import Profesional

    tel = _norm_tel(lead.telefono)
    if tel:
        for p in Paciente.objects.del_tenant_actual().exclude(telefono=""):
            if _norm_tel(p.telefono) == tel:
                # Aprovecha lo que el lead trae y a la ficha le falta, sin pisar
                # nada de lo que ya estaba cargado.
                completar = []
                if not p.email and lead.email:
                    p.email = lead.email
                    completar.append("email")
                if not p.direccion and lead.ubicacion:
                    p.direccion = lead.ubicacion
                    completar.append("direccion")
                if completar:
                    p.save(update_fields=completar)
                lead.paciente = p
                lead.save(update_fields=["paciente"])
                return p
    ficha = Profesional.objects.filter(usuario=lead.medico).first() if lead.medico_id else None
    paciente = Paciente.objects.create(
        clinica=lead.clinica, nombre=lead.nombre, telefono=lead.telefono,
        email=lead.email or "", sede=lead.sede or "", profesional=ficha,
        especialidad_habitual=lead.especialidad or lead.get_tipo_servicio_display() or "",
        provisional=True,
    )
    lead.paciente = paciente
    lead.save(update_fields=["paciente"])
    return paciente


def _servicio_de_consulta(lead):
    """Con qué servicio entra un lead a la agenda: una CONSULTA, no una sesión.

    No es un detalle de texto: la liquidación se calcula por el NOMBRE del
    servicio, y la consulta inicial y la sesión individual no se pagan igual. Si
    la cita entra como "Terapia individual", al psicólogo se le liquida de más.

    Se busca el nombre exacto en el catálogo de la clínica (si hay varias
    consultas —adultos, infantojuvenil…— se prefiere la que calce con el tipo de
    servicio del lead). Sin catálogo, cae a lo que traiga el lead.
    """
    from finanzas.models import Servicio

    consultas = [
        s for s in Servicio.objects.filter(clinica=lead.clinica, activo=True)
        if "consulta" in (s.nombre or "").lower()
    ]
    if not consultas:
        return lead.especialidad or lead.get_tipo_servicio_display() or ""
    tipo = (lead.get_tipo_servicio_display() or "").strip().lower()
    if tipo:
        for s in consultas:
            if tipo in s.nombre.lower():
                return s.nombre
    return sorted(consultas, key=lambda s: len(s.nombre))[0].nombre


def _sede_de_la_cita(lead):
    """La sesión pertenece a la sede de QUIEN ATIENDE, no a la del paciente.

    En las consultas virtuales el equipo se cubre entre ciudades: una coordinadora
    de Lima le agenda a una psicóloga de Piura. Esa hora la trabaja Piura, así que
    la agenda y la ocupación tienen que contarla ahí. La captación sigue midiendo
    por el lead —de dónde nos llega la gente—, que es otra pregunta.
    """
    from usuarios.models import Profesional

    if lead.medico_id:
        ficha = Profesional.objects.filter(usuario=lead.medico).first()
        if ficha and ficha.sede:
            return ficha.sede
    return lead.sede or ""


def _categoria_de(lead):
    """A qué categoría de la agenda corresponde el tipo de servicio del lead."""
    from pacientes.models import Cita

    return {
        Lead.TipoServicio.ADULTOS: Cita.Categoria.ADULTOS,
        Lead.TipoServicio.NINOS: Cita.Categoria.INFANTOJUVENIL,
        Lead.TipoServicio.ADOLESCENTES: Cita.Categoria.INFANTOJUVENIL,
        Lead.TipoServicio.PAREJA: Cita.Categoria.PAREJAS,
    }.get(lead.tipo_servicio, "")


def sincronizar_cita_del_lead(lead):
    """Crea (o mueve) la cita de la consulta agendada de un lead.

    Antes esto se hacía a mano: la coordinadora registraba la consulta en
    Marketing y volvía a registrarla en la Agenda. La reserva web ya creaba
    lead + paciente + cita de una sola vez; esto es lo mismo para el registro
    manual. Devuelve (cita, aviso) — el aviso sale si el horario choca.
    """
    from pacientes.api import _choque_de_horario
    from pacientes.models import Cita

    if not (lead.agendo_consulta and lead.fecha_consulta and lead.hora_consulta and lead.medico_id):
        return None, None  # sin los cuatro datos no hay cita que crear

    inicio = timezone.make_aware(datetime.combine(lead.fecha_consulta, lead.hora_consulta))
    paciente = _paciente_del_lead(lead)
    especialidad = _servicio_de_consulta(lead)

    cita = lead.cita if lead.cita_id else None
    if cita and cita.estado == Cita.Estado.CANCELADA:
        cita = None  # la cancelaron: se agenda una nueva
    choque = _choque_de_horario(lead.medico, inicio, excluir_id=cita.pk if cita else None)
    aviso = None
    if choque:
        aviso = (f"Ojo: {lead.medico} ya tiene una cita a las "
                 f"{timezone.localtime(choque.inicio):%H:%M} con {choque.paciente.nombre}.")

    if cita:
        cambios = []
        if cita.inicio != inicio or cita.medico_id != lead.medico_id:
            cita.inicio = inicio
            cita.medico = lead.medico
            cita.estado = Cita.Estado.REPROGRAMADA
            cambios += ["inicio", "medico", "estado"]
        # Si en Marketing cambian la modalidad o el enlace, la cita los toma: si no,
        # habría que ir a corregirlos a la agenda, que es la doble tarea de siempre.
        if lead.modalidad_consulta:
            from pacientes.api import _normaliza_enlace

            nueva_mod = (Cita.Modalidad.VIRTUAL if lead.modalidad_consulta == "virtual"
                         else Cita.Modalidad.PRESENCIAL)
            nuevo_enlace = _normaliza_enlace(lead.enlace_consulta) if nueva_mod == Cita.Modalidad.VIRTUAL else ""
            if cita.modalidad != nueva_mod or (nuevo_enlace and cita.enlace != nuevo_enlace):
                cita.modalidad = nueva_mod
                cita.enlace = nuevo_enlace
                cambios += ["modalidad", "enlace"]
        if cambios:
            cita.save(update_fields=cambios)
        return cita, aviso

    from pacientes.api import _normaliza_enlace

    virtual = lead.modalidad_consulta == "virtual"
    cita = Cita.objects.create(
        clinica=lead.clinica, paciente=paciente, medico=lead.medico, inicio=inicio,
        especialidad=especialidad, categoria=_categoria_de(lead),
        estado=Cita.Estado.AGENDADA, sede=_sede_de_la_cita(lead),
        modalidad=Cita.Modalidad.VIRTUAL if virtual else Cita.Modalidad.PRESENCIAL,
        enlace=_normaliza_enlace(lead.enlace_consulta) if virtual else "",
        motivo_consulta=lead.motivo_consulta or "",
        notas=f"Consulta registrada desde Marketing (lead #{lead.id}).",
    )
    lead.cita = cita
    lead.save(update_fields=["cita"])
    return cita, aviso


def convertir_lead_en_paciente(lead):
    """Crea el Paciente desde el Lead (si aún no existe) y los enlaza. Copia sede,
    teléfono y enlaza al psicólogo (su ficha del directorio). Idempotente.

    Este es el ÚNICO punto donde alguien pasa a ser paciente. Si ya tenía ficha
    provisional —la que dejó la consulta agendada—, aquí deja de serlo: recién
    ahora inició proceso."""
    if lead.paciente_id:
        paciente = lead.paciente
        if paciente.provisional:
            paciente.provisional = False
            paciente.save(update_fields=["provisional"])
        if lead.estado != Lead.Estado.GANADO:
            lead.estado = Lead.Estado.GANADO
            lead.save(update_fields=["estado"])
        return paciente
    from usuarios.models import Profesional

    ficha = Profesional.objects.filter(usuario=lead.medico).first() if lead.medico_id else None
    paciente = Paciente.objects.create(
        clinica=lead.clinica,
        nombre=lead.nombre,
        telefono=lead.telefono,
        sede=lead.sede or "",
        profesional=ficha,
        especialidad_habitual=lead.especialidad or lead.get_tipo_servicio_display() or "",
    )
    lead.paciente = paciente
    if lead.estado != Lead.Estado.GANADO:
        lead.estado = Lead.Estado.GANADO
    lead.save(update_fields=["paciente", "estado"])
    return paciente


class AnuncioViewSet(viewsets.ModelViewSet):
    """Catálogo de anuncios/publicaciones de pauta (lo gestiona el equipo de marketing)."""

    serializer_class = AnuncioSerializer

    def get_queryset(self):
        return Anuncio.objects.del_tenant_actual().order_by("-creado_en")

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())


class LeadViewSet(viewsets.ModelViewSet):
    """CRUD de leads + acciones de embudo y reportes, con scope de clínica."""

    serializer_class = LeadSerializer

    def get_queryset(self):
        qs = (
            Lead.objects.del_tenant_actual()
            .select_related("medico", "paciente")
            .order_by("-creado_en")
        )
        sede = (self.request.query_params.get("sede") or "").strip()
        if sede in dict(Lead.Sede.choices):
            qs = qs.filter(sede=sede)
        # Buscador (por nombre o número), p. ej. para ver si un número ya está registrado.
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            digitos = "".join(c for c in q if c.isdigit())
            filtro = Q(nombre__icontains=q) | Q(email__icontains=q)
            if digitos:
                filtro |= Q(telefono__icontains=digitos)
            qs = qs.filter(filtro)
        return qs

    def create(self, request, *args, **kwargs):
        # No permitir registrar dos veces el mismo número (salvo que se fuerce).
        tel = _norm_tel(request.data.get("telefono"))
        if len(tel) >= 9 and not request.data.get("forzar"):
            dup = next(
                (l for l in Lead.objects.del_tenant_actual().exclude(telefono="").only("id", "nombre", "telefono")
                 if _norm_tel(l.telefono) == tel),
                None,
            )
            if dup is not None:
                return Response(
                    {"detail": f"Ese número ya está registrado como lead: {dup.nombre}. Búscalo en la lista.",
                     "duplicado": {"id": dup.id, "nombre": dup.nombre}},
                    status=status.HTTP_409_CONFLICT,
                )
        return self._con_aviso(super().create(request, *args, **kwargs))

    def update(self, request, *args, **kwargs):
        return self._con_aviso(super().update(request, *args, **kwargs))

    def _con_aviso(self, respuesta):
        """Adjunta el aviso de la cita (choque de horario) a la respuesta."""
        aviso = getattr(self, "_aviso_cita", None)
        if aviso and isinstance(respuesta.data, dict):
            respuesta.data["aviso"] = aviso
        return respuesta

    def _aplicar_fecha_llegada(self, lead):
        """Permite registrar la fecha REAL de llegada (leads antiguos o fuera de
        horario) sobre `creado_en`, que es lo que usan los reportes."""
        f = (self.request.data.get("fecha_llegada") or "").strip()
        if not f:
            return
        try:
            d = datetime.strptime(f, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return
        dt = timezone.make_aware(datetime.combine(d, dtime(12, 0)), timezone.get_current_timezone())
        lead.creado_en = dt
        lead.save(update_fields=["creado_en"])

    def perform_create(self, serializer):
        lead = serializer.save(clinica=get_clinica_actual())
        self._aplicar_fecha_llegada(lead)
        # Si trae consulta agendada, la cita queda creada en la agenda: antes había
        # que registrarla otra vez a mano y de ahí salían los pacientes duplicados.
        _cita, self._aviso_cita = sincronizar_cita_del_lead(lead)
        # La fila puede entrar ya como "Inició proceso": el avance de etapa se
        # registra como fila NUEVA, no editando la anterior. En ese caso la ficha
        # que dejó la cita no debe quedarse provisional.
        if lead.estado == Lead.Estado.GANADO:
            convertir_lead_en_paciente(lead)

    def perform_update(self, serializer):
        lead = serializer.save()
        self._aplicar_fecha_llegada(lead)
        # Al marcar "Inició proceso" (ganado) recién ahora es paciente: se le crea
        # la ficha, o la provisional que dejó la consulta agendada deja de serlo.
        # Se llama SIEMPRE que el estado sea ganado (la función es idempotente):
        # si solo se llamara cuando no hay ficha, el lead que ya tenía una
        # provisional se quedaba con ella para siempre y nunca entraba al listado.
        if lead.estado == Lead.Estado.GANADO:
            convertir_lead_en_paciente(lead)
        _cita, self._aviso_cita = sincronizar_cita_del_lead(lead)

    def destroy(self, request, *args, **kwargs):
        # Solo la gerencia elimina leads (p. ej. un duplicado que llegó por IG y
        # por WhatsApp). El resto del equipo no puede borrarlos.
        from usuarios.models import Usuario
        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            return Response({"detail": "Solo la gerencia puede eliminar leads."},
                            status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def convertir(self, request, pk=None):
        """Convierte el lead en paciente (crea el paciente y marca el cierre).

        Tener ficha provisional (por la consulta agendada) no bloquea el botón:
        justamente esto es lo que la asciende a paciente de verdad."""
        lead = self.get_object()
        if lead.paciente_id and lead.estado == Lead.Estado.GANADO and not lead.paciente.provisional:
            return Response({"detail": "Este lead ya es paciente.", "paciente_id": lead.paciente_id})
        paciente = convertir_lead_en_paciente(lead)
        return Response({"paciente_id": paciente.id, "lead": LeadSerializer(lead).data},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def seguimiento(self, request, pk=None):
        """Registra un seguimiento: actualiza el último contacto y agrega la nota a
        observaciones. No cambia el estado (el lead sigue en seguimiento)."""
        lead = self.get_object()
        nota = (request.data.get("nota") or "").strip()
        lead.ultimo_contacto = timezone.now()
        if nota:
            sello = timezone.localtime(lead.ultimo_contacto).strftime("%d/%m %H:%M")
            extra = f"[{sello}] {nota}"
            lead.observaciones = (lead.observaciones + "\n" + extra).strip() if lead.observaciones else extra
        lead.save(update_fields=["ultimo_contacto", "observaciones"])
        return Response(LeadSerializer(lead).data)

    @action(detail=False, methods=["post"], url_path="probar-whatsapp")
    def probar_whatsapp(self, request):
        """Simula un mensaje de WhatsApp: muestra qué datos detecta el sistema y
        qué le respondería, SIN crear el lead ni enviar nada.

        Sirve para revisar los textos automáticos (plantillas `faq_*`) antes de
        que llegue gente real, y sin gastar mensajes."""
        texto = str(request.data.get("texto") or "").strip()
        if not texto:
            return Response({"detail": "Escribe un mensaje de ejemplo."},
                            status=status.HTTP_400_BAD_REQUEST)
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."},
                            status=status.HTTP_400_BAD_REQUEST)
        analisis = whatsapp_auto.analizar(texto)
        respuesta = whatsapp_auto.armar_respuesta(
            clinica, analisis,
            nombre=str(request.data.get("nombre") or "").strip(),
            base_url=_base_url(request),
        )
        return Response({
            "analisis": analisis,
            "sede_label": dict(Lead.Sede.choices).get(analisis["sede"], ""),
            "tipo_servicio_label": dict(Lead.TipoServicio.choices).get(analisis["tipo_servicio"], ""),
            "respuesta": respuesta,
        })

    @action(detail=False, methods=["get"], url_path="reporte-pauta")
    def reporte_pauta(self, request):
        """Genera el reporte de captación/pauta en texto (listo para WhatsApp).

        Params: sede (piura/lima, opcional), desde y hasta (YYYY-MM-DD). Por
        defecto, del día 1 del mes actual a hoy."""
        hoy = date.today()
        desde = _parse_fecha(request.query_params.get("desde"), hoy.replace(day=1))
        hasta = _parse_fecha(request.query_params.get("hasta"), hoy)
        sede = (request.query_params.get("sede") or "").strip()
        if sede and sede not in dict(Lead.Sede.choices):
            return Response({"detail": "Sede inválida."}, status=status.HTTP_400_BAD_REQUEST)
        resultado = generar_reporte_pauta(get_clinica_actual(), sede, desde, hasta)
        resultado["sede"] = sede
        resultado["desde"] = desde.isoformat()
        resultado["hasta"] = hasta.isoformat()
        return Response(resultado)

    @action(detail=False, methods=["get"], url_path="reporte-cierre")
    def reporte_cierre(self, request):
        """Métricas de marketing: % cierre leads→consulta, consulta→proceso, y
        sesiones promedio (LTV). Por sede, por psicólogo y general.

        Definiciones (acordadas): 'tuvo consulta' = estado evaluando/pendiente_pago/
        ganado; 'inició proceso' = ganado; LTV = promedio de N° de sesión de los
        pacientes con sesiones. Filtro opcional desde/hasta por fecha de alta del lead."""
        leads = Lead.objects.del_tenant_actual().select_related("medico")
        desde = request.query_params.get("desde")
        hasta = request.query_params.get("hasta")
        if desde:
            leads = leads.filter(creado_en__date__gte=_parse_fecha(desde, date.min))
        if hasta:
            leads = leads.filter(creado_en__date__lte=_parse_fecha(hasta, date.max))
        # Personas únicas (una fila nueva por etapa no debe contar doble).
        leads = personas_unicas(list(leads))

        E = Lead.Estado
        CONSULTA = {E.EVALUANDO, E.PENDIENTE_PAGO, E.GANADO}
        sede_label = dict(Lead.Sede.choices)

        def pct(n, d):
            return round(n / d * 100, 1) if d else 0.0

        def bloque_leads(items):
            den = len(items)
            num = sum(1 for l in items if l.estado in CONSULTA)
            return {"num": num, "den": den, "pct": pct(num, den)}

        def bloque_proc(items):
            con_consulta = [l for l in items if l.estado in CONSULTA]
            den = len(con_consulta)
            num = sum(1 for l in con_consulta if l.estado == E.GANADO)
            return {"num": num, "den": den, "pct": pct(num, den)}

        sedes = sorted({l.sede for l in leads})
        por_medico = {}
        for l in leads:
            por_medico.setdefault(str(l.medico) if l.medico_id else "Sin psicólogo", []).append(l)

        leads_consulta = {
            "general": bloque_leads(leads),
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), **bloque_leads([l for l in leads if l.sede == s])} for s in sedes],
        }
        consulta_proceso = {
            "general": bloque_proc(leads),
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), **bloque_proc([l for l in leads if l.sede == s])} for s in sedes],
            "por_psicologo": [{"psicologo": k, **bloque_proc(v)} for k, v in sorted(por_medico.items())],
        }

        # LTV — promedio de N° de sesión de los pacientes con sesiones.
        pacientes = list(Paciente.objects.del_tenant_actual().filter(n_sesion__gt=0).select_related("profesional"))

        def avg_ses(items):
            return round(sum(p.n_sesion for p in items) / len(items), 1) if items else 0.0

        psede = sorted({p.sede for p in pacientes})
        pprof = {}
        for p in pacientes:
            pprof.setdefault(p.profesional.nombre if p.profesional_id else "Sin psicólogo", []).append(p)
        ltv = {
            "general": {"promedio": avg_ses(pacientes), "n": len(pacientes)},
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), "promedio": avg_ses([p for p in pacientes if p.sede == s]), "n": len([p for p in pacientes if p.sede == s])} for s in psede],
            "por_psicologo": [{"psicologo": k, "promedio": avg_ses(v), "n": len(v)} for k, v in sorted(pprof.items())],
        }

        return Response({"leads_consulta": leads_consulta, "consulta_proceso": consulta_proceso, "ltv": ltv})

    @action(detail=False, methods=["get"])
    def reportes(self, request):
        """Embudo global + cierre por doctor + por fuente. Cuenta PERSONAS únicas:
        si la consulta/proceso se registró como fila aparte, no suma de nuevo."""
        leads = personas_unicas(list(self.get_queryset()))
        E = Lead.Estado

        AGENDADOS = (E.AGENDADO, E.AGENDO_NO_PAGO, E.AGENDO_ESPERA_PAGO, E.GANADO)
        embudo = {
            "recibidos": len(leads),
            "contactados": sum(1 for l in leads if l.estado == E.CONTACTADO or l.estado in AGENDADOS),
            "agendados": sum(1 for l in leads if l.estado in AGENDADOS),
            "iniciaron": sum(1 for l in leads if l.estado == E.GANADO),
            "perdidos": sum(1 for l in leads if l.estado == E.PERDIDO),
        }

        por_medico = {}
        por_fuente = {}
        for l in leads:
            mk = l.medico_id or 0
            m = por_medico.setdefault(mk, {
                "medico": str(l.medico) if l.medico_id else "Sin asignar",
                "leads": 0, "agendados": 0, "cierres": 0,
            })
            m["leads"] += 1
            if l.estado in AGENDADOS:
                m["agendados"] += 1
            if l.estado == E.GANADO:
                m["cierres"] += 1

            f = por_fuente.setdefault(l.fuente, {
                "fuente": _FUENTE_LABEL.get(l.fuente, l.fuente), "leads": 0, "cierres": 0,
            })
            f["leads"] += 1
            if l.estado == E.GANADO:
                f["cierres"] += 1

        def con_tasa(d):
            d["tasa"] = round(d["cierres"] / d["leads"] * 100) if d["leads"] else 0
            return d

        por_medico = sorted((con_tasa(d) for d in por_medico.values()), key=lambda x: -x["leads"])
        por_fuente = sorted((con_tasa(d) for d in por_fuente.values()), key=lambda x: -x["leads"])
        tasa_global = round(embudo["iniciaron"] / embudo["recibidos"] * 100) if embudo["recibidos"] else 0

        return Response({
            "embudo": embudo,
            "por_medico": por_medico,
            "por_fuente": por_fuente,
            "tasa_global": tasa_global,
        })
