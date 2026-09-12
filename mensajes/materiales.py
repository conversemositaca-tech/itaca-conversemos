"""API de la biblioteca de material compartible (el modelo está en models.py).

Son las piezas que Coordinación manda por WhatsApp: ubicación de la sede,
horarios, tarifas, medios de pago, cómo entrar a la sesión online. **No es
material clínico.** Los estudios, informes y documentos de un paciente viven en
`pacientes.Adjunto`, con su propio control de acceso (Ley 29733), y no se
mezclan con esto ni aparecen en el compositor de WhatsApp.

El archivo se guarda con `FileField` en MEDIA_ROOT —el mismo volumen persistente
que ya usan los adjuntos— y se sirve SOLO por un endpoint autenticado con scope
de clínica. No hay URL pública de media en este proyecto y esta biblioteca no la
introduce.

Validación sin dependencias nuevas
----------------------------------
El tipo real y las dimensiones se leen del **contenido binario**, no del
`Content-Type` que manda el navegador (que se falsifica renombrando la
extensión). Solo se aceptan las tres firmas de PNG, JPEG y WEBP: si el archivo
no empieza por una de esas, se rechaza aunque se llame `.png`. Hacerlo a mano
evita sumar Pillow al despliegue y, de paso, deja la lista blanca más cerrada
que la de cualquier librería general.

Ojo con la palabra "cabecera": solo PNG y WEBP guardan sus medidas al principio.
Un JPEG las pone después de la cabecera JFIF, el bloque EXIF y las tablas de
cuantización, así que hay que inspeccionar el archivo entero. Darlo por sentado
costó un bug en producción: toda foto de teléfono se rechazaba con un "puede
estar dañada" que era falso.
"""
import hashlib
import struct

from django.http import FileResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenant import get_clinica_actual

from .models import Material

# Límites de esta primera versión. El de 2 MB es provisional: manda el tamaño
# que aguanta el POST a Evolution, y el base64 infla el payload ~33 % (2 MB de
# imagen ≈ 2,7 MB de cuerpo). Se sube cuando esté medido contra EasyPanel.
MAX_MB = 2
MAX_LADO_PX = 4000
MAX_POR_COMUNICACION = 10

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
FIRMA_JPEG = b"\xff\xd8\xff"
FIRMA_VP8 = b"\x9d\x01\x2a"

# Cuántos segmentos se recorren en un JPEG antes de rendirse. Un archivo real
# llega al SOF en menos de diez (JFIF, EXIF y un par de tablas); el tope está
# para que uno malformado no haga recorrer el archivo entero.
MAX_SEGMENTOS_JPEG = 64


# --- lectura del contenido binario --------------------------------------------

def _dimensiones_png(b):
    # IHDR va siempre en los bytes 16..24, big-endian.
    if len(b) < 24 or b[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", b[16:24])


def _dimensiones_jpeg(b):
    """(ancho, alto) de un JPEG, leídos del marcador SOF.

    El SOF **no** está al principio del archivo: antes van la cabecera JFIF, el
    bloque EXIF y las tablas de cuantización. En un JPEG de teléfono eso lo
    empuja más allá del byte 150 (WhatsApp: 158; ffmpeg: 293), así que hay que
    recibir el archivo entero y recorrer los segmentos saltando por su longitud
    declarada. Leer solo una cabecera corta no sirve para JPEG, aunque sí baste
    para PNG y WEBP.

    El recorrido está acotado por los dos lados para que un archivo malformado
    no lo haga barrer megabytes: solo avanza por longitudes declaradas —nunca
    byte a byte buscando la sincronía— y se rinde a los MAX_SEGMENTOS_JPEG
    segmentos. Un JPEG real llega al SOF en menos de diez.
    """
    i, n = 2, len(b)
    for _ in range(MAX_SEGMENTOS_JPEG):
        # Antes de un marcador puede haber bytes de relleno 0xFF.
        while i + 1 < n and b[i] == 0xFF and b[i + 1] == 0xFF:
            i += 1
        if i + 3 >= n or b[i] != 0xFF:
            return None                      # aquí no empieza un segmento
        marcador = b[i + 1]
        if marcador in (0xD9, 0xDA):
            # Fin de imagen, o empiezan los datos comprimidos: a partir de aquí
            # las longitudes ya no describen segmentos y no habrá SOF.
            return None
        if marcador == 0x01 or 0xD0 <= marcador <= 0xD7:
            i += 2                           # marcadores sin carga
            continue
        largo = struct.unpack(">H", b[i + 2:i + 4])[0]
        if largo < 2:
            return None                      # longitud imposible: malformado
        # SOF0..SOF15, menos los marcadores que no son de trama (C4, C8, CC).
        if 0xC0 <= marcador <= 0xCF and marcador not in (0xC4, 0xC8, 0xCC):
            if i + 9 > n:
                return None                  # el SOF está cortado
            alto, ancho = struct.unpack(">HH", b[i + 5:i + 9])
            return (ancho, alto) if (ancho and alto) else None
        i += 2 + largo
    return None


def _dimensiones_webp(b):
    if len(b) < 30:
        return None
    formato = b[12:16]
    if formato == b"VP8 ":            # lossy
        if b[23:26] != FIRMA_VP8:
            return None
        ancho, alto = struct.unpack("<HH", b[26:30])
        return ancho & 0x3FFF, alto & 0x3FFF
    if formato == b"VP8L":            # lossless
        bits = struct.unpack("<I", b[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if formato == b"VP8X":            # extendido
        return (int.from_bytes(b[24:27], "little") + 1,
                int.from_bytes(b[27:30], "little") + 1)
    return None


def inspeccionar(datos):
    """(mime, ancho, alto) leídos del contenido. (None, 0, 0) si no es imagen.

    Recibe el archivo **completo**, no una cabecera recortada. PNG y WEBP
    guardan sus dimensiones en los primeros 30 bytes, pero un JPEG las pone
    después de la cabecera JFIF, el EXIF y las tablas de cuantización —por el
    byte 158 en los de WhatsApp—, así que con una cabecera corta se reconoce el
    formato y se pierden las medidas. El coste no depende del tamaño: el
    recorrido salta de segmento en segmento, nunca byte a byte.

    Lo que diga el nombre del archivo o el Content-Type no interviene: aquí
    manda la firma binaria.
    """
    b = datos
    if b[:8] == FIRMA_PNG:
        return ("image/png",) + (_dimensiones_png(b) or (0, 0))
    if b[:3] == FIRMA_JPEG:
        return ("image/jpeg",) + (_dimensiones_jpeg(b) or (0, 0))
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return ("image/webp",) + (_dimensiones_webp(b) or (0, 0))
    return (None, 0, 0)


# --- API ----------------------------------------------------------------------

class MaterialSerializer(serializers.ModelSerializer):
    categoria_label = serializers.CharField(source="get_categoria_display", read_only=True)
    sede_label = serializers.CharField(read_only=True)
    subido_por_nombre = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = ["id", "nombre", "categoria", "categoria_label", "sede", "sede_label",
                  "mime", "tamano", "ancho", "alto", "url", "subido_por_nombre",
                  "activo", "creado_en"]

    def get_subido_por_nombre(self, obj):
        return (getattr(obj.subido_por, "nombre", "") or "") if obj.subido_por_id else ""

    def get_url(self, obj):
        # Endpoint autenticado, nunca la ruta de disco ni una URL pública.
        return f"/api/materiales/{obj.id}/imagen/"


class MaterialViewSet(viewsets.ModelViewSet):
    """La biblioteca de material compartible.

    Listar y subir: cualquier usuario de la clínica que ya pueda operar (el rol
    de solo lectura lo bloquea el permiso global del proyecto). Retirar una
    pieza es baja lógica, nunca borrado: los mensajes ya enviados la referencian
    y el historial dejaría de cuadrar. La imagen se sirve por `imagen/`, siempre
    autenticada y con scope de clínica.
    """

    serializer_class = MaterialSerializer

    def get_queryset(self):
        qs = Material.objects.del_tenant_actual().select_related("subido_por")
        if self.action == "list":
            qs = qs.filter(activo=True)
            categoria = (self.request.query_params.get("categoria") or "").strip()
            if categoria:
                qs = qs.filter(categoria=categoria)
            q = (self.request.query_params.get("q") or "").strip()
            if q:
                qs = qs.filter(nombre__icontains=q)
        return qs.order_by("-creado_en")

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        archivo = request.FILES.get("archivo")
        if archivo is None:
            return Response({"detail": "No se recibió ninguna imagen."},
                            status=status.HTTP_400_BAD_REQUEST)
        if archivo.size > MAX_MB * 1024 * 1024:
            return Response({"detail": f"La imagen pesa más de {MAX_MB} MB. "
                                       "Redúcela antes de subirla."},
                            status=status.HTTP_400_BAD_REQUEST)

        datos = archivo.read()
        # El archivo entero, no una cabecera: en un JPEG las dimensiones están
        # pasado el byte 150 y recortar aquí rechazaba TODA foto de teléfono
        # con un "puede estar dañada" que era falso.
        mime, ancho, alto = inspeccionar(datos)
        if mime is None:
            return Response({"detail": "El archivo no es una imagen PNG, JPG o WEBP."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not (ancho and alto):
            return Response({"detail": "No se pudo leer la imagen: puede estar dañada."},
                            status=status.HTTP_400_BAD_REQUEST)
        if ancho > MAX_LADO_PX or alto > MAX_LADO_PX:
            return Response({"detail": f"La imagen mide {ancho}×{alto} px. "
                                       f"El máximo es {MAX_LADO_PX} px por lado."},
                            status=status.HTTP_400_BAD_REQUEST)

        firma = hashlib.sha256(datos).hexdigest()
        nombre = (request.data.get("nombre") or archivo.name or "imagen").strip()[:200]
        categoria = request.data.get("categoria") or Material.Categoria.OTROS
        if categoria not in Material.Categoria.values:
            categoria = Material.Categoria.OTROS
        sede = request.data.get("sede") or ""
        if sede not in ("lima", "piura"):
            sede = ""

        # Ya estaba subida: se devuelve la que existe en vez de duplicar el
        # archivo en disco y en la cuadrícula.
        gemela = (Material.objects.filter(clinica=clinica, hash=firma)
                  .order_by("-activo", "-id").first())
        if gemela is not None:
            if gemela.activo:
                return Response(
                    {**MaterialSerializer(gemela).data, "duplicada": True,
                     "detail": f"Esa imagen ya está en la biblioteca como «{gemela.nombre}»."},
                    status=status.HTTP_200_OK)
            # Estaba retirada: se reactiva con los datos nuevos, en vez de crear
            # otra fila con el mismo contenido.
            gemela.activo, gemela.nombre = True, nombre
            gemela.categoria, gemela.sede = categoria, sede
            gemela.save(update_fields=["activo", "nombre", "categoria", "sede"])
            return Response(MaterialSerializer(gemela).data, status=status.HTTP_201_CREATED)

        archivo.seek(0)
        material = Material(
            clinica=clinica, nombre=nombre, categoria=categoria, sede=sede,
            mime=mime, tamano=len(datos), ancho=ancho, alto=alto, hash=firma,
            subido_por=request.user,
        )
        # El mime tiene que estar puesto ANTES de asignar el archivo:
        # `ruta_material` lo usa para decidir con qué extensión se guarda.
        material.archivo = archivo
        material.save()
        return Response(MaterialSerializer(material).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        material = self.get_object()
        material.activo = False
        material.save(update_fields=["activo"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def imagen(self, request, pk=None):
        material = self.get_object()   # get_queryset ya filtra por clínica
        return FileResponse(material.archivo.open("rb"), content_type=material.mime)
