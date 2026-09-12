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
from .evolution import enviar_media as enviar_media_evolution
from .evolution import enviar_texto as enviar_evolution
from .evolution import wa_link
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
                       plantilla_clave="", texto_original="", gestion_continuidad=None,
                       instancia_prueba=""):
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
    # Un proceso automático NUNCA puede usar la línea de pruebas, venga de donde
    # venga el parámetro: el modo de prueba es para un envío que una persona
    # está mirando.
    if automatico:
        instancia_prueba = ""

    proveedor, resultado, detalle_previo = Mensaje.Proveedor.EVOLUTION, None, ""

    if instancia_prueba:
        # Modo de prueba: va directo a la línea de pruebas, sin pasar por Meta ni
        # por el routing por sede. Lo valida la vista antes de llegar aquí.
        resultado = enviar_evolution(clinica, telefono, texto, sede=sede,
                                     automatico=False, instancia_prueba=instancia_prueba)
        mensaje = Mensaje.objects.create(
            clinica=clinica, paciente=paciente, cita=cita, telefono=telefono or "",
            texto=texto, tipo=tipo, estado=resultado["estado"],
            detalle=("[PRUEBA] " + resultado.get("detalle", ""))[:300], enviado_por=usuario,
            proveedor=Mensaje.Proveedor.EVOLUTION, direccion=Mensaje.Direccion.SALIENTE,
            sede=sede or "", instancia=(resultado.get("instancia") or "")[:120],
            external_message_id=(resultado.get("external_message_id") or "")[:180],
            error_codigo=(resultado.get("error_codigo") or "")[:40],
            plantilla_clave=(plantilla_clave or "")[:40], texto_original=texto_original or "",
            gestion_continuidad=gestion_continuidad,
        )
        return mensaje, resultado, (wa_link(telefono, texto)
                                    if resultado["estado"] != "enviado" else None)

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


# ---------------------------------------------------------------------------
# Comunicación con imágenes: varias partes, una sola comunicación
# ---------------------------------------------------------------------------
# WhatsApp no tiene álbum y Evolution 2.3.7 tampoco: sus trece rutas de envío
# mandan un archivo por petición. Tres imágenes y un texto son CUATRO mensajes
# para el proveedor, aunque para Coordinación sean una sola comunicación. De ahí
# salen las tres reglas de abajo.
#
# 1. **Se detiene en el primer fallo.** Si la imagen 3 no salió porque la línea
#    se cayó, la 4 tampoco va a salir: seguir solo produciría un segundo error y
#    dejaría al paciente con un texto que habla de una imagen que nunca le llegó.
# 2. **Nada se reintenta solo.** Quién reintenta y cuándo lo decide la
#    coordinadora, mirando qué llegó.
# 3. **`external_message_id` es la prueba de que esa parte salió.** Es un dato
#    del proveedor, no una suposición nuestra: una parte que lo tiene NUNCA se
#    reenvía, y eso es lo que impide que "reintentar" le mande al paciente la
#    misma imagen dos veces.
#
# Las imágenes salen SIEMPRE por Evolution, nunca por Meta: la Cloud API tiene
# otro formato de envío de media y, si el texto saliera por un proveedor y las
# imágenes por otro, el paciente recibiría la comunicación desde dos números
# distintos. Por eso el texto de una comunicación CON imágenes también va por
# Evolution. Un mensaje sin imágenes conserva la cascada de siempre.

# Pausa entre partes para que WhatsApp las muestre en el orden en que se
# enviaron. Sin ella, dos peticiones seguidas pueden llegar cruzadas.
PAUSA_ENTRE_PARTES = 1.0


def _dormir(segundos):
    """Aislado para que los tests no esperen de verdad."""
    import time

    time.sleep(segundos)


def _plan_de_partes(materiales, texto):
    """En qué se parte la comunicación: [(orden, material, caption)].

    Una imagen sola viaja CON el texto como pie: es un único mensaje, tal como
    lo mandaría una persona. Con varias, el pie no sirve (iría pegado a una sola
    de ellas), así que las imágenes van limpias y el texto cierra al final.
    """
    materiales = list(materiales)
    texto = (texto or "").strip()
    if len(materiales) == 1 and texto:
        return [(1, materiales[0], texto)]
    partes = [(i, m, "") for i, m in enumerate(materiales, start=1)]
    if texto:
        partes.append((len(partes) + 1, None, texto))
    return partes


def _texto_de_parte(material, caption, texto):
    """Qué se guarda en `Mensaje.texto` de cada parte.

    La bitácora tiene que poder leerse sola: una parte que es una imagen sin pie
    guarda de qué imagen se trata, no una cadena vacía.
    """
    if material is None:
        return texto
    return caption or f"[imagen] {material.nombre}"


def _aplicar_resultado(mensaje, resultado, *, prefijo=""):
    """Vuelca en la fila lo que respondió el proveedor."""
    mensaje.estado = resultado["estado"]
    mensaje.detalle = (prefijo + (resultado.get("detalle") or ""))[:300]
    mensaje.instancia = (resultado.get("instancia") or "")[:120]
    mensaje.external_message_id = (resultado.get("external_message_id") or "")[:180]
    mensaje.error_codigo = (resultado.get("error_codigo") or "")[:40]
    mensaje.save(update_fields=["estado", "detalle", "instancia", "external_message_id",
                                "error_codigo", "actualizado_en"])
    return mensaje


def despachar_partes(partes, *, clinica, telefono, sede="", instancia_prueba="",
                     dormir=None):
    """Envía las partes que faltan, en orden, y se detiene en el primer fallo.

    Una parte con `external_message_id` ya salió: se salta sin tocarla. Es la
    única garantía real contra el doble envío, y por eso el filtro va aquí
    dentro y no en quien llama.
    """
    dormir = dormir or _dormir
    prefijo = "[PRUEBA] " if instancia_prueba else ""
    pendientes = [m for m in partes if not m.external_message_id]
    enviadas, fallo = [], None

    for i, mensaje in enumerate(pendientes):
        if i:
            dormir(PAUSA_ENTRE_PARTES)
        if mensaje.material_id:
            material = mensaje.material
            try:
                contenido = material.leer_bytes()
            except (OSError, ValueError) as e:
                resultado = {"estado": "fallido", "instancia": "",
                             "external_message_id": "",
                             "detalle": f"No se pudo leer la imagen «{material.nombre}»: {e}"}
            else:
                # El pie solo existe cuando la comunicación es de UNA imagen.
                caption = mensaje.texto if not mensaje.texto.startswith("[imagen] ") else ""
                resultado = enviar_media_evolution(
                    clinica, telefono, contenido=contenido, mimetype=material.mime,
                    nombre_archivo=material.nombre, caption=caption, sede=sede,
                    instancia_prueba=instancia_prueba)
        else:
            resultado = enviar_evolution(clinica, telefono, mensaje.texto, sede=sede,
                                         automatico=False,
                                         instancia_prueba=instancia_prueba)
        _aplicar_resultado(mensaje, resultado, prefijo=prefijo)
        if resultado["estado"] == "enviado":
            enviadas.append(mensaje)
        else:
            fallo = mensaje
            break   # regla 1: no se sigue con las siguientes

    return enviadas, fallo


def resumen_comunicacion(partes):
    """Cómo le queda la comunicación a Coordinación: una fila, no cuatro.

    `estado` ∈ enviado | parcial | fallido | pendiente.
    """
    partes = list(partes)
    total = len(partes)
    enviadas = [m for m in partes if m.external_message_id]
    n = len(enviadas)
    if total and n == total:
        estado = "enviado"
    elif n:
        estado = "parcial"
    elif any(m.estado == Mensaje.Estado.PENDIENTE for m in partes):
        estado = "pendiente"
    else:
        estado = "fallido"
    imagenes = sum(1 for m in partes if m.material_id)
    return {
        "estado": estado,
        "total": total,
        "enviadas": n,
        "faltan": total - n,
        "imagenes": imagenes,
        "textos": total - imagenes,
        # Lo que se muestra en el aviso de fallo parcial.
        "detalle": next((m.detalle for m in partes
                         if not m.external_message_id and m.detalle), ""),
    }


def serializar_partes(partes):
    """Las partes tal como las pinta el historial del caso."""
    return [{
        "id": m.id,
        "orden": m.orden,
        "estado": m.estado,
        "estado_label": m.get_estado_display(),
        "enviada": bool(m.external_message_id),
        "material": m.material_id,
        "material_nombre": m.material.nombre if m.material_id else "",
        "texto": "" if m.material_id else m.texto,
        "detalle": m.detalle,
    } for m in partes]


def enviar_comunicacion(clinica, *, telefono, texto, tipo, materiales=(), paciente=None,
                        cita=None, usuario=None, sede="", plantilla_clave="",
                        texto_original="", gestion_continuidad=None, instancia_prueba="",
                        dormir=None):
    """Envía una comunicación de imágenes + texto como UN solo acto.

    Sin imágenes, delega en `registrar_y_enviar` y no cambia nada del camino de
    siempre (cascada Meta → Evolution incluida).

    Con imágenes, crea todas las partes ANTES de empezar a enviar, en estado
    `pendiente`. Así, si algo se corta a mitad —la línea, el servidor, la
    petición—, queda constancia de qué faltaba: sin esas filas, "reintentar lo
    que falta" no tendría de dónde saber qué falta.

    Devuelve (partes, resumen).
    """
    import uuid

    if usuario is not None and es_solo_lectura(usuario):
        raise PermissionDenied("Tu perfil es de solo lectura: no puede enviar mensajes.")
    materiales = list(materiales)
    sede = sede or _sede_de(paciente, cita)

    if not materiales:
        mensaje, _resultado, _wa = registrar_y_enviar(
            clinica, telefono=telefono, texto=texto, tipo=tipo, paciente=paciente,
            cita=cita, usuario=usuario, sede=sede, plantilla_clave=plantilla_clave,
            texto_original=texto_original, gestion_continuidad=gestion_continuidad,
            instancia_prueba=instancia_prueba)
        return [mensaje], resumen_comunicacion([mensaje])

    grupo = uuid.uuid4()
    plan = _plan_de_partes(materiales, texto)
    partes = [
        Mensaje.objects.create(
            clinica=clinica, paciente=paciente, cita=cita, telefono=telefono or "",
            texto=_texto_de_parte(material, caption, texto), tipo=tipo,
            estado=Mensaje.Estado.PENDIENTE,
            detalle="En cola: aún no se envió.", enviado_por=usuario,
            proveedor=Mensaje.Proveedor.EVOLUTION,
            direccion=Mensaje.Direccion.SALIENTE, sede=sede or "",
            plantilla_clave=(plantilla_clave or "")[:40],
            texto_original=(texto_original or "") if material is None else "",
            gestion_continuidad=gestion_continuidad,
            grupo_envio=grupo, orden=orden, material=material,
        )
        for orden, material, caption in plan
    ]

    despachar_partes(partes, clinica=clinica, telefono=telefono, sede=sede,
                     instancia_prueba=instancia_prueba, dormir=dormir)
    return partes, resumen_comunicacion(partes)


def partes_del_grupo(clinica, grupo):
    """Las partes de una comunicación, en su orden de envío."""
    return list(Mensaje.objects.filter(clinica=clinica, grupo_envio=grupo)
                .select_related("material").order_by("orden", "id"))


def reintentar_comunicacion(clinica, grupo, *, usuario=None, instancia_prueba="",
                            dormir=None):
    """Reenvía SOLO las partes que nunca salieron. Devuelve (partes, resumen).

    Las que tienen `external_message_id` se saltan dentro de `despachar_partes`:
    reenviarlas le dejaría al paciente la misma imagen dos veces.
    """
    if usuario is not None and es_solo_lectura(usuario):
        raise PermissionDenied("Tu perfil es de solo lectura: no puede enviar mensajes.")
    partes = partes_del_grupo(clinica, grupo)
    if not partes:
        return [], resumen_comunicacion([])
    primera = partes[0]
    despachar_partes(partes, clinica=clinica, telefono=primera.telefono,
                     sede=primera.sede, instancia_prueba=instancia_prueba,
                     dormir=dormir)
    return partes, resumen_comunicacion(partes)
