"""Cuentas: con Google (la opción principal) o con correo y contraseña; sesiones.

- Google: el backend verifica el ID token (backend/acceso_google.py).
- Correo y contraseña: la contraseña se guarda como hash scrypt con sal propia; nunca en claro.
  No hay recuperación de contraseña ni proveedor de correo: quien la olvida crea una cuenta
  nueva o entra con Google si su correo es de Google.
- Crear una cuenta, por cualquiera de las dos vías, exige aceptar la política de privacidad
  (Ley 29733).
- La sesión es un token al azar; en la base queda solo su hash.
- Qué desbloquea el plan pagado y cómo se activa: backend/pagos.py.
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
from backend import acceso_google, guardado
from backend.guardado import sesiones, usuarios

DIAS_SESION = 30
MIN_CLAVE = 8
_CORREO = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_CAMPOS = (usuarios.c.id, usuarios.c.correo, usuarios.c.plan, usuarios.c.clave_hash, usuarios.c.google_sub,
           usuarios.c.radiografia_gratis, usuarios.c.saldo, usuarios.c.radiografias)


class ErrorCuenta(ValueError):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def hash_clave(clave: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    return f"scrypt${sal.hex()}${hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32).hex()}"


def clave_correcta(clave: str, guardada: str) -> bool:
    try:
        _, sal, _ = guardada.split("$")
        return hmac.compare_digest(hash_clave(clave, bytes.fromhex(sal)), guardada)
    except ValueError:
        return False


def exentos() -> set[str]:
    """QMC_CORREOS_SIN_LIMITE: correos separados por coma (el dueño de la app). Esas cuentas no
    tienen tope diario, mensual ni bolsa, y tienen todas las funciones. El tope global de gasto
    del servicio sigue valiendo también para ellas."""
    return {c.strip().lower() for c in (config("QMC_CORREOS_SIN_LIMITE") or "").split(",") if c.strip()}


def _cuenta(fila) -> dict:
    exenta = fila.correo in exentos()
    return {"usuario_id": fila.id, "correo": fila.correo, "plan": "pagado" if exenta else fila.plan, "exenta": exenta,
            "con_clave": bool(fila.clave_hash), "con_google": bool(fila.google_sub), "radiografia_gratis": fila.radiografia_gratis,
            "saldo": fila.saldo or 0, "radiografias": fila.radiografias}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _abrir_sesion(c: sa.Connection, usuario_id: str) -> str:
    token = secrets.token_urlsafe(32)
    c.execute(sa.insert(sesiones).values(token_hash=_hash_token(token), usuario_id=usuario_id,
                                         expira=guardado.ahora() + timedelta(days=DIAS_SESION)))
    return token


def _crear(c: sa.Connection, correo: str, clave_hash: str, google_sub: str | None) -> str:
    ahora = guardado.ahora()
    usuario_id = "u_" + secrets.token_urlsafe(18)
    c.execute(sa.insert(usuarios).values(id=usuario_id, correo=correo, clave_hash=clave_hash, plan="gratis", creado=ahora,
                                         ultimo_acceso=ahora, acepto_privacidad=ahora, google_sub=google_sub))
    return usuario_id


def _leer(c: sa.Connection, condicion) -> dict | None:
    fila = c.execute(sa.select(*_CAMPOS).where(condicion)).first()
    return _cuenta(fila) if fila else None


def registrar(motor: sa.Engine, correo: str, clave: str, acepto: bool) -> tuple[str, dict]:
    """Crea la cuenta con correo y contraseña y abre sesión: (token, cuenta)."""
    correo = correo.strip().lower()
    if not acepto:
        raise ErrorCuenta("falta_consentimiento", "Para crear la cuenta tienes que aceptar la política de privacidad.")
    if not _CORREO.match(correo) or len(correo) > 254:
        raise ErrorCuenta("correo_invalido", "Ese correo no parece válido.")
    if len(clave) < MIN_CLAVE:
        raise ErrorCuenta("clave_corta", f"La contraseña tiene que tener al menos {MIN_CLAVE} caracteres.")
    try:
        with motor.begin() as c:
            usuario_id = _crear(c, correo, hash_clave(clave), None)
            return _abrir_sesion(c, usuario_id), _leer(c, usuarios.c.id == usuario_id)
    except IntegrityError as e:
        raise ErrorCuenta("correo_en_uso", "Ese correo ya tiene una cuenta. Entra con Google o usa otro correo.") from e


def entrar(motor: sa.Engine, correo: str, clave: str) -> tuple[str, dict]:
    with motor.begin() as c:
        cuenta = _leer(c, usuarios.c.correo == correo.strip().lower())
        if cuenta is not None and not cuenta["con_clave"]:
            raise ErrorCuenta("entra_con_google", "Esa cuenta entra con Google.")
        fila = c.execute(sa.select(usuarios.c.clave_hash).where(usuarios.c.id == cuenta["usuario_id"])).first() if cuenta else None
        if fila is None or not clave_correcta(clave, fila.clave_hash):
            raise ErrorCuenta("credenciales", "El correo o la contraseña no coinciden.")
        c.execute(sa.update(usuarios).where(usuarios.c.id == cuenta["usuario_id"]).values(ultimo_acceso=guardado.ahora()))
        return _abrir_sesion(c, cuenta["usuario_id"]), cuenta


def entrar_con_google(motor: sa.Engine, id_token: str, acepto: bool) -> tuple[str, dict, bool]:
    """Entra con el ID token de Google: (token, cuenta, si la cuenta es nueva).

    - Si ya entró antes con esa cuenta de Google: entra.
    - Si hay una cuenta con contraseña y ese mismo correo: Google acaba de probar que el correo
      es suyo, así que entra a esa cuenta, y la contraseña queda desactivada y se cierran sus
      otras sesiones (quien hubiera registrado ese correo antes sin ser su dueño pierde el acceso).
    - Si no hay cuenta: se crea, solo si aceptó la política de privacidad.
    """
    try:
        g = acceso_google.verificar(id_token)
    except acceso_google.TokenInvalido as e:
        raise ErrorCuenta("google_invalido", str(e)) from e
    with motor.begin() as c:
        cuenta = _leer(c, usuarios.c.google_sub == g["sub"]) or _leer(c, usuarios.c.correo == g["correo"])
        if cuenta is not None:
            if not cuenta["con_google"]:
                c.execute(sa.delete(sesiones).where(sesiones.c.usuario_id == cuenta["usuario_id"]))
            c.execute(sa.update(usuarios).where(usuarios.c.id == cuenta["usuario_id"]).values(
                google_sub=g["sub"], clave_hash="" if not cuenta["con_google"] else usuarios.c.clave_hash,
                ultimo_acceso=guardado.ahora()))
            return _abrir_sesion(c, cuenta["usuario_id"]), _leer(c, usuarios.c.id == cuenta["usuario_id"]), False
        if not acepto:
            raise ErrorCuenta("falta_consentimiento", "Para crear la cuenta tienes que aceptar la política de privacidad.")
        usuario_id = _crear(c, g["correo"], "", g["sub"])
        return _abrir_sesion(c, usuario_id), _leer(c, usuarios.c.id == usuario_id), True


def de_sesion(motor: sa.Engine, token: str | None) -> dict | None:
    """La cuenta dueña de ese token, o None si no existe o venció."""
    if not token:
        return None
    with motor.connect() as c:
        fila = c.execute(sa.select(*_CAMPOS, sesiones.c.expira).join(sesiones, sesiones.c.usuario_id == usuarios.c.id)
                         .where(sesiones.c.token_hash == _hash_token(token))).first()
    if fila is None or guardado._utc(fila.expira) <= guardado.ahora():
        return None
    return _cuenta(fila)


def clave_de(motor: sa.Engine, usuario_id: str, clave: str) -> bool:
    with motor.connect() as c:
        guardada = c.execute(sa.select(usuarios.c.clave_hash).where(usuarios.c.id == usuario_id)).scalar()
    return bool(guardada) and clave_correcta(clave, guardada)


def salir(motor: sa.Engine, token: str) -> None:
    with motor.begin() as c:
        c.execute(sa.delete(sesiones).where(sesiones.c.token_hash == _hash_token(token)))
