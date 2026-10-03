"""QA de producción · SOLO LECTURA · solo conteos.

No imprime nombres, teléfonos, correos, documentos, tokens ni contenido clínico:
solo números agregados por rol, estado o antigüedad. La sesión de Postgres se
pone en READ ONLY antes de consultar, así que cualquier escritura fallaría.

Uso (desde la raíz del repo, con la CLI de Railway enlazada):

    railway ssh --service itaca-conversemos -- python manage.py shell < scripts/qa_prod_readonly.py

Si `railway ssh` no acepta stdin en tu terminal, copia el archivo al contenedor
y corre `python manage.py shell < /tmp/qa_prod_readonly.py`.

Qué mirar en la salida:
- "integridad entre clínicas": todo 0.
- comercial: visibles 0; psicólogo: visibles <= los de su clínica.
- "citas con >1 cobro vigente", "montos <= 0", "usadas > total": 0.
- consentimientos pendientes por antigüedad: base para decidir si se regeneran.
"""
from collections import Counter
from datetime import timedelta

from django.db import connection
from django.db.models import Count, F, Q
from django.utils import timezone

from core import politicas as P
from core.models import Clinica, RegistroAuditoria
from finanzas.models import Cobro, Paquete
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes.models import Adjunto, Atencion, Cita, Consentimiento, Paciente, SugerenciaRiesgo
from usuarios.models import Usuario

# Toda la sesión en solo lectura: si algo intentara escribir, Postgres lo rechaza.
assert connection.vendor == "postgresql"
with connection.cursor() as c:
    c.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")

print("== clínicas", Clinica.objects.count())
activos = Usuario.objects.filter(is_active=True)
print("== usuarios activos por rol", dict(Counter(activos.values_list("rol", flat=True))))

print("== alcance clínico por rol (pacientes visibles / pacientes de su clínica)")
fila = {}
for u in activos.exclude(clinica=None):
    base = Paciente.objects.filter(clinica=u.clinica_id)
    vis = P.acotar_clinico(base, u, "profesional").count()
    fila.setdefault(u.rol, []).append((vis, base.count(), P.ve_contacto(u), P.ve_finanzas(u),
                                      P.puede_registrar_pago(u), P.ve_token_consentimiento(u)))
for rol, xs in sorted(fila.items()):
    print(f"  {rol:10} n={len(xs)} visibles={[v for v, *_ in xs]} de={sorted({t for _, t, *_ in xs})}"
          f" contacto={sorted({x[2] for x in xs})} finanzas={sorted({x[3] for x in xs})}"
          f" registra_pago={sorted({x[4] for x in xs})} token_consent={sorted({x[5] for x in xs})}")

print("== integridad entre clínicas (debe ser 0)")
for nombre, qs in [
    ("cita", Cita.objects.exclude(clinica=F("paciente__clinica"))),
    ("atencion", Atencion.objects.exclude(clinica=F("paciente__clinica"))),
    ("cobro", Cobro.objects.exclude(clinica=F("paciente__clinica"))),
    ("cobro.cita", Cobro.objects.exclude(cita=None).exclude(clinica=F("cita__clinica"))),
    ("paquete", Paquete.objects.exclude(clinica=F("paciente__clinica"))),
    ("adjunto", Adjunto.objects.exclude(clinica=F("paciente__clinica"))),
    ("consentimiento", Consentimiento.objects.exclude(clinica=F("paciente__clinica"))),
    ("sugerencia", SugerenciaRiesgo.objects.exclude(clinica=F("paciente__clinica"))),
    ("paciente.profesional", Paciente.objects.exclude(profesional=None).exclude(clinica=F("profesional__clinica"))),
]:
    print(f"  {nombre:22} {qs.count()}")
if any(f.name == "paciente" for f in Mensaje._meta.fields):
    print(f"  {'mensaje':22} {Mensaje.objects.exclude(paciente=None).exclude(clinica=F('paciente__clinica')).count()}")

print("== cobros")
print("  por estado", dict(Cobro.objects.values_list("estado").annotate(n=Count("id"))))
dobles = (Cobro.objects.exclude(cita=None).exclude(estado=Cobro.Estado.ANULADO)
          .values("cita").annotate(n=Count("id")).filter(n__gt=1).count())
print("  citas con >1 cobro vigente", dobles)
print("  montos <= 0", Cobro.objects.filter(monto__lte=0).count())
print("  paquetes con usadas > total", Paquete.objects.filter(sesiones_usadas__gt=F("sesiones_total")).count())

print("== IA clínica")
print("  sugerencias por estado", dict(SugerenciaRiesgo.objects.values_list("estado").annotate(n=Count("id"))))
print("  riesgo oficial por valor", dict(Paciente.objects.values_list("riesgo").annotate(n=Count("id"))))

desde = timezone.now() - timedelta(hours=6)
print("== auditoría (últimas 6 h) por acción", dict(
    RegistroAuditoria.objects.filter(creado_en__gte=desde).values_list("accion").annotate(n=Count("id"))))
print("  total auditoría", RegistroAuditoria.objects.count())

print("== consentimientos")
hoy = timezone.now()
pend = Consentimiento.objects.filter(aceptado=False)
print("  total", Consentimiento.objects.count(), "aceptados", Consentimiento.objects.filter(aceptado=True).count(),
      "pendientes", pend.count())
print("  aceptados por vía", dict(Consentimiento.objects.filter(aceptado=True).values_list("aceptado_via").annotate(n=Count("id"))))
print("  pendientes por antigüedad",
      {"<7d": pend.filter(creado_en__gte=hoy - timedelta(days=7)).count(),
       "7-30d": pend.filter(creado_en__lt=hoy - timedelta(days=7), creado_en__gte=hoy - timedelta(days=30)).count(),
       ">30d": pend.filter(creado_en__lt=hoy - timedelta(days=30)).count()})
print("  pacientes con pendiente", pend.values("paciente").distinct().count())
print("  pendientes cuyo paciente YA aceptó otro del mismo tipo",
      pend.filter(paciente__consentimientos__aceptado=True, paciente__consentimientos__tipo=F("tipo")).distinct().count())

print("== leads", Lead.objects.count(), "· adjuntos", Adjunto.objects.count(), "· mensajes", Mensaje.objects.count())
print("FIN · solo lectura")
