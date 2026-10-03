# STACK-EVIDENCE · Django vs Next.js para la Software Factory

> Este documento reúne evidencia; **no decide**. La decisión es de Max y no se fuerza aquí.
> Fuentes: auditoría (1 oct 2026) de 8 sistemas y 14 bots en `C:\projects`, Fases 0–1 sobre Conversemos y el template de la Fase 3.

## Lo que hay hoy

| Stack | Sistemas | Tests formales | CI | En producción con datos sensibles |
|---|---|---|---|---|
| Django + DRF + React/Vite | Conversemos (41 k LOC de backend, **1.131 tests**), Mont' Sinai (8 archivos de test), clinica-saas (7) | Conversemos: sí, + matriz de permisos, campos por rol y Postgres | Solo Conversemos (4 jobs desde la Fase 0/1) | Sí: 2 clínicas (datos de salud) |
| Next.js + Prisma | beauty-spa-saas / Aldanna (70+ modelos) | No; 39 scripts `probar-*.cjs` | No | Sí (centro estético, sin datos clínicos) |
| Next.js + Supabase | life-wellness, bonos-descuentos (fork), mirai-saas / Notaluma | No; scripts sueltos | Solo respaldo en Life | Sí (Notaluma: datos de terapia, con RLS) |

## Evaluación por criterio

| Criterio | Django | Next.js | Evidencia |
|---|---|---|---|
| Velocidad de arranque | Media: template de la Fase 3 listo y probado | Alta para landing + CRUD | Los 4 sistemas más nuevos (ago–set 2026) se hicieron en Next |
| Productividad sostenida | Alta en back-office | Media: dos sub-stacks (Prisma / Supabase) | Life y Bonos se copiaron entre sí: el problema de la copia también existe en Next |
| ORM y migraciones | Maduras; `makemigrations --check` en CI | Prisma: buenas; Supabase: 23 archivos SQL a mano en Life | — |
| Admin | Incluido (útil para soporte; Faro gestiona colegios desde ahí) | No incluido | — |
| Auth | Sesión + CSRF + throttle probados | Supabase Auth / propio, según el proyecto | — |
| RBAC | `core/politicas.py` + matriz de 210 celdas + campos por rol | Aldanna: RBAC Role/Permission en Prisma (modelo más fino); Notaluma: RLS | El mejor modelo de RBAC de negocio está en Prisma; el mejor *contrato probado* de RBAC, en Django |
| Jobs / tareas | Sin cola propia (cron externo) | Sin cola propia (cron / Vercel) | Empate: ninguno lo tiene resuelto |
| Integraciones (WhatsApp, correo) | Las más maduras de la agencia (Evolution con tests, correo con webhooks) | 14 clientes de Evolution distintos en JS (bots) | — |
| Testing | Suite grande, rápida (~100 s) con hasher de test; Postgres en CI | Casi sin tests formales | **La diferencia más grande hoy** |
| Frontend | React separado (Conversemos: monolito de 16 k líneas) | Integrado (SSR, rutas, layouts) | Next resuelve rutas y layout de serie; Django+React necesita disciplina (UI base de la Fase 1) |
| Mantenimiento | Django LTS, cambios graduales | Next 16 "no es el Next que conoces" (AGENTS.md de Life): cambios que rompen compatibilidad | — |
| IA (Claude) | Muy productivo; la fábrica ya tiene rules, hooks y skills probadas aquí | Muy productivo; `criterio-de-diseno` y `listo-para-produccion` asumen Next + Supabase | — |
| Reutilización | Template de la Fase 3 funcionando | Sin template; motor + piel (`lib/marca.ts`) en Life/Bonos | — |
| Operación por una persona | Railway + Postgres, un solo servicio | Vercel/Railway + Supabase: más servicios administrados | — |

## Lo que la evidencia sí permite afirmar
1. **Para back-office clínico con datos sensibles**, hoy solo Django tiene las protecciones *probadas*: matriz de permisos, campos por rol, auditoría, Postgres en CI, hasher de test y un template que pasa su smoke test.
2. **Para landing, reservas y productos comerciales livianos**, Next tiene la ventaja de velocidad y la mayoría de los proyectos recientes.
3. **Mantener dos cores completos** (uno por stack) duplica exactamente el problema que la fábrica quiere resolver.

## Lo que la evidencia NO permite afirmar todavía
- Que Next sea más lento de mantener o menos seguro: no hay tests para medirlo.
- Qué stack produce menos retrabajo: solo Conversemos tiene la historia de PR medida (~31 % de correcciones).

## Opciones para Max (sin recomendación forzada)
| Opción | Implica |
|---|---|
| A. Django como core de back-office; Next solo para sitios públicos | Usar el template de la Fase 3; los proyectos Next consumen la API |
| B. Next como stack único | Portar a Next lo probado (matriz, campos por rol, auditoría, Postgres en CI) **antes** del próximo sistema clínico |
| C. Dos templates con specs comunes | Las specs y los tests de contrato (identidad, agenda, mensajería) son agnósticos; cada template los implementa. Es el más caro |

**Dato que falta para decidir mejor:** medir retrabajo (PR de corrección / PR total) en un proyecto Next con la misma vara que Conversemos.
