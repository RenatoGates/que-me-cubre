"""Inicio de sesión con Google: el backend verifica el token de identidad (ID token) que el
cliente obtiene de Google (la app de Android con Credential Manager; la web con st.login).

Se verifica la firma con los certificados públicos de Google, el emisor, el vencimiento, que
el token sea para uno de nuestros clientes (QMC_GOOGLE_CLIENT_IDS) y que Google haya
verificado el correo. Alcances: openid, email y profile. De la cuenta de Google se guarda
solo el correo y su identificador (sub); el nombre y la foto no se guardan.
"""

from __future__ import annotations

import re
import time

import httpx
from google.auth import exceptions as google_exceptions
from google.auth import jwt as google_jwt

from ai.llm import config

CERTIFICADOS = "https://www.googleapis.com/oauth2/v1/certs"
EMISORES = {"accounts.google.com", "https://accounts.google.com"}
_cache: dict = {"hasta": 0.0, "certificados": {}}


class TokenInvalido(ValueError):
    pass


def clientes() -> list[str]:
    """Los ID de cliente de OAuth de Google Cloud (separados por comas). No son secretos."""
    return [c.strip() for c in (config("QMC_GOOGLE_CLIENT_IDS") or "").split(",") if c.strip()]


def disponible() -> bool:
    return bool(clientes())


def _certificados(forzar: bool = False) -> dict[str, str]:
    if forzar or time.time() >= _cache["hasta"]:
        r = httpx.get(CERTIFICADOS, timeout=10)
        r.raise_for_status()
        edad = re.search(r"max-age=(\d+)", r.headers.get("cache-control", ""))
        _cache.update(certificados=r.json(), hasta=time.time() + (int(edad.group(1)) if edad else 3600))
    return _cache["certificados"]


def verificar(id_token: str) -> dict:
    """{"sub", "correo"} de un ID token válido de Google para nuestra app, o TokenInvalido."""
    if not disponible():
        raise TokenInvalido("El inicio de sesión con Google no está configurado en este servidor.")
    try:
        kid = google_jwt.decode_header(id_token).get("kid")
        certificados = _certificados()
        if kid not in certificados:  # Google rota sus llaves: se piden de nuevo una vez
            certificados = _certificados(forzar=True)
        datos = google_jwt.decode(id_token, certs=certificados, audience=clientes(), clock_skew_in_seconds=60)
    except (ValueError, google_exceptions.GoogleAuthError, httpx.HTTPError) as e:
        raise TokenInvalido("No pude verificar tu inicio de sesión con Google.") from e
    if datos.get("iss") not in EMISORES:
        raise TokenInvalido("Ese token no lo emitió Google.")
    if not datos.get("email") or datos.get("email_verified") not in (True, "true"):
        raise TokenInvalido("Tu cuenta de Google no tiene un correo verificado.")
    return {"sub": str(datos["sub"]), "correo": datos["email"].strip().lower()}
