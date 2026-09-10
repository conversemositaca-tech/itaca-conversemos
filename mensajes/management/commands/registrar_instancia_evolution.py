"""Registra (o actualiza) la línea de WhatsApp de una sede.

Solo escribe en NUESTRA base: no toca Evolution, no crea instancias allá, no
empareja ningún número. Sirve para decirle al sistema "los mensajes de Lima
salen por la instancia conversemoslima".

    python manage.py registrar_instancia_evolution --sede lima  --instancia conversemoslima
    python manage.py registrar_instancia_evolution --sede piura --instancia conversemospiura
    python manage.py registrar_instancia_evolution --sede lima  --instancia conversemoslima --desactivar
    python manage.py registrar_instancia_evolution --listar

Con `--clinica <slug>` se elige la clínica cuando hay más de una.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Clinica, InstanciaEvolution


class Command(BaseCommand):
    help = "Registra la instancia de Evolution que atiende a una sede."

    def add_arguments(self, parser):
        parser.add_argument("--clinica", default="", help="Slug de la clínica (si hay varias).")
        parser.add_argument("--sede", default="", choices=["", "lima", "piura", "ambas"])
        parser.add_argument("--instancia", default="", help="Nombre EXACTO en Evolution.")
        parser.add_argument("--desactivar", action="store_true",
                            help="Deja la línea registrada pero apagada (no se envía por ella).")
        parser.add_argument("--listar", action="store_true", help="Solo muestra lo registrado.")

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

    def _listar(self, clinica):
        filas = InstanciaEvolution.objects.filter(clinica=clinica).order_by("sede", "id")
        if not filas:
            self.stdout.write("Sin líneas registradas.")
            return
        self.stdout.write(f"Líneas de {clinica.nombre}:")
        for i in filas:
            estado = "activa" if i.activo else "APAGADA"
            visto = i.ultimo_evento_en.strftime("%d/%m %H:%M") if i.ultimo_evento_en else "nunca"
            self.stdout.write(
                f"  · {i.sede or '(sin sede)':<6} → {i.nombre_instancia:<24} [{estado}] "
                f"último evento: {visto} ({i.ultimo_estado or '—'})"
            )

    @transaction.atomic
    def handle(self, *args, **options):
        clinica = self._clinica(options["clinica"])
        if options["listar"]:
            self._listar(clinica)
            return

        sede = options["sede"]
        nombre = (options["instancia"] or "").strip()
        if not nombre:
            raise CommandError("Falta --instancia (o usa --listar).")
        if not sede:
            raise CommandError("Falta --sede (lima, piura o ambas).")

        activo = not options["desactivar"]
        # Solo puede haber UNA línea activa por sede (lo sostiene un constraint):
        # si ya hay otra, se apaga antes para no chocar contra la base.
        if activo and sede in ("lima", "piura"):
            otras = (InstanciaEvolution.objects
                     .filter(clinica=clinica, sede=sede, activo=True)
                     .exclude(nombre_instancia=nombre))
            for o in otras:
                o.activo = False
                o.save(update_fields=["activo"])
                self.stdout.write(self.style.WARNING(
                    f"Se apagó la línea anterior de {sede}: {o.nombre_instancia}"))

        instancia, creada = InstanciaEvolution.objects.update_or_create(
            clinica=clinica, nombre_instancia=nombre,
            defaults={"sede": sede, "activo": activo},
        )
        verbo = "Registrada" if creada else "Actualizada"
        estado = "activa" if instancia.activo else "apagada"
        self.stdout.write(self.style.SUCCESS(
            f"{verbo}: {sede} → {nombre} ({estado})."))
        self.stdout.write(
            "Las respuestas automáticas quedan APAGADAS: esta línea la atiende una persona."
        )
        self.stdout.write(
            "Falta configurar el webhook en Evolution: "
            "python manage.py configurar_webhook_evolution --instancia " + nombre
        )
