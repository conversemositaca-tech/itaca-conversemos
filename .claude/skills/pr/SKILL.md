---
name: pr
description: Prepara un pull request en un proyecto de la Ítaca Software Factory - commits pequeños, mensaje en español, descripción con Definition of Done marcada, riesgos, migraciones y rollback. Úsala al cerrar cualquier trabajo. No hace push, ni merge, ni deploy sin autorización explícita de la persona.
---

# PR

## Antes
- `scripts/verificar.ps1 -Modo STANDARD` verde (FULL si toca migraciones, settings, permisos o dinero).
- `git status` limpio salvo lo que entra en el PR. Nada de `.env`, sqlite, xlsx ni datos reales.
- Si la rama está detrás de `origin/main`: rebase local y volver a verificar.

## Commits
- Uno por responsabilidad, reversible por separado: `tipo(ámbito): frase en español` (`security`, `rbac`, `tests`, `ci`, `backend`, `frontend`, `ux`, `core`, `docs`, `refactor`).
- Cuerpo: el porqué, qué se probó y con qué resultado.
- Línea final de co-autoría según la configuración del proyecto.
- **No edites `CLAUDE.md` como bitácora.** Solo si cambia una regla permanente.

## Descripción del PR
```
## Qué cambia y por qué
## Definition of Done
- [ ] Criterios de aceptación cumplidos
- [ ] Tests nuevos (matriz rol×endpoint / campos por rol / transiciones / doble envío según aplique)
- [ ] verificar STANDARD verde (pegar resumen)
- [ ] Revisión de seguridad (si toca permisos, datos personales, dinero o integraciones)
- [ ] QA en navegador por rol (o "no ejecutado" y por qué)
- [ ] Migraciones: aditivas / reversibles / rollback descrito
- [ ] Docs de dominio actualizadas si cambió una regla
## Riesgos y rollback
## Decisiones que necesitan a la persona
```

## Después
- Si es un arreglo universal (seguridad, bug de un patrón core), anota "portar al template de la fábrica" en el PR.
- **No** hagas push, PR remoto, merge ni deploy: deja el comando exacto para que la persona lo ejecute o lo autorice.
