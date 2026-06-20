"""Verifica la configuración de Google Calendar (service account).

    python manage.py test_gcalendar

Sin credenciales reporta que la sincronización está en no-op (apagada). Con
credenciales, intenta leer cada calendario configurado para confirmar el acceso.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core import gcalendar


class Command(BaseCommand):
    help = "Prueba la conexión con Google Calendar (service account)."

    def handle(self, *args, **opt):
        creds_set = bool((settings.GOOGLE_CALENDAR_CREDENTIALS or "").strip())
        self.stdout.write(f"GOOGLE_CALENDAR_CREDENTIALS configurado: {creds_set}")
        ids = {k: v for k, v in (settings.GOOGLE_CALENDAR_IDS or {}).items() if v}
        if settings.GOOGLE_CALENDAR_DEFAULT:
            ids["(default)"] = settings.GOOGLE_CALENDAR_DEFAULT
        self.stdout.write(f"Calendarios configurados: {ids or 'ninguno'}")

        svc = gcalendar._service()
        if svc is None:
            self.stdout.write(self.style.WARNING(
                "Servicio NO disponible (faltan credenciales o la librería). "
                "La sincronización de citas queda en no-op (no rompe nada)."
            ))
            return
        self.stdout.write(self.style.SUCCESS("Servicio de Google Calendar: OK."))
        if not ids:
            self.stdout.write(self.style.WARNING(
                "Hay credenciales pero ningún calendario configurado "
                "(GOOGLE_CALENDAR_LIMA / GOOGLE_CALENDAR_PIURA / GOOGLE_CALENDAR_ID)."
            ))
            return
        for sede, cal in ids.items():
            try:
                r = svc.events().list(calendarId=cal, maxResults=1).execute()
                self.stdout.write(self.style.SUCCESS(
                    f"  {sede}: acceso OK ({cal}) — {len(r.get('items', []))} evento(s) leído(s)."
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {sede}: ERROR accediendo a {cal}: {e}"))
