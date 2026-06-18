# Clínica SaaS

Sistema multitenant de gestión para clínicas médicas. Ver [CLAUDE.md](CLAUDE.md)
para el contexto completo del proyecto.

## Stack
- Django 5.2 + PostgreSQL 17
- Aislamiento multitenant por `clinica_id` en cada tabla (Ley 29733).

## Apps
- `core` — modelo `Clinica` (tenant), base abstracta `ModeloTenant`, middleware de tenant.
- `usuarios` — `Usuario` (login por email, roles: admin / médico / asistente).
- `pacientes` — `Paciente`, `Cita`, `Atencion`.

## Puesta en marcha local

Requisitos: Python 3.12+ y PostgreSQL corriendo en local.

```powershell
# 1. Entorno virtual + dependencias
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env   # y completar credenciales de la base

# 3. Migraciones
.\.venv\Scripts\python.exe manage.py migrate

# 4. Servidor de desarrollo
.\.venv\Scripts\python.exe manage.py runserver
```

Panel admin: http://127.0.0.1:8000/admin/

## Frontend (React + Vite)

El prototipo `clinica-mvp.jsx` portado a `frontend/`, consumiendo la API.

```powershell
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxy /api -> Django :8000)
```

Atajo para levantar backend + frontend juntos: `./dev.ps1`.

## Estado
- Etapa 1: modelo de datos multitenant + migraciones + base en local. ✓
- Etapa 2: API REST (DRF) + frontend con el diseño del prototipo conectado a datos
  reales (Hoy, Agenda, Pacientes). Marketing y Finanzas quedan como diseño de
  referencia. ✓
- Próximo: login y roles (médico / asistente / admin) — reemplaza la clínica de
  desarrollo temporal por autenticación real.
