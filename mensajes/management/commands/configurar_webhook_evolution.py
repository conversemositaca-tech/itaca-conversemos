"""Configura el webhook de una instancia de Evolution para que apunte a este sistema.

NO se ejecuta solo: por defecto solo MUESTRA lo que haría (dry-run). Para
escribir de verdad en Evolution hay que pasar `--confirmar`. Es una operación
que toca un servidor en producción y que afecta a la línea de una coordinadora,
así que se hace a mano y a propósito.

    # 1. Ver qué se va a hacer (no escribe nada):
    python manage.py configurar_webhook_evolution --instancia conversemoslima --base-url https://tu-dominio
    # 2. Aplicarlo:
    python manage.py configurar_webhook_evolution --instancia conversemoslima --base-url https://tu-dominio --confirmar
    # 3. Comprobar cómo quedó:
    python manage.py configurar_webhook_evolution --instancia conversemoslima --ver

Eventos que se activan (los mínimos que el sistema necesita):
    MESSAGES_UPSERT · MESSAGES_UPDATE · CONNECTION_UPDATE

A propósito NO se activa MESSAGES_SET (sincronización del historial): traería de
golpe conversaciones viejas enteras a la bitácora. Tampoco se enciende ninguna
respuesta automática: este webhook solo escucha.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Clinica, InstanciaEvolution
from mensajes.monitor_evolution import EVENTOS_REQUERIDOS


def _oculto(texto, visibles=4):
    """Muestra solo el final de un secreto, para poder compararlo sin filtrarlo."""
    texto = texto or ""
    if len(texto) <= visibles:
        return "…"
    return "…" + texto[-visibles:]


class Command(BaseCommand):
    help = "Configura (o muestra) el webhook de una instancia de Evolution."

    def add_arguments(self, parser):
        parser.add_argument("--clinica", default="", help="Slug de la clínica (si hay varias).")
        parser.add_argument("--instancia", required=True, help="Nombre EXACTO en Evolution.")
        parser.add_argument("--base-url", default="",
                            help="Origen público de este sistema (ej. https://mi-app.up.railway.app).")
        parser.add_argument("--confirmar", action="store_true",
                            help="Escribe de verdad en Evolution. Sin esto, solo muestra.")
        parser.add_argument("--ver", action="store_true",
                            help="Solo consulta cómo está el webhook hoy.")

    def _clinica(self, slug):
        if slug:
            c = Clinica.objects.filter(slug=slug).first()
            if c is None:
                raise CommandError(f"No existe una clínica con slug '{slug}'.")
            return c
        clinicas = list(Clinica.objects.filter(activo=True)[:2])
        if not clinicas:
            raise CommandError("No hay ninguna clínica activa.")
        if len(clinicas) > 1:
            raise CommandError("Hay más de una clínica: indica cuál con --clinica <slug>.")
        return clinicas[0]

    def handle(self, *args, **options):
        url = settings.EVOLUTION_API_URL.strip()
        key = settings.EVOLUTION_API_KEY.strip()
        if not (url and key):
            raise CommandError("Faltan EVOLUTION_API_URL / EVOLUTION_API_KEY en el entorno.")

        clinica = self._clinica(options["clinica"])
        nombre = options["instancia"].strip()
        instancia = InstanciaEvolution.objects.filter(
            clinica=clinica, nombre_instancia=nombre).first()
        if instancia is None:
            raise CommandError(
                f"La instancia '{nombre}' no está registrada en el sistema. "
                f"Regístrala primero: python manage.py registrar_instancia_evolution "
                f"--sede <lima|piura> --instancia {nombre}"
            )

        if options["ver"]:
            self._ver(url, key, nombre)
            return

        base = (options["base_url"] or "").strip().rstrip("/")
        if not base:
            raise CommandError("Falta --base-url (el origen público de este sistema).")
        if not base.startswith("https://"):
            # Evolution llama desde fuera: sin https el token del webhook viajaría
            # en claro por internet.
            raise CommandError("--base-url debe empezar con https:// (el token viaja en la URL).")

        token = clinica.asegurar_token_webhook_evolution()
        destino = f"{base}/api/webhook/evolution/{token}/"

        self.stdout.write(f"Clínica:   {clinica.nombre}")
        self.stdout.write(f"Instancia: {nombre}  (sede: {instancia.sede or '—'})")
        # La URL lleva el token secreto: se muestra enmascarada.
        self.stdout.write(f"Webhook:   {base}/api/webhook/evolution/{_oculto(token)}/")
        self.stdout.write(f"Eventos:   {', '.join(EVENTOS_REQUERIDOS)}")

        if not options["confirmar"]:
            self.stdout.write(self.style.WARNING(
                "\nEnsayo: no se escribió nada en Evolution.\n"
                "Para aplicarlo de verdad, repite el comando con --confirmar."))
            return

        cuerpo = {
            "webhook": {
                "enabled": True,
                "url": destino,
                "events": EVENTOS_REQUERIDOS,
                "byEvents": False,
                "base64": False,
            }
        }
        try:
            r = requests.post(
                url.rstrip("/") + "/webhook/set/" + nombre,
                headers={"apikey": key, "Content-Type": "application/json"},
                json=cuerpo, timeout=20,
            )
        except requests.RequestException as e:
            raise CommandError(f"No se pudo conectar con Evolution: {e}")

        if r.status_code in (200, 201):
            self.stdout.write(self.style.SUCCESS("\nWebhook configurado."))
            self.stdout.write(
                "El sistema ya registrará los mensajes de esta línea. NO responde solo: "
                "las respuestas las escribe la coordinadora desde su WhatsApp.")
        else:
            # El cuerpo de la respuesta puede repetir la URL con el token dentro.
            raise CommandError(f"Evolution respondió {r.status_code} al configurar el webhook.")

    def _ver(self, url, key, nombre):
        try:
            r = requests.get(url.rstrip("/") + "/webhook/find/" + nombre,
                             headers={"apikey": key}, timeout=20)
        except requests.RequestException as e:
            raise CommandError(f"No se pudo conectar con Evolution: {e}")
        if r.status_code not in (200, 201):
            self.stdout.write(self.style.WARNING(
                f"Evolution respondió {r.status_code}: la instancia no tiene webhook configurado."))
            return
        try:
            data = r.json()
        except ValueError:
            raise CommandError("Respuesta ilegible de Evolution.")
        eventos = [str(e).upper() for e in (data.get("events") or [])]
        faltan = [e for e in EVENTOS_REQUERIDOS if e not in eventos]
        self.stdout.write(f"Encendido: {bool(data.get('enabled'))}")
        # La URL configurada NO se imprime: contiene el token del webhook.
        self.stdout.write(f"Destino:   {'configurado' if data.get('url') else 'vacío'}")
        self.stdout.write(f"Eventos:   {', '.join(eventos) or '—'}")
        if faltan:
            self.stdout.write(self.style.WARNING(f"Faltan eventos: {', '.join(faltan)}"))
        else:
            self.stdout.write(self.style.SUCCESS("Los eventos necesarios están activos."))
