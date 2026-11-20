"""Los topes de gasto.

1. Por persona, al día y al mes (día y mes de Lima); corta el primero que se agote. Sin cuenta,
   por dispositivo: QMC_LIMITE_DISPOSITIVO_DIA y _MES. Cuenta gratis: QMC_LIMITE_GRATIS_DIA y
   _MES. La cuenta pagada no se mide por mes sino con su bolsa de consultas (backend/pagos.py),
   más un freno diario contra abuso: QMC_LIMITE_PAGADO_DIA.
2. Por IP, de respaldo: el identificador de dispositivo lo genera el cliente y se puede
   cambiar reinstalando; la IP pone un techo aunque eso pase.
3. Global mensual: QMC_TOPE_GLOBAL_USD. Al llegar, el servicio sigue y responde sin modelo
   (cláusulas sin veredicto).

Los contadores viven en una base (DATABASE_URL; sin ella, SQLite local): el disco del
servidor gratuito se borra en cada reinicio. No se guarda ni el identificador ni la IP,
solo su hash, y el de la IP cambia cada día.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ai.llm import config

LIMA = timezone(timedelta(hours=-5))  # el Perú no cambia de hora
RAIZ = Path(__file__).resolve().parent.parent

_meta = sa.MetaData()
uso_diario = sa.Table(
    "uso_diario", _meta,
    sa.Column("clave", sa.String(80), primary_key=True),
    sa.Column("dia", sa.String(10), primary_key=True),
    sa.Column("cuenta", sa.Integer, nullable=False),
)
gasto_mensual = sa.Table(
    "gasto_mensual", _meta,
    sa.Column("mes", sa.String(7), primary_key=True),
    sa.Column("usd", sa.Float, nullable=False),
    sa.Column("consultas", sa.Integer, nullable=False),
    sa.Column("sin_modelo", sa.Integer, nullable=False),
)


def _url() -> str:
    url = config("DATABASE_URL")
    if not url:
        carpeta = RAIZ / "data" / "privado"
        carpeta.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(carpeta / 'contadores.db').as_posix()}"
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def _entero(nombre: str, defecto: int) -> int:
    return int(config(nombre, str(defecto)) or defecto)


def hoy() -> str:
    return datetime.now(LIMA).strftime("%Y-%m-%d")


def clave_dispositivo(dispositivo: str) -> str:
    return "d:" + hashlib.sha256(dispositivo.encode()).hexdigest()[:40]


def clave_ip(ip: str) -> str:
    return "i:" + hashlib.sha256(f"{hoy()}|{ip}".encode()).hexdigest()[:40]


class Limites:
    def __init__(self, url: str | None = None) -> None:
        self.motor = sa.create_engine(url or _url(), pool_pre_ping=True)
        _meta.create_all(self.motor)
        with self.motor.begin() as c:  # los contadores de días pasados no se necesitan
            ayer = (datetime.now(LIMA) - timedelta(days=1)).strftime("%Y-%m-%d")
            c.execute(sa.delete(uso_diario).where(sa.func.length(uso_diario.c.dia) == 10, uso_diario.c.dia < ayer))
            c.execute(sa.delete(uso_diario).where(sa.func.length(uso_diario.c.dia) == 7, uso_diario.c.dia < self.mes()))

    # Sin cuenta: 3 al día y 10 al mes. Cuenta gratis: 3 al día y 20 al mes. Cuenta pagada: su
    # bolsa, con un freno de 20 al día.
    @property
    def limite_dispositivo(self) -> int:
        return _entero("QMC_LIMITE_DISPOSITIVO_DIA", 3)

    @property
    def limite_dispositivo_mes(self) -> int:
        return _entero("QMC_LIMITE_DISPOSITIVO_MES", 10)

    @property
    def limite_gratis_dia(self) -> int:
        return _entero("QMC_LIMITE_GRATIS_DIA", 3)

    @property
    def limite_gratis_mes(self) -> int:
        return _entero("QMC_LIMITE_GRATIS_MES", 20)

    @property
    def limite_pagado_dia(self) -> int:
        return _entero("QMC_LIMITE_PAGADO_DIA", 20)  # freno contra abuso, no un cupo

    def limite_de(self, plan: str) -> int:
        return {"pagado": self.limite_pagado_dia, "gratis": self.limite_gratis_dia}.get(plan, self.limite_dispositivo)

    def limite_mes_de(self, plan: str) -> int | None:
        return {"pagado": None, "gratis": self.limite_gratis_mes}.get(plan, self.limite_dispositivo_mes)

    @staticmethod
    def renueva_el_mes() -> str:
        """Primer día del mes siguiente (Lima), dd/mm/aaaa: cuando se reinicia el tope mensual."""
        hoy_ = datetime.now(LIMA)
        return (hoy_.replace(day=28) + timedelta(days=4)).replace(day=1).strftime("%d/%m/%Y")

    @property
    def limite_ip(self) -> int:
        return _entero("QMC_LIMITE_IP_DIA", 60)

    @property
    def limite_subidas(self) -> int:
        return _entero("QMC_LIMITE_SUBIDAS_DIA", 10)

    @property
    def tope_global_usd(self) -> float:
        return float(config("QMC_TOPE_GLOBAL_USD", "2.00") or 2.0)

    def usadas(self, clave: str, periodo: str | None = None) -> int:
        with self.motor.connect() as c:
            fila = c.execute(sa.select(uso_diario.c.cuenta).where(uso_diario.c.clave == clave, uso_diario.c.dia == (periodo or hoy())))
            return fila.scalar() or 0

    def tomar(self, clave: str, limite: int, periodo: str | None = None) -> bool:
        """Cuenta una más si no pasó el límite. La comparación y la suma van en una sola
        sentencia: dos consultas simultáneas no pueden pasar las dos por el último cupo.
        `periodo` es el día (por defecto, hoy) o el mes ("2026-11") al que se carga."""
        t, dia = uso_diario, periodo or hoy()
        for _ in range(2):
            with self.motor.begin() as c:
                suma = c.execute(sa.update(t).where(t.c.clave == clave, t.c.dia == dia, t.c.cuenta < limite)
                                 .values(cuenta=t.c.cuenta + 1))
                if suma.rowcount:
                    return True
                existe = c.execute(sa.select(t.c.cuenta).where(t.c.clave == clave, t.c.dia == dia)).scalar()
                if existe is not None:
                    return False
                if limite < 1:
                    return False
                try:
                    c.execute(sa.insert(t).values(clave=clave, dia=dia, cuenta=1))
                    return True
                except IntegrityError:  # otra consulta la creó a la vez: se reintenta la suma
                    pass
        return False

    def devolver(self, clave: str, periodo: str | None = None) -> None:
        t = uso_diario
        with self.motor.begin() as c:
            c.execute(sa.update(t).where(t.c.clave == clave, t.c.dia == (periodo or hoy()), t.c.cuenta > 0).values(cuenta=t.c.cuenta - 1))

    def olvidar(self, clave: str) -> None:
        """Borra todos los contadores de una clave (al borrar una cuenta)."""
        with self.motor.begin() as c:
            c.execute(sa.delete(uso_diario).where(uso_diario.c.clave == clave))

    # --- global mensual ---

    @staticmethod
    def mes() -> str:
        return datetime.now(LIMA).strftime("%Y-%m")

    def gasto_del_mes(self) -> dict:
        g = gasto_mensual
        with self.motor.connect() as c:
            fila = c.execute(sa.select(g.c.usd, g.c.consultas, g.c.sin_modelo).where(g.c.mes == self.mes())).first()
        usd, consultas, sin_modelo = fila or (0.0, 0, 0)
        return {"mes": self.mes(), "usd": round(usd, 6), "consultas": consultas, "sin_modelo": sin_modelo,
                "tope_usd": self.tope_global_usd}

    def tope_global_alcanzado(self) -> bool:
        return self.gasto_del_mes()["usd"] >= self.tope_global_usd

    def registrar_gasto(self, usd: float, sin_modelo: bool) -> None:
        g, mes = gasto_mensual, self.mes()
        valores = {"usd": g.c.usd + usd, "consultas": g.c.consultas + 1, "sin_modelo": g.c.sin_modelo + int(sin_modelo)}
        for _ in range(2):
            with self.motor.begin() as c:
                if c.execute(sa.update(g).where(g.c.mes == mes).values(**valores)).rowcount:
                    return
                try:
                    c.execute(sa.insert(g).values(mes=mes, usd=usd, consultas=1, sin_modelo=int(sin_modelo)))
                    return
                except IntegrityError:
                    pass
