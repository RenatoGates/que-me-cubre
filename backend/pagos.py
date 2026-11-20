"""El plan pagado: qué desbloquea y cómo se activa. Es el único archivo que toca el cobro.

Producto: pago de S/ 3,99 vendido con Google Play Billing desde la app de Android (Fase 4).
Cada pago suma una bolsa de 200 consultas que no caducan; cuando se acaba, se puede volver a
comprar. Por eso, en Play, la compra se consume (consumeAsync) después de acreditarla: un
producto que no se consume no se puede comprar dos veces. La versión web no vende.

Qué desbloquea (gratis siguen la repregunta, varias preguntas, qué hacer ahora, la alerta de
plazo y el mapa):
- guardar hasta 4 pólizas, sin borrado automático (gratis: 1, que se borra a los 14 días);
- la bolsa: cada consulta descuenta 1 y cada radiografía nueva, 5. Además, un freno de 20
  consultas al día contra abuso o scripts (backend/limites.py). Sin saldo, la cuenta consulta
  con los topes del plan gratis y se le ofrece volver a comprar;
- ¿Pagas doble? (superposiciones entre pólizas): necesita varias pólizas;
- la radiografía de cualquier póliza. Cada cuenta gratis tiene una sola, completa, de muestra.

Cómo se cobra: la app (con sesión iniciada) compra con Play Billing, con el id ofuscado de la
cuenta (`id_ofuscado`), y manda el token de compra a POST /v1/cuenta/compra. El backend lo
verifica contra la Google Play Developer API con una cuenta de servicio
(QMC_PLAY_CUENTA_SERVICIO, el JSON de la llave, solo en Render): la compra tiene que estar
pagada, sin consumir y hecha por esa misma cuenta. Recién entonces se acredita (una misma
compra, una sola vez), se reconoce en Play y la app la consume para poder volver a comprar.
Nunca se confía en lo que dice el cliente. Sin la cuenta de servicio, el cobro responde 501.
"""

from __future__ import annotations

import hashlib
import json

import httpx
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ai.llm import config
from backend import guardado
from backend.guardado import compras, usuarios

PAQUETE = config("QMC_PAQUETE_ANDROID") or "com.renatogates.quecubre"
PLAY = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
PRODUCTO = "consultas_200"  # id del producto en Play Console; se consume tras acreditarlo para poder recomprarlo
PRECIO = "S/ 3,99"
COSTO_RADIOGRAFIA = 5


class CobroNoDisponible(RuntimeError):
    """Todavía no hay cobro: Play Billing llega con la app de Android (Fase 4)."""


class CompraInvalida(ValueError):
    """Play no confirma esa compra."""


def _entero(nombre: str, defecto: int) -> int:
    return int(config(nombre, str(defecto)) or defecto)


def consultas_por_pago() -> int:
    return _entero("QMC_CONSULTAS_POR_PAGO", 200)


def polizas_permitidas(plan: str) -> int:
    return _entero("QMC_POLIZAS_PAGADO", 4) if plan == "pagado" else _entero("QMC_POLIZAS_GRATIS", 1)


def dias_de_guardado(plan: str) -> int | None:
    """Plan gratis: la póliza guardada se borra sola a los 14 días. Plan pagado: no se borra."""
    return None if plan == "pagado" else _entero("QMC_DIAS_POLIZA_GRATIS", 14)


def puede_comparar(plan: str) -> bool:
    """¿Pagas doble? es del plan pagado."""
    return plan == "pagado"


# --- La bolsa de consultas ---

def saldo(motor: sa.Engine, usuario_id: str) -> int:
    with motor.connect() as c:
        return c.execute(sa.select(usuarios.c.saldo).where(usuarios.c.id == usuario_id)).scalar() or 0


def descontar(motor: sa.Engine, usuario_id: str, n: int = 1) -> bool:
    """Descuenta n de la bolsa si alcanza. En una sola sentencia: dos consultas a la vez no
    pueden gastar la misma consulta."""
    with motor.begin() as c:
        return c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id, usuarios.c.saldo >= n)
                         .values(saldo=usuarios.c.saldo - n)).rowcount > 0


def reponer(motor: sa.Engine, usuario_id: str, n: int = 1) -> None:
    with motor.begin() as c:
        c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id).values(saldo=sa.func.coalesce(usuarios.c.saldo, 0) + n))


# --- Radiografía ---

def radiografias_pagadas(cuenta: dict) -> list[str]:
    return json.loads(cuenta.get("radiografias") or "[]")


def acceso_radiografia(cuenta: dict | None, clave_poliza: str) -> str:
    """"ya_obtenida" (de esta póliza ya la tiene: no cuesta nada), "cobrar" (plan pagado: 5 de
    la bolsa), "sin_saldo" (plan pagado sin 5 consultas), "muestra" (la gratis, sin usar),
    "bloqueada" (la gratis ya se usó en otra) o "sin_cuenta"."""
    if cuenta is None:
        return "sin_cuenta"
    if clave_poliza == cuenta.get("radiografia_gratis") or clave_poliza in radiografias_pagadas(cuenta):
        return "ya_obtenida"
    if cuenta["plan"] == "pagado":
        return "cobrar" if (cuenta.get("saldo") or 0) >= COSTO_RADIOGRAFIA else "sin_saldo"
    return "muestra" if cuenta.get("radiografia_gratis") is None else "bloqueada"


def cobrar_radiografia(motor: sa.Engine, usuario_id: str, clave_poliza: str) -> bool:
    """Descuenta 5 de la bolsa y anota la póliza: volver a abrir esa radiografía no cuesta."""
    with motor.begin() as c:
        if not c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id, usuarios.c.saldo >= COSTO_RADIOGRAFIA)
                         .values(saldo=usuarios.c.saldo - COSTO_RADIOGRAFIA)).rowcount:
            return False
        vistas = json.loads(c.execute(sa.select(usuarios.c.radiografias).where(usuarios.c.id == usuario_id)).scalar() or "[]")
        c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id).values(radiografias=json.dumps(vistas + [clave_poliza])))
    return True


def devolver_radiografia(motor: sa.Engine, usuario_id: str, clave_poliza: str) -> None:
    """Si la radiografía no salió (el modelo falló), se devuelven las 5 consultas."""
    with motor.begin() as c:
        vistas = json.loads(c.execute(sa.select(usuarios.c.radiografias).where(usuarios.c.id == usuario_id)).scalar() or "[]")
        if clave_poliza in vistas:
            vistas.remove(clave_poliza)
            c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id).values(
                radiografias=json.dumps(vistas), saldo=usuarios.c.saldo + COSTO_RADIOGRAFIA))


def tomar_muestra(motor: sa.Engine, usuario_id: str, clave_poliza: str) -> bool:
    """Reserva la radiografía gratis para esa póliza. En una sola sentencia: dos pedidos a la
    vez por pólizas distintas no pueden llevarse las dos."""
    with motor.begin() as c:
        hecho = c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id, usuarios.c.radiografia_gratis.is_(None))
                          .values(radiografia_gratis=clave_poliza)).rowcount
        if hecho:
            return True
        return c.execute(sa.select(usuarios.c.radiografia_gratis).where(usuarios.c.id == usuario_id)).scalar() == clave_poliza


def soltar_muestra(motor: sa.Engine, usuario_id: str, clave_poliza: str) -> None:
    """Si la radiografía no salió (el modelo falló), la muestra gratis no se pierde."""
    with motor.begin() as c:
        c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id, usuarios.c.radiografia_gratis == clave_poliza)
                  .values(radiografia_gratis=None))


# --- El cobro ---

def id_ofuscado(usuario_id: str) -> str:
    """Lo que la app pasa a Play como obfuscatedAccountId: ata la compra a la cuenta sin darle
    a Google el id ni el correo."""
    return hashlib.sha256(f"qmc|{usuario_id}".encode()).hexdigest()


def _huella(comprobante: str) -> str:
    return hashlib.sha256(comprobante.encode()).hexdigest()


def ya_acreditada(motor: sa.Engine, usuario_id: str, comprobante: str) -> bool:
    """¿Esa compra ya se acreditó a esta cuenta? (la app la reenvía si no alcanzó a consumirla)"""
    with motor.connect() as c:
        return c.execute(sa.select(compras.c.usuario_id).where(compras.c.comprobante_hash == _huella(comprobante))).scalar() == usuario_id


def _token_play() -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    credenciales = service_account.Credentials.from_service_account_info(
        json.loads(config("QMC_PLAY_CUENTA_SERVICIO")), scopes=["https://www.googleapis.com/auth/androidpublisher"])
    credenciales.refresh(Request())
    return credenciales.token


def _consultar_play(producto: str, token_compra: str) -> dict:
    """purchases.products.get de la Google Play Developer API."""
    r = httpx.get(f"{PLAY}/{PAQUETE}/purchases/products/{producto}/tokens/{token_compra}",
                  headers={"Authorization": f"Bearer {_token_play()}"}, timeout=20)
    if r.status_code in (400, 404, 410):
        raise CompraInvalida("Play no conoce esa compra.")
    r.raise_for_status()
    return r.json()


def reconocer(producto: str, token_compra: str) -> None:
    """Reconoce la compra en Play (si no, Play la reembolsa a los 3 días). La app la consume
    después; si no alcanza, esto la deja a salvo. Sin cuenta de servicio, no hace nada."""
    if not config("QMC_PLAY_CUENTA_SERVICIO"):
        return
    try:
        httpx.post(f"{PLAY}/{PAQUETE}/purchases/products/{producto}/tokens/{token_compra}:acknowledge",
                   headers={"Authorization": f"Bearer {_token_play()}"}, json={}, timeout=20)
    except httpx.HTTPError:
        pass  # ya acreditada; si falló, consumirla en la app también la reconoce


def verificar_compra(token_compra: str, producto: str = PRODUCTO, cuenta: str | None = None) -> str:
    """Valida con Google Play una compra del producto y devuelve el token, que `acreditar`
    guarda como hash. Exige: pagada (purchaseState 0), sin consumir (consumptionState 0) y, si
    se da `cuenta`, hecha con ese id ofuscado. Si no: CompraInvalida."""
    if not config("QMC_PLAY_CUENTA_SERVICIO"):
        raise CobroNoDisponible("La compra todavía no está disponible.")
    datos = _consultar_play(producto, token_compra)
    if datos.get("purchaseState") != 0:
        raise CompraInvalida("La compra no está pagada.")
    if datos.get("consumptionState") == 1:
        raise CompraInvalida("La compra ya se usó.")
    if cuenta is not None and datos.get("obfuscatedExternalAccountId") != cuenta:
        raise CompraInvalida("La compra es de otra cuenta.")
    return token_compra


def acreditar(motor: sa.Engine, usuario_id: str, comprobante: str) -> bool:
    """Suma una bolsa de consultas a la cuenta, la pasa al plan pagado y quita la fecha de
    borrado de sus pólizas guardadas. Un mismo comprobante no se acredita dos veces."""
    huella = _huella(comprobante)
    n = consultas_por_pago()
    try:
        with motor.begin() as c:
            c.execute(sa.insert(compras).values(comprobante_hash=huella, usuario_id=usuario_id, creado=guardado.ahora(), consultas=n))
            if not c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id).values(
                    plan="pagado", saldo=sa.func.coalesce(usuarios.c.saldo, 0) + n)).rowcount:
                raise IntegrityError("cuenta inexistente", None, ValueError())
    except IntegrityError:
        return False
    guardado.conservar_polizas(motor, usuario_id)
    return True
