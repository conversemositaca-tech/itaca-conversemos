"""Lógica de envío de mensajes: registra en la bitácora y envía por WhatsApp.

Cascada de envío (por la SEDE del paciente, nunca por la de otra sede):

1. WhatsApp Cloud API (Meta), si hay un número configurado en "Conexión
   WhatsApp" para esa sede.
2. Evolution API, si Meta no está configurado **o si Meta rechazó el envío**.
3. Enlace wa.me de respaldo (lo arma quien recibe el resultado) cuando ninguno
   envió de forma automática.

El paso 2 era antes un `else`: bastaba con que EXISTIERA un número de Meta —
aunque su token fuera inválido — para que Evolution no se intentara nunca. Con
tres números de Meta rotos en producción, eso dejó 455 mensajes seguidos sin
enviar, recordatorios de cita incluidos.

**Un corte de red con Meta NO se reintenta.** Si la conexión se cortó no
sabemos si Meta llegó a entregar, y reintentar por Evolution le mandaría al
paciente el mismo mensaje dos veces. Solo se reintenta cuando Meta respondió y
rechazó explícitamente (400, 401, 5xx…), que es cuando consta que no entregó.

Pase lo que pase, una comunicación deja UNA sola fila en la bitácora, con el
proveedor que de verdad envió.
"""
from rest_framework.exceptions import PermissionDenied

from core.permisos import es_solo_lectura

from . import cloud_api
from .evolution import enviar_texto as enviar_evolution, wa_link
from .models import Mensaje, PlantillaMensaje, params_plantilla


def _sede_de(paciente, cita):
    if paciente is not None and getattr(paciente, "sede", ""):
        return paciente.sede
    if cita is not None and getattr(cita, "sede", ""):
        return cita.sede
    return ""


def _meta_rechazo(resultado):
    """¿Meta respondió y rechazó el envío? (única condición para reintentar)

    `error_codigo` solo viene lleno cuando hubo respuesta HTTP de error. Un
    corte de red lo deja vacío justamente para NO reintentar: no se puede saber
    si el mensaje llegó a salir.
    """
    return resultado.get("estado") == "fallido" and bool(resultado.get("error_codigo"))


def _hay_linea(clinica, sede, automatico):
    """¿Existe una línea de Evolution que pueda atender a esa sede?

    Se consulta ANTES de reintentar para no gastar una llamada de red cuando no
    hay a dónde. Respeta el aislamiento: `instancia_para` nunca devuelve la
    línea de otra sede ni una de pruebas.
    """
    from .evolution import esta_configurado as evolution_configurado

    return evolution_configurado(clinica, sede, automatico=automatico)


def plantilla_por_clave(clinica, clave):
    """Plantilla activa de una clínica por su clave (recordatorio, cumpleanos, …)."""
    return PlantillaMensaje.objects.filter(clinica=clinica, clave=clave, activo=True).first()


def registrar_y_enviar(clinica, *, telefono, texto, tipo, paciente=None, cita=None,
                       usuario=None, plantilla=None, sede="",
                       plantilla_clave="", texto_original="", gestion_continuidad=None):
    """Intenta enviar por WhatsApp y deja registro en la bitácora.

    Si `plantilla` tiene una plantilla aprobada de Meta (wa_template_nombre) y la
    Cloud API está configurada, envía por esa plantilla (HSM): se entrega aunque
    hayan pasado >24h. Si no, envía texto libre (Cloud o Evolution).

    Devuelve (mensaje, resultado, wa_url). `wa_url` es el enlace de respaldo
    (wa.me) cuando el envío automático no salió (sin configurar o falló).

    `sede` solo hace falta cuando no hay paciente ni cita de dónde sacarla (por
    ejemplo al responderle a un lead): elige el número de esa sede para enviar.

    `plantilla_clave` y `texto_original` son para auditoría: qué plantilla se
    propuso y qué decía antes de que la persona la editara. `texto_original`
    solo se llena si de verdad hubo edición. `gestion_continuidad` ata el
    mensaje al caso que lo motivó.
    """
    # Defensa en profundidad: este es el cuello de botella de TODOS los envíos
    # (recordatorios, NPS, mensajes libres, respuestas a leads). El rol de solo
    # lectura nunca contacta pacientes, aunque mañana alguien agregue un
    # llamador nuevo sin chequeo de rol.
    if usuario is not None and es_solo_lectura(usuario):
        raise PermissionDenied("Tu perfil es de solo lectura: no puede enviar mensajes.")
    sede = sede or _sede_de(paciente, cita)
    # Una respuesta automática (las preguntas frecuentes que se le contestan a
    # un lead) NO puede salir por el número oficial de una coordinadora: quien
    # escribe desde ese número es ella. Sale por la línea de captación.
    automatico = tipo == Mensaje.Tipo.AUTOMATICO

    proveedor, resultado, detalle_previo = Mensaje.Proveedor.EVOLUTION, None, ""

    if cloud_api.esta_configurado(clinica, sede):
        proveedor = Mensaje.Proveedor.META
        if plantilla is not None and plantilla.wa_template_nombre:
            params = params_plantilla(plantilla, paciente=paciente, cita=cita, clinica=clinica)
            resultado = cloud_api.enviar_plantilla(
                clinica, telefono, plantilla.wa_template_nombre,
                plantilla.wa_template_idioma, params, sede=sede)
        else:
            resultado = cloud_api.enviar_texto(clinica, telefono, texto, sede=sede)

        if _meta_rechazo(resultado) and _hay_linea(clinica, sede, automatico):
            # Meta respondió y rechazó: consta que NO entregó. Se intenta la
            # línea de la sede antes de darse por vencido.
            detalle_previo = f"Meta falló ({resultado.get('error_codigo') or 'sin código'}). "
            reintento = enviar_evolution(clinica, telefono, texto, sede=sede,
                                         automatico=automatico)
            if reintento.get("estado") == "enviado":
                proveedor, resultado = Mensaje.Proveedor.EVOLUTION, reintento
            else:
                # Tampoco salió por Evolution: se informa el desenlace real.
                proveedor, resultado = Mensaje.Proveedor.EVOLUTION, reintento

    if resultado is None:
        resultado = enviar_evolution(clinica, telefono, texto, sede=sede,
                                     automatico=automatico)

    mensaje = Mensaje.objects.create(
        clinica=clinica,
        paciente=paciente,
        cita=cita,
        telefono=telefono or "",
        texto=texto,
        tipo=tipo,
        estado=resultado["estado"],
        detalle=(detalle_previo + resultado.get("detalle", ""))[:300],
        enviado_por=usuario,
        proveedor=proveedor,
        direccion=Mensaje.Direccion.SALIENTE,
        sede=sede or "",
        instancia=(resultado.get("instancia") or "")[:120],
        external_message_id=(resultado.get("external_message_id") or "")[:180],
        error_codigo=(resultado.get("error_codigo") or "")[:40],
        plantilla_clave=(plantilla_clave or "")[:40],
        texto_original=texto_original or "",
        gestion_continuidad=gestion_continuidad,
    )
    wa_url = wa_link(telefono, texto) if resultado["estado"] != "enviado" else None
    return mensaje, resultado, wa_url
