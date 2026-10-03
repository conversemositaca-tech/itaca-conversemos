# 07 · Métricas antes / después

Medido el 1 oct 2026 en la misma máquina (Windows, Python 3.14 del `.venv`, Node 24), salvo que se indique otra cosa.

## Tests

| | Antes | Después |
|---|---|---|
| Cantidad | 1.043 | **1.071** (+24 regresión P0-S, +2 matriz, +2 hasher) |
| Duración local de la suite completa | **No terminó**: abortada a los 55 min (auditoría); 528/1.043 en ~116 min (Fase 0, con carga concurrente) | **103 s** sin otra carga (64 s de ejecución + 36 s de base); 77 s dentro de FULL |
| Mejora | — | **> 30×** como cota inferior: 55 min sin terminar frente a 103 s. La línea base nunca terminó, así que no hay un factor exacto |
| Paso de pruebas en CI (Linux) | 460 s (última corrida exitosa) | No medido (sin push); estimado ~1–1,5 min (**HIPÓTESIS**) |

## Verificación

| Modo | Tiempo medido | Contenido |
|---|---|---|
| FAST | **20,7 s** (cambios en scripts) · **44,7 s** (cambio en un `.jsx`) | check, migraciones, tests de las apps tocadas + seguridad + matriz, ESLint de los cambiados |
| STANDARD | **141 s** (sin caché de ESLint) · ~105 s dentro del hook | + suite completa, build y ESLint del proyecto |
| FULL | **138 s** · **87 s** (corrida final, con caché de ESLint) | + `check --deploy` |
| Stop hook | **1 s** con el árbol ya verificado · ~105–110 s si hay que verificar | STANDARD silencioso |

## Contexto

| | Antes | Después |
|---|---|---|
| `CLAUDE.md` | 85.671 bytes | 6.023 bytes |
| Tokens aproximados | ~21.400 | ~1.500 |
| Reducción | — | **−93 %** |
| Reglas por dominio | 0 | 8 (se cargan por ruta) |

## QA

**Controles manuales eliminados (pasan a ser automáticos): 7**

1. `manage.py check`
2. `makemigrations --check`
3. Correr la suite completa con sus trampas de Windows (a archivo, sin `--parallel`, `--noinput`)
4. Build de Vite
5. Comparar ESLint contra `main` a ojo ("106 avisos")
6. Recordar verificar antes de declarar terminado (ahora lo hace el Stop hook)
7. Revisar a mano que un cambio no abra permisos (ahora lo hace la matriz)

**Controles automáticos añadidos: 11**

1. Guardia del hasher de pruebas (2 tests)
2. Regresión P0-S (24 tests)
3. Matriz rol × endpoint (168 celdas)
4. `verificar.ps1` FAST
5. `verificar.ps1` STANDARD
6. `verificar.ps1` FULL
7. Stop hook
8. Job de CI `seguridad`
9. Job de CI `frontend` con ESLint sin deuda nueva
10. `manage.py check` en CI
11. `concurrency` en CI

## Seguridad (P0-S)

| Estado | Cantidad | Riesgos |
|---|---|---|
| OPEN | 0 | — |
| FIXED (en rama, sin desplegar) | 4 | Adjuntos clínicos, tokens de consentimiento, riesgo clínico de Eli, hosts de Railway |
| MITIGATED | 1 | Token de integración (código listo; compatible con los consumidores actuales) |
| BLOCKED | 1 (parcial) | El cierre total del token de integración depende de configurar `ITACA_TOKEN_*` en Railway, kira-bot y Eli |

## Autorización

| | Valor |
|---|---|
| Combinaciones endpoint × rol cubiertas | **168** (28 endpoints × 6 roles) |
| Escrituras cubiertas sin modificar datos | 6 endpoints (cuerpo inválido → 400 autorizado, 403/404 no autorizado) |
| Brechas conocidas fijadas, no corregidas | 2 en la matriz (Faro, leads) + 1 fuera de ella (cobros) |
| Detección probada | Sí: deshacer el arreglo de adjuntos produce 3 celdas de "ESCALAMIENTO DE PRIVILEGIOS" |

## Calidad

| Chequeo | Resultado final (FULL sobre `b47992b`) |
|---|---|
| Backend | 1.071 tests OK |
| Frontend: build | OK |
| ESLint | 74 errores / 38 avisos = línea base; **0 errores nuevos** |
| Migraciones | Al día (`pacientes/0039` aditiva) |
| `check --deploy` | 1 aviso: `security.W021` (HSTS preload) |
| Regresión de seguridad | 24/24 + matriz 2/2 |
