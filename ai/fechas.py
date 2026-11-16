"""Fechas y plazos, sin modelo: la fecha del hecho que la persona escribió y la fecha límite.

El modelo solo propone el plazo que dice la póliza (cantidad, unidad y su cita). Todo lo
demás es código: comprobar que ese número está escrito en la cita, leer la fecha del hecho
del texto de la persona y sumar los días.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone

LIMA = timezone(timedelta(hours=-5))
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), start=1)} | {"setiembre": 9}
_UNIDADES = "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete dieciocho diecinueve veinte".split()
_DECENAS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}


def hoy() -> date:
    return datetime.now(LIMA).date()


def en_palabras(n: int) -> list[str]:
    """Formas escritas de n entre 1 y 99 ("siete", "veintiún"/"veintiuno", "cuarenta y ocho")."""
    if 1 <= n <= 20:
        return [_UNIDADES[n]] + (["un", "una"] if n == 1 else [])
    if 21 <= n <= 29:
        base = {1: ["veintiuno", "veintiún", "veintiuna"], 2: ["veintidós"], 3: ["veintitrés"], 6: ["veintiséis"]}
        return base.get(n - 20, ["veinti" + _UNIDADES[n - 20]])
    if 30 <= n <= 99:
        decena, unidad = _DECENAS[n // 10 * 10], n % 10
        return [decena] if unidad == 0 else [f"{decena} y {_UNIDADES[unidad]}"] + ([f"{decena} y un", f"{decena} y una"] if unidad == 1 else [])
    return []


def numero_en_texto(n: int, texto: str) -> bool:
    """¿El número está escrito en el texto, en cifras o en palabras? Para no aceptar un plazo
    que la cita no dice."""
    if re.search(rf"(?<![\d.,]){n}(?![\d.,]*\d)", texto):
        return True
    plano = texto.lower()
    return any(re.search(rf"\b{re.escape(p)}\b", plano) for p in en_palabras(n))


_PALABRA_A_NUMERO = {p: n for n in range(1, 31) for p in en_palabras(n)}
_RE_HACE = re.compile(r"\bhace\s+(\d{1,3}|[a-záéíóú]+)\s+(d[íi]as?|semanas?)\b", re.IGNORECASE)
_RE_LARGA = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+(?:de|del)\s+(\d{4}))?\b", re.IGNORECASE)
_RE_CORTA = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?(?!\d)")
_RELATIVAS = [(re.compile(r"\b(?:anteayer|antes\s+de\s+ayer|antier)\b", re.IGNORECASE), 2),
              (re.compile(r"\bayer\b", re.IGNORECASE), 1)]


def _valida(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def fecha_en_texto(texto: str, referencia: date | None = None) -> tuple[date, str] | None:
    """La fecha del hecho si la persona la escribió: (fecha, las palabras de donde sale).
    Reconoce "ayer", "anteayer", "hace 3 días", "hace una semana", "el 12 de noviembre (de
    2026)" y "12/11(/2026)". Sin año, la más reciente que no sea futura. "Hoy" no se toma:
    aparece demasiado en frases que no hablan de cuándo pasó."""
    ref = referencia or hoy()
    for patron, dias in _RELATIVAS:
        m = patron.search(texto)
        if m:
            return ref - timedelta(days=dias), m.group(0)
    m = _RE_HACE.search(texto)
    if m:
        cantidad = int(m.group(1)) if m.group(1).isdigit() else _PALABRA_A_NUMERO.get(m.group(1).lower())
        if cantidad:
            return ref - timedelta(days=cantidad * (7 if m.group(2).lower().startswith("semana") else 1)), m.group(0)
    for m in _RE_LARGA.finditer(texto):
        mes = MESES.get(m.group(2).lower())
        if mes:
            f = _sin_anio(int(m.group(1)), mes, int(m.group(3)) if m.group(3) else None, ref)
            if f:
                return f, m.group(0)
    m = _RE_CORTA.search(texto)
    if m:
        anio = int(m.group(3)) if m.group(3) else None
        f = _sin_anio(int(m.group(1)), int(m.group(2)), anio + 2000 if anio is not None and anio < 100 else anio, ref)
        if f:
            return f, m.group(0)
    return None


def _sin_anio(dia: int, mes: int, anio: int | None, ref: date) -> date | None:
    if anio is not None:
        f = _valida(anio, mes, dia)
        return f if f and f <= ref else None
    f = _valida(ref.year, mes, dia)
    if f and f > ref:
        f = _valida(ref.year - 1, mes, dia)
    return f


def fecha_limite(hecho: date, cantidad: int, unidad: str, tipo_dias: str, referencia: date | None = None) -> dict:
    """La fecha límite para avisar y cuánto falta. Las notas dicen cada supuesto del cálculo."""
    ref = referencia or hoy()
    notas = []
    if unidad == "horas":
        dias = math.ceil(cantidad / 24)
        limite = hecho + timedelta(days=dias)
        notas.append(f"El plazo es de {cantidad} horas y no sé a qué hora ocurrió: cuento {dias} día{'s' if dias != 1 else ''} completo{'s' if dias != 1 else ''}.")
    elif tipo_dias == "habiles":
        limite, quedan = hecho, cantidad
        while quedan > 0:
            limite += timedelta(days=1)
            if limite.weekday() < 5:
                quedan -= 1
        notas.append("Son días hábiles: conté de lunes a viernes y no conté feriados, así que la fecha real puede ser posterior.")
    else:
        limite = hecho + timedelta(days=cantidad)
        if tipo_dias != "calendario":
            notas.append("La póliza no dice si son días hábiles o calendario: conté días calendario, que da la fecha más temprana.")
    restantes = (limite - ref).days
    return {"fecha_hecho": hecho.isoformat(), "fecha_limite": limite.isoformat(), "dias_restantes": restantes,
            "vencido": restantes < 0, "notas": notas}
