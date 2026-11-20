"""El plan pagado: qué desbloquea y cómo se activa. Es el único archivo que toca el cobro.

Producto: pago único de S/ 3,99, no consumible, vendido con Google Play Billing desde la app
de Android (Fase 4). La versión web no vende: ahí el plan pagado no se ofrece.

Qué desbloquea (todo lo demás es gratis: repregunta, varias preguntas, qué hacer ahora,
alerta de plazo y mapa):
- guardar hasta 4 pólizas, sin borrado automático (gratis: 1, que se borra a los 14 días);
- 20 consultas al día (gratis: 3), en backend/limites.py;
- ¿Pagas doble? (superposiciones entre pólizas): necesita varias pólizas;
- la radiografía de cualquier póliza. Cada cuenta gratis tiene una sola radiografía completa
  de muestra; la cuenta lleva en la base de qué póliza fue.

Cómo se activa: la app compra con Play Billing y manda el token de compra a POST /cuenta/compra.
`verificar_compra` es el punto donde se conecta Play Billing; hoy dice que el cobro no está
disponible, así que no hay forma de pasar al plan pagado fuera de las pruebas automáticas,
que llaman a `activar` directamente.
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa

from ai.llm import config
from backend import guardado
from backend.guardado import usuarios

PRODUCTO = "plan_pagado"  # id del producto no consumible en Play Console
PRECIO = "S/ 3,99"


class CobroNoDisponible(RuntimeError):
    """Todavía no hay cobro: Play Billing llega con la app de Android (Fase 4)."""


class CompraInvalida(ValueError):
    """Play no confirma esa compra."""


def _entero(nombre: str, defecto: int) -> int:
    return int(config(nombre, str(defecto)) or defecto)


def polizas_permitidas(plan: str) -> int:
    return _entero("QMC_POLIZAS_PAGADO", 4) if plan == "pagado" else _entero("QMC_POLIZAS_GRATIS", 1)


def dias_de_guardado(plan: str) -> int | None:
    """Plan gratis: la póliza guardada se borra sola a los 14 días. Plan pagado: no se borra."""
    return None if plan == "pagado" else _entero("QMC_DIAS_POLIZA_GRATIS", 14)


def puede_comparar(plan: str) -> bool:
    """¿Pagas doble? es del plan pagado."""
    return plan == "pagado"


def acceso_radiografia(cuenta: dict | None, clave_poliza: str) -> str:
    """"pagado" (todas), "muestra" (la gratis, todavía sin usar), "ya_obtenida" (la gratis, de
    esta misma póliza), "bloqueada" (la gratis ya se usó en otra) o "sin_cuenta"."""
    if cuenta is None:
        return "sin_cuenta"
    if cuenta["plan"] == "pagado":
        return "pagado"
    usada = cuenta.get("radiografia_gratis")
    if usada is None:
        return "muestra"
    return "ya_obtenida" if usada == clave_poliza else "bloqueada"


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


def verificar_compra(token_compra: str, producto: str = PRODUCTO) -> str:
    """Valida con Google Play el token de una compra del producto y devuelve un comprobante.

    PUNTO DE INTEGRACIÓN (Google Play Billing, Fase 4): consultar purchases.products.get de la
    Google Play Developer API (paquete de la app, `producto`, `token_compra`) con una cuenta de
    servicio; aceptar solo purchaseState == 0 (comprada), reconocer la compra
    (acknowledge) y devolver el token, que `activar` guarda como hash. Si Play no la confirma:
    CompraInvalida.
    """
    raise CobroNoDisponible("El pago único se hace desde la app de Android.")


def activar(motor: sa.Engine, usuario_id: str, comprobante: str) -> bool:
    """Pasa la cuenta al plan pagado y quita la fecha de borrado de sus pólizas guardadas.
    Un mismo comprobante no activa dos cuentas."""
    huella = hashlib.sha256(comprobante.encode()).hexdigest()
    with motor.begin() as c:
        otra = c.execute(sa.select(usuarios.c.id).where(usuarios.c.compra == huella, usuarios.c.id != usuario_id)).first()
        if otra is not None:
            return False
        if not c.execute(sa.update(usuarios).where(usuarios.c.id == usuario_id).values(plan="pagado", compra=huella)).rowcount:
            return False
    guardado.conservar_polizas(motor, usuario_id)
    return True
