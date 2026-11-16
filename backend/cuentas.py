"""Cuentas: correo y contraseña, sesiones y plan.

- La contraseña se guarda como hash scrypt con sal propia; nunca en claro.
- No hay recuperación de contraseña: no hay proveedor de correo. Quien la olvida se registra
  de nuevo y vuelve a subir su póliza, y el registro lo avisa.
- El registro exige la aceptación explícita de la política de privacidad (Ley 29733).
- La sesión es un token al azar; en la base queda solo su hash.

    python -m backend.cuentas --plan pagado correo@ejemplo.com    # activar el plan a mano
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ai.llm import config
from backend import guardado
from backend.guardado import sesiones, usuarios

DIAS_SESION = 30
MIN_CLAVE = 8
AVISO_CLAVE = "Si olvidas tu contraseña no podemos recuperarla. Tendrías que registrarte de nuevo y volver a subir tu póliza."
_CORREO = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class ErrorCuenta(ValueError):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def _entero(nombre: str, defecto: int) -> int:
    return int(config(nombre, str(defecto)) or defecto)


def polizas_permitidas(plan: str) -> int:
    return _entero("QMC_POLIZAS_PAGADO", 4) if plan == "pagado" else _entero("QMC_POLIZAS_GRATIS", 1)


def dias_de_guardado(plan: str) -> int | None:
    """Plan gratis: la póliza guardada se borra sola a los 7 días. Plan pagado: no se borra."""
    return None if plan == "pagado" else _entero("QMC_DIAS_POLIZA_GRATIS", 7)


def hash_clave(clave: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    return f"scrypt${sal.hex()}${hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32).hex()}"


def clave_correcta(clave: str, guardada: str) -> bool:
    try:
        _, sal, _ = guardada.split("$")
        return hmac.compare_digest(hash_clave(clave, bytes.fromhex(sal)), guardada)
    except ValueError:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _abrir_sesion(c: sa.Connection, usuario_id: str) -> str:
    token = secrets.token_urlsafe(32)
    c.execute(sa.insert(sesiones).values(token_hash=_hash_token(token), usuario_id=usuario_id,
                                         expira=guardado.ahora() + timedelta(days=DIAS_SESION)))
    return token


def registrar(motor: sa.Engine, correo: str, clave: str, acepto: bool) -> tuple[str, dict]:
    """Crea la cuenta y abre sesión: (token, cuenta)."""
    correo = correo.strip().lower()
    if not acepto:
        raise ErrorCuenta("falta_consentimiento", "Para crear la cuenta tienes que aceptar la política de privacidad.")
    if not _CORREO.match(correo) or len(correo) > 254:
        raise ErrorCuenta("correo_invalido", "Ese correo no parece válido.")
    if len(clave) < MIN_CLAVE:
        raise ErrorCuenta("clave_corta", f"La contraseña tiene que tener al menos {MIN_CLAVE} caracteres.")
    ahora = guardado.ahora()
    usuario_id = "u_" + secrets.token_urlsafe(18)
    # PUNTO DE INTEGRACIÓN (proveedor de correo): aquí iría el envío del correo de verificación
    # y, con él, la recuperación de contraseña. Hoy no se envía ningún correo.
    try:
        with motor.begin() as c:
            c.execute(sa.insert(usuarios).values(id=usuario_id, correo=correo, clave_hash=hash_clave(clave), plan="gratis",
                                                 creado=ahora, ultimo_acceso=ahora, acepto_privacidad=ahora))
            token = _abrir_sesion(c, usuario_id)
    except IntegrityError as e:
        raise ErrorCuenta("correo_en_uso", "Ya hay una cuenta con ese correo.") from e
    return token, {"usuario_id": usuario_id, "correo": correo, "plan": "gratis"}


def entrar(motor: sa.Engine, correo: str, clave: str) -> tuple[str, dict]:
    with motor.begin() as c:
        fila = c.execute(sa.select(usuarios).where(usuarios.c.correo == correo.strip().lower())).first()
        if fila is None or not clave_correcta(clave, fila.clave_hash):
            raise ErrorCuenta("credenciales", "El correo o la contraseña no coinciden.")
        c.execute(sa.update(usuarios).where(usuarios.c.id == fila.id).values(ultimo_acceso=guardado.ahora()))
        return _abrir_sesion(c, fila.id), {"usuario_id": fila.id, "correo": fila.correo, "plan": fila.plan}


def de_sesion(motor: sa.Engine, token: str | None) -> dict | None:
    """La cuenta dueña de ese token, o None si no existe o venció."""
    if not token:
        return None
    with motor.connect() as c:
        fila = c.execute(sa.select(usuarios.c.id, usuarios.c.correo, usuarios.c.plan, sesiones.c.expira)
                         .join(sesiones, sesiones.c.usuario_id == usuarios.c.id)
                         .where(sesiones.c.token_hash == _hash_token(token))).first()
    if fila is None or guardado._utc(fila.expira) <= guardado.ahora():
        return None
    return {"usuario_id": fila.id, "correo": fila.correo, "plan": fila.plan}


def salir(motor: sa.Engine, token: str) -> None:
    with motor.begin() as c:
        c.execute(sa.delete(sesiones).where(sesiones.c.token_hash == _hash_token(token)))


def cambiar_plan(motor: sa.Engine, correo: str, plan: str) -> bool:
    """Activa o quita el plan pagado. Hoy se llama a mano (ver el uso arriba).
    PUNTO DE INTEGRACIÓN (pasarela de pago): cuando haya cobro del pago único de S/ 3,99, la
    confirmación de la pasarela llama a esta función; con QMC_PAGOS_ACTIVOS=0 no hay cobro."""
    if plan not in ("gratis", "pagado"):
        raise ValueError("plan: gratis o pagado")
    with motor.begin() as c:
        fila = c.execute(sa.select(usuarios.c.id).where(usuarios.c.correo == correo.strip().lower())).first()
        if fila is None:
            return False
        c.execute(sa.update(usuarios).where(usuarios.c.id == fila.id).values(plan=plan))
    if plan == "pagado":
        guardado.conservar_polizas(motor, fila.id)
    return True


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    from backend.limites import Limites

    p = argparse.ArgumentParser(description="Cambia el plan de una cuenta a mano.")
    p.add_argument("--plan", required=True, choices=["gratis", "pagado"])
    p.add_argument("correo")
    a = p.parse_args()
    motor = Limites().motor
    guardado.crear_tablas(motor)
    print("hecho" if cambiar_plan(motor, a.correo, a.plan) else "no hay una cuenta con ese correo")
