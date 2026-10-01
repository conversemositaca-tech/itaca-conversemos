# 04 · Matriz rol × endpoint × método

Archivo: `core/tests_matriz_permisos.py`. Corre en el CI (job `seguridad`) y en todos los modos de `verificar.ps1`.

## Cómo funciona

- **ROLES** (6): anónimo, admin, asistente (coordinación/recepción), médico (psicólogo), comercial, analista.
- **ENDPOINTS** (28): método + ruta. Con un paciente **propio** y otro **ajeno** del psicólogo, y con adjunto, atención, consentimiento, sugerencia de riesgo y egreso de cada lado.
- **MATRIZ**: el código HTTP esperado por celda (28 × 6 = **168 combinaciones**).
- Las escrituras usan **cuerpos inválidos**: un rol autorizado recibe 400 y uno no autorizado 403/404. No se modifican datos, salvo el `DELETE` de egreso, que solo un admin puede hacer.
- Si una celda pasa de 4xx a 2xx/3xx, el test falla con el mensaje **"ESCALAMIENTO DE PRIVILEGIOS"** y la celda exacta. Si se vuelve más restrictiva, falla con "la política cambió", para que también ese cambio sea consciente.
- `ITACA_MATRIZ_GENERAR=1 python manage.py test core.tests_matriz_permisos` imprime la matriz real, para revisar o proponer un cambio.

**Cambiar una celda es cambiar la política de acceso:** se hace en el mismo PR que el código y con aprobación de Max.

## Cobertura por área

| Área | Endpoints |
|---|---|
| Pacientes e historia clínica | `pacientes` (lista, propio, ajeno), `atenciones` (ajena) |
| Adjuntos clínicos | descargar propio, descargar ajeno |
| Consentimiento | detalle ajeno |
| Riesgo clínico (IA) | ver ajena, resolver propia, resolver ajena |
| Continuidad | pendientes, caso ajeno |
| Dirección / gerencia | resumen de gerencia |
| Administración y finanzas | caja, liquidación, egresos (lista, borrar), usuarios (lista, crear), configuración de clínica, captación, WhatsApp |
| Duplicados | lista, fusionar |
| Comunicaciones | bitácora de mensajes, leads |
| Faro | alertas |
| Exportación sensible | respaldo por integración sin token |

## Prueba de que detecta escalamientos

Con el arreglo de adjuntos deshecho a mano, el test falló con:

```
ESCALAMIENTO DE PRIVILEGIOS:
adjuntos.descargar_propio · comercial: esperado 404, recibió 200
adjuntos.descargar_ajeno · medico: esperado 404, recibió 200
adjuntos.descargar_ajeno · comercial: esperado 404, recibió 200
```

## Brechas conocidas fijadas en la matriz (para la fase 1, no cambiadas aquí)

| Celda | Hoy | Por qué no se tocó |
|---|---|---|
| `faro.alertas` · médico = 200 | Cualquier psicólogo ve todas las alertas de tamizaje (menores) | No es P0-S de este encargo; requiere decidir quién atiende las alertas |
| `leads.lista` · médico = 200 | El psicólogo recibe el contacto de los leads | Hay que decidir si el psicólogo debe ver leads |
| Cobros (`/api/cobros/`) | Todos los roles ven todos los cobros (según la auditoría) | Fuera de la matriz a propósito: fijarlo como "esperado" congelaría una brecha. Entra en la fase 1 con su arreglo |

## Lo que la matriz no cubre (todavía)

- **Qué campos** ve cada rol dentro de una respuesta 200 (p. ej. el contacto enmascarado). Eso lo cubren tests puntuales en `tests_seguridad_p0` para consentimiento y bitácora; generalizarlo es fase 1.
- Endpoints públicos por token (agendamiento, Faro, consentimiento): tienen su propio modelo de acceso.
- Dirección Clínica y Continuidad fase 2: viven en `feat/direccion-clinica`. Al integrarla hay que añadir sus filas.
