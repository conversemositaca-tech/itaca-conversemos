"""Utilidades compartidas."""

_MESES_ABREV = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "set", "oct", "nov", "dic",
]

# Para parsear fechas escritas (datos de ejemplo). Incluye variantes comunes.
_MES_A_NUM = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def fecha_corta(d):
    """Formatea una fecha/datetime como '2 jun 2026' (estilo del prototipo)."""
    if d is None:
        return None
    return f"{d.day} {_MESES_ABREV[d.month - 1]} {d.year}"


def parse_fecha_corta(texto):
    """Convierte '2 jun 2026' en (anio, mes, dia). Solo para datos de ejemplo."""
    partes = texto.strip().split()
    dia = int(partes[0])
    mes = _MES_A_NUM[partes[1].lower()[:3]]
    anio = int(partes[2])
    return anio, mes, dia
