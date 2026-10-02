# Software Factory — Estado al 1 oct 2026 (Fases 0–4)

| Fase | Estado | Dónde |
|---|---|---|
| 0 · Secure & Accelerate | **Completada** (rebasada sobre `9ed776c`) | `docs/SOFTWARE-FACTORY-PHASE-0.md` |
| 1 · Integrate, Harden & Standardize | **Completada** (Dirección Clínica la integra otra sesión) | `docs/SOFTWARE-FACTORY-PHASE-1.md` |
| 2 · Extract & Reuse | **Completada** (template mínimo; agenda, caja, mensajería e identidad pasan a una ola posterior) | `docs/factory/CORE-MAP.md`, `EXTRACTION-PLAN.md` |
| 3 · Template + generador | **Completada** | Repo local `C:\projects\itaca-software-factory` (`template/`, `generator/`); smoke en `C:\projects\factory-smoke-test` |
| 4 · AI Software Factory | **Completada** | Fábrica: `skills/`, `agents/`, `docs/`; Conversemos: `.claude/skills`, `.claude/agents`; `docs/factory/STACK-EVIDENCE.md` |

**Nada se publicó.** Rama `chore/software-factory-phase-0`: 33 commits locales sobre `origin/main` `9ed776c`, sin upstream. Fábrica: 7 commits locales, sin remoto.

## Siguiente paso de Max

1. Revisar la rama y, si está bien:
   ```powershell
   cd C:\projects\itaca-factory-p0
   git push -u origin chore/software-factory-phase-0
   gh pr create --base main --title "Software Factory: fases 0–4 (seguridad, RBAC, verificación, CI, fábrica)" --body-file docs/SOFTWARE-FACTORY-ESTADO.md
   ```
   El CI (4 jobs) correrá por primera vez de verdad.
2. Antes o después de mergear: configurar `ITACA_TOKEN_RESPALDO`, `ITACA_TOKEN_TAREAS` e `ITACA_TOKEN_ELI` en Railway, kira-bot y Eli.
3. Responder las decisiones D1–D9 (`docs/software-factory-phase-1/04-decisiones-para-max.md`) y elegir stack (`docs/factory/STACK-EVIDENCE.md`).
4. Para la fábrica: crear un repo privado en GitHub y hacer push de `C:\projects\itaca-software-factory`.
