"""Carga el histórico mensual de marketing por sede (Piura y Lima, 2024-2026).

Datos tomados del reporte 'CONVERSEMOS PIURA Y LIMA'. Cada fila:
(mes, invertido S/, mensajes, citas nuevas, pacientes/clientes nuevos).

    python manage.py seed_metricas
    python manage.py seed_metricas --reset
"""
from django.core.management.base import BaseCommand

from core.models import Clinica, MetricaMensual

# (mes, invertido, mensajes, citas_nuevas, pacientes)
PIURA = {
    2024: [
        (1, 1291.54, 122, 17, 4), (2, 1330.16, 128, 15, 5), (3, 1356.57, 122, 17, 13),
        (4, 1393.09, 132, 22, 14), (5, 1301.39, 82, 18, 6), (6, 1271.28, 72, 22, 19),
        (7, 1293.06, 85, 34, 24), (8, 1396.06, 117, 29, 16), (9, 1366.71, 139, 26, 14),
        (10, 1341.60, 177, 34, 14), (11, 1552.78, 184, 19, 10), (12, 1537.68, 159, 17, 12),
    ],
    2025: [
        (1, 1417.40, 213, 37, 18), (2, 1493.56, 258, 25, 12), (3, 1596.35, 243, 36, 21),
        (4, 1220.41, 155, 44, 24), (5, 1468.19, 186, 39, 19), (6, 1534.20, 164, 29, 20),
        (7, 1178.37, 162, 25, 15), (8, 1210.12, 121, 45, 31), (9, 1590.87, 182, 43, 35),
        (10, 1543.61, 126, 63, 27), (11, 1504.21, 215, 44, 19), (12, 1461.12, 232, 37, 19),
    ],
    2026: [
        (1, 1453.25, 187, 53, 23), (2, 1251.99, 138, 31, 12), (3, 1537.49, 141, 35, 20),
        (4, 1578.43, 204, 30, 18), (5, 1498.94, 222, 27, 11), (6, 689.49, 48, 21, 5),
    ],
}
LIMA = {
    2024: [
        (1, 1364.69, 195, 15, 6), (2, 1327.36, 189, 15, 7), (3, 1336.67, 224, 15, 8),
        (4, 1288.18, 169, 13, 9), (5, 1322.39, 157, 15, 4), (6, 1271.28, 166, 12, 7),
        (7, 1396.01, 162, 25, 14), (8, 1295.18, 191, 19, 14), (9, 1320.06, 223, 24, 15),
        (10, 1319.70, 244, 40, 27), (11, 1206.77, 181, 34, 23), (12, 1241.44, 168, 17, 10),
    ],
    2025: [
        (1, 1433.91, 233, 33, 22), (2, 1471.85, 250, 21, 10), (3, 1416.93, 225, 20, 10),
        (4, 1578.62, 237, 28, 17), (5, 1418.62, 237, 39, 21), (6, 1457.30, 213, 23, 13),
        (7, 1301.83, 221, 25, 17), (8, 1283.36, 242, 44, 20), (9, 1564.89, 225, 31, 19),
        (10, 1504.05, 283, 40, 28), (11, 1389.17, 279, 26, 22), (12, 1589.02, 319, 31, 22),
    ],
    2026: [
        (1, 1594.02, 253, 38, 22), (2, 1124.27, 246, 28, 17), (3, 1548.13, 233, 26, 14),
        (4, 1277.74, 153, 24, 11), (5, 1722.23, 261, 11, 6), (6, 697.04, 78, 9, 1),
    ],
}


class Command(BaseCommand):
    help = "Carga el histórico mensual de marketing por sede (Piura y Lima, 2024-2026)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra y recarga el histórico.")

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        if options["reset"]:
            n, _ = MetricaMensual.objects.filter(clinica=clinica).delete()
            self.stdout.write(f"Histórico anterior borrado ({n} filas).")

        creadas = 0
        for sede, datos in (("piura", PIURA), ("lima", LIMA)):
            for anio, filas in datos.items():
                for mes, invertido, mensajes, citas, pacientes in filas:
                    _, creada = MetricaMensual.objects.update_or_create(
                        clinica=clinica, sede=sede, anio=anio, mes=mes,
                        defaults=dict(
                            invertido=invertido, mensajes=mensajes,
                            citas_nuevas=citas, pacientes=pacientes,
                        ),
                    )
                    creadas += 1 if creada else 0

        total = MetricaMensual.objects.filter(clinica=clinica).count()
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {total} filas de histórico en '{clinica.nombre}' "
            f"({creadas} nuevas)."
        ))
