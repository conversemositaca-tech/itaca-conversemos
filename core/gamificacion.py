"""Sistema de progreso del psicólogo ("Mi Progreso Ítaca").

Calcula NIVEL + puntos (XP) + medallas por niveles a partir de métricas reales del
psicólogo, usando una configuración que la GERENCIA puede editar (guardada en
Clinica.gamificacion; si está vacía se usa DEFAULT). Premia calidad Y volumen.
"""

# Configuración por defecto (editable por gerencia). Cada medalla tiene:
#   metrica: qué mide (calculada en mi_panel) · niveles: umbrales de bronce→…
#   puntos: XP por cada nivel alcanzado · sufijo: "%" para métricas de porcentaje.
DEFAULT_GAMIFICACION = {
    "puntos_por_nivel": 100,
    "rangos": ["Aprendiz", "En camino", "Referente", "Maestro/a Ítaca", "Leyenda Ítaca"],
    "medallas": [
        {"clave": "historias", "label": "Excelencia clínica", "emoji": "📋",
         "metrica": "historias", "niveles": [10, 50, 100, 250], "puntos": 8, "sufijo": "",
         "desc": "Historias clínicas registradas y al día."},
        {"clave": "satisfaccion", "label": "Pacientes felices", "emoji": "⭐",
         "metrica": "satisfaccion", "niveles": [70, 80, 90], "puntos": 10, "sufijo": "%",
         "desc": "Satisfacción de tus pacientes (NPS)."},
        {"clave": "continuidad", "label": "Continuidad", "emoji": "🔁",
         "metrica": "continuidad", "niveles": [5, 15, 30, 60], "puntos": 6, "sufijo": "",
         "desc": "Pacientes que continúan su proceso contigo."},
        {"clave": "cierre", "label": "Cierre con claridad", "emoji": "🎯",
         "metrica": "cierre", "niveles": [50, 65, 80], "puntos": 6, "sufijo": "%",
         "desc": "Consultas que inician proceso terapéutico."},
        {"clave": "sesiones", "label": "Dedicación", "emoji": "🩺",
         "metrica": "sesiones", "niveles": [10, 25, 50, 100, 250, 500], "puntos": 3, "sufijo": "",
         "desc": "Sesiones acompañadas en total."},
    ],
}


def config_efectiva(clinica):
    """Config de la clínica mezclada con la de por defecto (si falta o está incompleta)."""
    g = (getattr(clinica, "gamificacion", None) or {}) if clinica else {}
    return {
        "puntos_por_nivel": g.get("puntos_por_nivel") or DEFAULT_GAMIFICACION["puntos_por_nivel"],
        "rangos": g.get("rangos") or DEFAULT_GAMIFICACION["rangos"],
        "medallas": g.get("medallas") or DEFAULT_GAMIFICACION["medallas"],
    }


def calcular(config, valores):
    """Devuelve {xp, nivel, rango, xp_en_nivel, xp_por_nivel, es_max, medallas[]}.
    `valores` = {metrica: numero} (sesiones, historias, satisfaccion, continuidad, cierre)."""
    medallas, xp = [], 0
    for m in config.get("medallas", []):
        try:
            v = float(valores.get(m.get("metrica")) or 0)
        except (TypeError, ValueError):
            v = 0
        niveles = [n for n in (m.get("niveles") or []) if isinstance(n, (int, float))]
        nivel = sum(1 for t in niveles if v >= t)
        pts = nivel * int(m.get("puntos") or 0)
        xp += pts
        medallas.append({
            "clave": m.get("clave"), "label": m.get("label"), "emoji": m.get("emoji") or "🏅",
            "desc": m.get("desc", ""), "sufijo": m.get("sufijo", ""),
            "valor": int(v) if v == int(v) else round(v, 1),
            "nivel": nivel, "total_niveles": len(niveles),
            "siguiente": niveles[nivel] if nivel < len(niveles) else None,
            "puntos": pts,
        })
    ppn = int(config.get("puntos_por_nivel") or 100) or 100
    rangos = config.get("rangos") or ["Nivel 1"]
    nivel_general = xp // ppn
    rango = rangos[min(nivel_general, len(rangos) - 1)]
    return {
        "xp": xp, "nivel": nivel_general, "rango": rango,
        "xp_en_nivel": xp % ppn, "xp_por_nivel": ppn,
        "es_max": nivel_general >= len(rangos) - 1,
        "medallas": medallas,
    }
